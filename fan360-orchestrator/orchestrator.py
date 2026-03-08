# orchestrator.py
# ─────────────────────────────────────────────────────────────────────────────
# Fan360 Orchestrator — MCP Version
# Gold tables accessed exclusively via DAB MCP Server (localhost:5000)
# No pyodbc. No direct SQL. All reads/writes go through MCP.
# ─────────────────────────────────────────────────────────────────────────────

import os
import json
import time
import uuid
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
from azure.identity import AzureCliCredential
from azure.ai.agents import AgentsClient
from dotenv import load_dotenv

# AutoGen A2A — formal agent-to-agent message passing
from autogen_agents import a2a_dispatch, a2a_chain_dispatch, AGENT_REGISTRY

# Live event stream — push_event() sends SSE to Control Room UI
from event_bus import push_event

load_dotenv()

# ── Semantic Kernel plugins ───────────────────────────────────────────────────
from semantic_kernel import Kernel
from sk_plugins import FabricMCPPlugin, EngagementLogPlugin

def build_kernel() -> Kernel:
    kernel = Kernel()
    kernel.add_plugin(FabricMCPPlugin(),     plugin_name="FabricMCP")
    kernel.add_plugin(EngagementLogPlugin(), plugin_name="EngagementLog")
    return kernel

KERNEL = build_kernel()

# ── Azure AI Foundry client ───────────────────────────────────────────────────
agents_client = AgentsClient(
    endpoint=os.getenv("AZURE_AI_FOUNDRY_ENDPOINT"),
    credential=AzureCliCredential()
)
AGENT_ID = os.getenv("AZURE_AI_AGENT_ID")

# ── Hardened Orchestrator Instructions ────────────────────────────────────────────
ORCHESTRATOR_INSTRUCTIONS = """
You are the Fan360 Orchestrator Agent. Your ONLY job is to analyse a fan's 
profile and return a structured routing decision. You do NOT generate offers, 
messages, or recommendations yourself.

## YOUR OUTPUT MUST ALWAYS BE VALID JSON — NOTHING ELSE

Return exactly this structure:

{
  "fan_id": "<fan_id>",
  "fan_segment": "<segment>",
  "churn_risk": "<LOW|MEDIUM|HIGH>",
  "target_child_agent": "<ChurnAgent|PersonalisationAgent|RecommendationAgent|SegmentationAgent|SponsorMatchingAgent>",
  "suppress": false,
  "use_chain": <true|false>,
  "chain_reason": "<why chaining is needed, or null>",
  "event_type": "<from the input payload, e.g. ChurnDrop, BirthdayEvent, GateScan, CartAbandoned>",
  "fan_context": {
    "favourite_player": "<value or null>",
    "favourite_team": "<value or null>",
    "push_opt_in": <true|false>,
    "email_opt_in": <true|false>,
    "last_contact_date": "<ISO date or null>",
    "churn_score": <float or null>
  },
  "reasoning": "<one sentence explaining the routing decision>"
}

## ROUTING RULES

| Condition                              | target_child_agent         |
|----------------------------------------|----------------------------|
| churn_score > 0.75 OR score is null    | ChurnAgent                 |
| churn_score <= 0.75, active fan        | PersonalisationAgent       |
| inactive fan, low engagement           | RecommendationAgent        |
| segment unknown or needs reclassifying | SegmentationAgent          |
| VIP Diehard OR Loyal Regular, low churn, high-value signal | SponsorMatchingAgent |
| event_type = BirthdayEvent                                 | CHAIN (use_chain=true) |
| event_type = GateScan, VIP Diehard                         | CHAIN (use_chain=true) |
| event_type = CartAbandoned                                 | CHAIN (use_chain=true) |

When use_chain = true, set target_child_agent to the FIRST agent in the chain
(usually SegmentationAgent). The Orchestrator code will handle running the
full chain: SegmentationAgent → RecommendationAgent → PersonalisationAgent.

## HARD RULES — NEVER VIOLATE
1. NEVER produce offer_type, offer_detail, or channel in your output
2. NEVER make the offer yourself — that is the child agent's job
3. ALWAYS include target_child_agent
4. ALWAYS include fan_context with the fields above
5. Output raw JSON only — no markdown, no explanation, no code blocks
6. SUPPRESS RULE: set "suppress" to true ONLY when days_since_last_contact < 7.
   If days_since_last_contact is null, 999, or >= 7, set "suppress" to false.
"""

# ── MCP Server config ─────────────────────────────────────────────────────────
MCP_BASE_URL = os.getenv("MCP_BASE_URL", "http://localhost:5000/mcp")
MCP_HEADERS  = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}

# ── MCP session management ────────────────────────────────────────────────────
_mcp_session_id = None
_mcp_request_id = 0

def _next_mcp_id() -> int:
    global _mcp_request_id
    _mcp_request_id += 1
    return _mcp_request_id

def _parse_sse_data(response) -> dict | None:
    """Extract the first data: payload from an SSE response."""
    for line in response.iter_lines():
        if line:
            decoded = line.decode("utf-8")
            if decoded.startswith("data:"):
                return json.loads(decoded[len("data:"):].strip())
    return None

def _ensure_mcp_session():
    """Initialize an MCP session if we don't have one yet."""
    global _mcp_session_id
    if _mcp_session_id:
        return
    payload = {
        "jsonrpc": "2.0",
        "id": _next_mcp_id(),
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "fan360-orchestrator", "version": "1.0"}
        }
    }
    resp = requests.post(
        MCP_BASE_URL,
        headers=MCP_HEADERS,
        json=payload,
        stream=True,
        timeout=15
    )
    _mcp_session_id = resp.headers.get("Mcp-Session-Id")
    _parse_sse_data(resp)  # consume the response


# ── Core MCP caller — handles SSE framing ────────────────────────────────────
# DAB MCP uses Server-Sent Events (SSE)
# Response format:  event: message\ndata: {...}\n\n
# We parse the data: line and return it as a dict
def mcp_call(tool_name: str, arguments: dict) -> dict:
    _ensure_mcp_session()
    payload = {
        "jsonrpc": "2.0",
        "id":      _next_mcp_id(),
        "method":  "tools/call",
        "params":  {
            "name":      tool_name,
            "arguments": arguments
        }
    }
    headers = {**MCP_HEADERS}
    if _mcp_session_id:
        headers["Mcp-Session-Id"] = _mcp_session_id
    try:
        response = requests.post(
            MCP_BASE_URL,
            headers=headers,
            json=payload,
            stream=True,
            timeout=15
        )
        result = _parse_sse_data(response)
        if result is None:
            return {"error": "No data returned from MCP"}
        # DAB returns result inside content[0].text as JSON string
        if "result" in result:
            content = result["result"].get("content", [])
            if content and content[0].get("type") == "text":
                inner = json.loads(content[0]["text"])
                # Unwrap: {entity, result: {value: [...]}, ...} → return the inner "result" dict
                if "result" in inner and isinstance(inner["result"], dict):
                    return inner["result"]
                return inner
        if "error" in result:
            return {"error": result["error"].get("message", str(result["error"]))}
        return result
    except Exception as e:
        return {"error": str(e)}


# ── STEP 1 TOOL: Fan Profile ──────────────────────────────────────────────────
# MCP → read_records on gold_dim_fan
# Returns: email, consent flags, spend, season ticket status
def get_fan_profile(fan_id: str) -> dict:
    result = mcp_call("read_records", {
        "entity":  "gold_dim_fan",
        "filter":  f"fan_id eq '{fan_id}'",
        "select":  "fan_id,fan_email,marketing_opt_in,push_opt_in,dob,postcode,is_season_ticket_holder,total_ticket_spend_eur,total_app_events,avg_sentiment_score,last_app_activity,last_purchase_date",
        "first":   1
    })
    items = result.get("value", [])
    if items:
        row = items[0]
        return {
            "fan_id":                  row.get("fan_id"),
            "fan_email":               row.get("fan_email"),
            "marketing_opt_in":        bool(row.get("marketing_opt_in")),
            "push_opt_in":             bool(row.get("push_opt_in")),
            "dob":                     row.get("dob"),
            "postcode":                row.get("postcode"),
            "is_season_ticket_holder": bool(row.get("is_season_ticket_holder")),
            "total_ticket_spend_eur":  float(row.get("total_ticket_spend_eur") or 0),
            "total_app_events":        int(row.get("total_app_events") or 0),
            "avg_sentiment_score":     float(row.get("avg_sentiment_score") or 0),
            "last_app_activity":       row.get("last_app_activity"),
            "last_purchase_date":      row.get("last_purchase_date")
        }
    return {"error": f"Fan {fan_id} not found"}


# ── STEP 2 TOOL: Last Contact ─────────────────────────────────────────────────
# MCP → read_records on gold_fact_engagement
# Filter: row_type = AGENT_ACTION only
# Returns: days_since_last_contact for 7-day suppression
def get_last_contact(fan_id: str) -> dict:
    result = mcp_call("read_records", {
        "entity":  "gold_fact_engagement",
        "filter":  f"fan_id eq '{fan_id}' and row_type eq 'AGENT_ACTION'",
        "select":  "fan_id,event_timestamp",
        "orderby": ["event_timestamp desc"],
        "first":   1
    })
    items = result.get("value", [])
    if items:
        from datetime import datetime, timezone
        ts  = items[0].get("event_timestamp")
        dt  = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        days = (now - dt).days
        return {
            "days_since_last_contact": days,
            "last_contact_date":       str(ts)
        }
    return {
        "days_since_last_contact": 999,
        "last_contact_date":       None
    }


# ── STEP 3 TOOL: Fan Segment ──────────────────────────────────────────────────
# MCP → read_records on gold_fan_segments
# Returns: fan_segment label e.g. 'VIP Diehard'
def get_fan_segment(fan_id: str) -> dict:
    result = mcp_call("read_records", {
        "entity": "gold_fan_segments",
        "filter": f"fan_id eq '{fan_id}'",
        "select": "fan_id,fan_segment,prediction",
        "first":  1
    })
    items = result.get("value", [])
    if items:
        return {
            "fan_id":      items[0].get("fan_id"),
            "fan_segment": items[0].get("fan_segment"),
            "prediction":  items[0].get("prediction")
        }
    return {"fan_segment": "Unknown", "prediction": None}


# ── STEP 4 TOOL: Churn Score ──────────────────────────────────────────────────
# MCP → read_records on gold_churn_score
# Only called when event_type = ChurnDrop
def get_churn_score(fan_id: str) -> dict:
    result = mcp_call("read_records", {
        "entity": "gold_churn_score",
        "filter": f"fan_id eq '{fan_id}'",
        "select": "fan_id,churn_score,days_since_app,days_since_purchase",
        "first":  1
    })
    items = result.get("value", [])
    if items:
        return {
            "fan_id":              items[0].get("fan_id"),
            "churn_score":         items[0].get("churn_score"),
            "days_since_app":      items[0].get("days_since_app"),
            "days_since_purchase": items[0].get("days_since_purchase")
        }
    return {
        "churn_score":         None,
        "days_since_app":      None,
        "days_since_purchase": None
    }


# ── STEP 8: Write AGENT_ACTION back to gold_fact_engagement ──────────────────
# OneLake DFS API — writes JSON to lakehouse Files path
# Schema-enabled lakehouses don't support the Tables /rows API
# Called by orchestrator AFTER child agent returns result
# This is what makes the 7-day suppression work next time
def write_agent_action(fan_id: str, routing_decision: dict, child_result: dict):
    """
    Writes AGENT_ACTION to OneLake Files via the DFS API.
    Each action lands as a JSON file under Files/agent_actions/.
    A downstream notebook/dataflow can merge these into the delta table.
    Token is fetched dynamically via AzureCliCredential so it never expires.
    """
    workspace_id = os.environ.get("FABRIC_WORKSPACE_ID")
    lakehouse_id = os.environ.get("FABRIC_LAKEHOUSE_ID")

    if not all([workspace_id, lakehouse_id]):
        print("  ⚠️  Write-back skipped: FABRIC_WORKSPACE_ID / FABRIC_LAKEHOUSE_ID not set")
        return {"status": "skipped", "reason": "FABRIC env vars not set"}

    # Dynamic token — never expires mid-session
    token = AzureCliCredential().get_token("https://storage.azure.com/.default").token

    record = {
        "engagement_id":    str(uuid.uuid4()),
        "fan_id":           fan_id,
        "event_type":       "AGENT_ACTION",
        "event_timestamp":  datetime.now(timezone.utc).isoformat(),
        "offer_type":       child_result.get("offer_type"),
        "offer_detail":     child_result.get("offer_detail"),
        "channel":          child_result.get("channel"),
        "churn_risk":       routing_decision.get("churn_risk"),
        "target_agent":     routing_decision.get("target_child_agent"),
        "reasoning":        child_result.get("reasoning"),
    }

    # OneLake DFS path:  Files/agent_actions/<engagement_id>.json
    file_name = f"{record['engagement_id']}.json"
    dfs_url = (
        f"https://onelake.dfs.fabric.microsoft.com"
        f"/{workspace_id}/{lakehouse_id}"
        f"/Files/agent_actions/{file_name}"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }

    # Step 1: Create the file (PUT with ?resource=file)
    create_resp = requests.put(
        f"{dfs_url}?resource=file",
        headers=headers
    )
    if create_resp.status_code not in (200, 201):
        print(f"  ⚠️  Step 8 file create failed: {create_resp.status_code} — {create_resp.text}")
        return {"status": "error", "code": create_resp.status_code, "detail": create_resp.text}

    # Step 2: Append data + flush (PATCH with ?action=append&position=0, then ?action=flush)
    body = json.dumps(record, default=str).encode("utf-8")
    append_resp = requests.patch(
        f"{dfs_url}?action=append&position=0",
        headers={**headers, "Content-Length": str(len(body))},
        data=body
    )
    if append_resp.status_code not in (200, 202):
        print(f"  ⚠️  Step 8 append failed: {append_resp.status_code} — {append_resp.text}")
        return {"status": "error", "code": append_resp.status_code, "detail": append_resp.text}

    # Step 3: Flush
    flush_resp = requests.patch(
        f"{dfs_url}?action=flush&position={len(body)}",
        headers=headers
    )
    if flush_resp.status_code not in (200,):
        print(f"  ⚠️  Step 8 flush failed: {flush_resp.status_code} — {flush_resp.text}")
        return {"status": "error", "code": flush_resp.status_code, "detail": flush_resp.text}

    print(f"  ✅ Step 8 write-back: {file_name} written to OneLake for {fan_id}")
    return {"status": "success", "fan_id": fan_id, "file": file_name}


# ── Tool Dispatcher ───────────────────────────────────────────────────────────
def dispatch_tool(tool_name: str, arguments: dict) -> str:
    fan_id = str(arguments.get("fan_id"))
    if tool_name == "get_fan_profile":
        return json.dumps(get_fan_profile(fan_id))
    elif tool_name == "get_last_contact":
        return json.dumps(get_last_contact(fan_id))
    elif tool_name == "get_fan_segment":
        return json.dumps(get_fan_segment(fan_id))
    elif tool_name == "get_churn_score":
        return json.dumps(get_churn_score(fan_id))
    return json.dumps({"error": f"Unknown tool: {tool_name}"})


# ── Tool Schema (unchanged — LLM sees same interface) ─────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_fan_profile",
            "description": (
                "STEP 1 — Always call first. "
                "Reads gold_dim_fan via MCP. Returns fan_email, marketing_opt_in, "
                "push_opt_in, dob, postcode, is_season_ticket_holder, "
                "total_ticket_spend_eur, total_app_events, avg_sentiment_score."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fan_id": {"type": "string"}
                },
                "required": ["fan_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_last_contact",
            "description": (
                "STEP 2 — Reads gold_fact_engagement via MCP. AGENT_ACTION rows only. "
                "Returns days_since_last_contact. "
                "If < 7 days → suppress. If >= 7 days → proceed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fan_id": {"type": "string"}
                },
                "required": ["fan_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_fan_segment",
            "description": (
                "STEP 3 — Reads gold_fan_segments via MCP. "
                "Returns fan_segment: VIP Diehard, Casual Viewer, Lapsed etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fan_id": {"type": "string"}
                },
                "required": ["fan_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_churn_score",
            "description": (
                "STEP 4 — Only call when event_type = ChurnDrop. "
                "Reads gold_churn_score via MCP. "
                "Returns churn_score (0-1), days_since_app, days_since_purchase."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fan_id": {"type": "string"}
                },
                "required": ["fan_id"]
            }
        }
    }
]


# ── Birthday Email Sender ───────────────────────────────────────────────────
def send_birthday_email(to_email: str, fan_id: str, chain_result: dict):
    """Send birthday offer email using Gmail SMTP"""

    pers   = chain_result.get("personalisation", {})
    rec    = chain_result.get("recommendation", {})
    seg    = chain_result.get("segmentation", {})

    offer_detail  = pers.get("offer_detail", "Happy Birthday from Fan360!")
    offer_type    = pers.get("offer_type", "BirthdayOffer")
    rec_offer     = rec.get("offer_detail", "")
    segment       = seg.get("assigned_segment", "Valued Fan")

    subject = f"\U0001f382 Happy Birthday from Leinster Rugby \u2014 A Special Gift for You"

    html_body = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: auto;">
      <div style="background: #003087; padding: 20px; text-align: center;">
        <h1 style="color: white;">\U0001f382 Happy Birthday!</h1>
        <p style="color: #90caf9;">From everyone at Leinster Rugby & Fan360</p>
      </div>

      <div style="padding: 30px;">
        <p style="font-size: 16px;">Dear <strong>{segment}</strong>,</p>

        <p style="font-size: 16px;">{offer_detail}</p>

        <div style="background: #f0f4ff; padding: 15px; border-radius: 8px; margin: 20px 0;">
          <p style="margin: 0; font-weight: bold;">\U0001f381 Your Birthday Offer:</p>
          <p style="margin: 8px 0 0 0;">{rec_offer}</p>
        </div>

        <p style="font-size: 14px; color: #666;">
          Offer type: <strong>{offer_type}</strong><br>
          Fan ID: {fan_id}<br>
          Powered by Fan360 \u00b7 Azure AI Foundry \u00b7 Multi-Agent System
        </p>
      </div>

      <div style="background: #003087; padding: 15px; text-align: center;">
        <p style="color: white; font-size: 12px; margin: 0;">
          Fan360 \u2014 Powered by Microsoft Fabric + Azure AI Foundry
        </p>
      </div>
    </body></html>
    """

    # Gmail SMTP
    sender_email    = os.environ["GMAIL_SENDER"]
    sender_password = os.environ["GMAIL_APP_PASSWORD"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = sender_email
    msg["To"]      = to_email
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())

    print(f"  \U0001f4e7 Birthday email sent to {to_email} \u2705")


# ── Multi-Agent Chain Runner (delegates to AutoGen A2A) ──────────────────────
def run_chained_agents(fan_id: str, fan_context: dict, event_type: str) -> dict:
    """
    Multi-agent chain via AutoGen A2A message passing.
    SegmentationAgent → RecommendationAgent → PersonalisationAgent
    """
    return a2a_chain_dispatch(fan_id, fan_context, event_type)


# ── Main Orchestrator Runner ──────────────────────────────────────────────────
def run_orchestrator(event_payload: dict) -> dict:
    fan_id = event_payload.get("fan_id", "unknown")
    print(f"\n▶ Running orchestrator for: {event_payload}")
    push_event("THINKING", f"Reading fan profile for {fan_id} from Gold tables via MCP", "Orchestrator")

    thread = agents_client.threads.create()
    print(f"  📋 Thread created: {thread.id}")

    agents_client.messages.create(
        thread_id=thread.id,
        role="user",
        content=json.dumps(event_payload)
    )

    run = agents_client.runs.create(
        thread_id=thread.id,
        agent_id=AGENT_ID,
        tools=TOOLS,
        instructions=ORCHESTRATOR_INSTRUCTIONS
    )
    print(f"  🚀 Run started: {run.id}")

    while run.status in ["queued", "in_progress", "requires_action"]:
        time.sleep(1)
        run = agents_client.runs.get(thread_id=thread.id, run_id=run.id)
        print(f"  ⏳ Status: {run.status}")

        if run.status == "requires_action":
            tool_outputs = []
            for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                args   = json.loads(tool_call.function.arguments)
                push_event("THINKING", f"Calling MCP tool: {tool_call.function.name}({args})", "Orchestrator")
                result = dispatch_tool(tool_call.function.name, args)
                print(f"  🔧 Tool: {tool_call.function.name}({args}) → {result}")
                tool_outputs.append({
                    "tool_call_id": tool_call.id,
                    "output":       result
                })
            run = agents_client.runs.submit_tool_outputs(
                thread_id=thread.id,
                run_id=run.id,
                tool_outputs=tool_outputs
            )

    if run.status == "completed":
        messages      = list(agents_client.messages.list(thread_id=thread.id))
        response_text = messages[0].content[0].text.value
        print(f"\n✅ Orchestrator routing decision:\n{response_text}")

        try:
            routing_decision = json.loads(response_text)
        except json.JSONDecodeError:
            push_event("ERROR", f"Failed to parse routing JSON: {response_text[:200]}", "Orchestrator")
            return {"raw_response": response_text}

        push_event("ROUTING", f"Routing decision: {routing_decision.get('target_child_agent')} — {routing_decision.get('reasoning')}", "Orchestrator", routing_decision)

        # ── STEP 6 + 7: A2A — call child agent or chain ────────────────────────
        if not routing_decision.get("suppress"):
            target     = routing_decision.get("target_child_agent")
            use_chain  = routing_decision.get("use_chain", False)
            fan_context = routing_decision.get("fan_context", {})

            # Add fan_id and fan_segment into context so child has full picture
            fan_context["fan_id"]        = routing_decision.get("fan_id")
            fan_context["fan_segment"]   = routing_decision.get("fan_segment")
            fan_context["birthday_event"] = (
                routing_decision.get("event_type") == "BirthdayEvent"
            )

            if use_chain:
                # ── MULTI-AGENT CHAIN (AutoGen A2A) ───────────────────────
                print(f"\n  🔗 Chain mode activated for {routing_decision['fan_id']}")
                push_event("A2A", f"Chain mode: SegmentationAgent → RecommendationAgent → PersonalisationAgent", "Orchestrator")
                child_result = run_chained_agents(
                    fan_id=routing_decision["fan_id"],
                    fan_context=fan_context,
                    event_type=routing_decision.get("event_type", "Unknown")
                )
            elif target == "SegmentationAgent":
                # SegmentationAgent may re-route to another agent
                seg_result = a2a_dispatch("SegmentationAgent", fan_context)
                child_result = seg_result

                next_agent = seg_result.get("recommended_next_agent")
                if next_agent and next_agent != "none" and seg_result.get("confidence") == "HIGH":
                    print(f"\n  🔄 SegmentationAgent re-routing → {next_agent}")
                    fan_context["fan_segment"] = seg_result["assigned_segment"]
                    child_result = a2a_dispatch(next_agent, fan_context)
            else:
                # ── Single A2A dispatch (AutoGen) ─────────────────────────
                push_event("A2A", f"Orchestrator → {target}: sending fan context", target)
                child_result = a2a_dispatch(target, fan_context)

            print(f"  ✅ Child result: {child_result}")
            push_event("RESULT", f"{target} responded with {child_result.get('offer_type', child_result.get('assigned_segment', 'result'))}", target, child_result)

            # ── STEP 8: Write AGENT_ACTION back to gold_fact_engagement ──────
            print(f"\n  📝 Step 8: Writing AGENT_ACTION to gold_fact_engagement")
            push_event("WRITEBACK", f"Writing AGENT_ACTION to gold_fact_engagement for {routing_decision['fan_id']}", "Orchestrator")
            write_agent_action(
                routing_decision["fan_id"],
                routing_decision,
                child_result
            )

            # Send real email for BirthdayEvent
            if routing_decision.get("event_type") == "BirthdayEvent" and use_chain:
                send_birthday_email(
                    to_email="smrutipote0502@gmail.com",
                    fan_id=routing_decision["fan_id"],
                    chain_result=child_result
                )

            # Return complete end-to-end result
            return {
                "orchestrator": routing_decision,
                "child_agent":  child_result
            }

        # Suppressed — no child agent called, no write-back
        return routing_decision

    print(f"  ❌ Run failed: {run.status}")
    return {"error": f"Run ended with status: {run.status}"}
