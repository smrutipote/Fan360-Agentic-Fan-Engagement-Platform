# personalisation_agent.py
# ─────────────────────────────────────────────────────────────────────────────
# Fan360 PersonalisationAgent (child)
#
# Receives: FanContext payload from Orchestrator via A2A
# Does:     LLM reasons over context → picks personalised offer
# Returns:  offer JSON back to Orchestrator
#
# Rules:
#   - NO tools
#   - NO database access
#   - NO MCP access
#   - Pure LLM decision from FanContext only
#   - Orchestrator writes result to gold_fact_engagement (not this agent)
# ─────────────────────────────────────────────────────────────────────────────

import os
import json
import time
from azure.identity import AzureCliCredential
from azure.ai.agents import AgentsClient
from dotenv import load_dotenv

load_dotenv()

# ── Azure AI Foundry client ───────────────────────────────────────────────────
agents_client = AgentsClient(
    endpoint=os.getenv("AZURE_AI_FOUNDRY_ENDPOINT"),
    credential=AzureCliCredential()
)

PERSONALISATION_AGENT_ID = os.getenv("AZURE_AI_PERSONALISATION_AGENT_ID")

INSTRUCTIONS = """
You are the Fan360 Personalisation Agent. Your job is to generate a
personalised engagement offer for an active fan based on their preferences.

## YOUR OUTPUT MUST ALWAYS BE VALID JSON — NOTHING ELSE

Return exactly this structure:

{
  "fan_id": "<fan_id>",
  "offer_type": "<MatchDayExperience|PlayerContent|EarlyAccess|LoyaltyReward|ExclusiveContent>",
  "offer_detail": "<one sentence, personalised to favourite_player or favourite_team>",
  "channel": "<push|email|sms>",
  "urgency": <true|false>,
  "reasoning": "<one sentence explaining the personalisation decision>"
}

## PERSONALISATION RULES

| Condition                                      | offer_type           |
|------------------------------------------------|----------------------|
| favourite_player is set                        | PlayerContent        |
| favourite_team is set, upcoming match          | MatchDayExperience   |
| fan has high loyalty (VIP/Diehard segment)     | EarlyAccess          |
| fan has milestone engagement (attended 10+)    | LoyaltyReward        |
| no strong signal but active                    | ExclusiveContent     |

## CHANNEL RULES
- push_opt_in = true  → prefer push
- email_opt_in = true → use email if no push
- fallback             → email

## HARD RULES — NEVER VIOLATE
1. Output raw JSON only — no markdown, no explanation, no code blocks
2. offer_detail MUST mention favourite_player OR favourite_team if available
3. urgency = true only for time-sensitive offers (match tomorrow, 24h window)
4. NEVER return target_child_agent — that is the Orchestrator's field
"""


# ── Main PersonalisationAgent Runner ──────────────────────────────────────────
# Input:  fan_context dict assembled by Orchestrator
# Output: offer dict returned to Orchestrator
def run_personalisation_agent(fan_context: dict) -> dict:
    fan_id = fan_context.get("fan_id", "UNKNOWN")
    print(f"\n▶ PersonalisationAgent processing: {fan_id}")
    print(f"  📦 Context received: {json.dumps(fan_context, indent=2)}")

    # Create a new thread for this fan
    thread = agents_client.threads.create()
    print(f"  📋 Thread: {thread.id}")

    # Send FanContext as the user message — this is ALL the agent sees
    agents_client.messages.create(
        thread_id=thread.id,
        role="user",
        content=(
            f"Generate a personalised offer for this fan.\n\n"
            f"FanContext:\n{json.dumps(fan_context, indent=2)}"
        )
    )

    # Start run — no tools, pure LLM
    run = agents_client.runs.create(
        thread_id=thread.id,
        agent_id=PERSONALISATION_AGENT_ID
    )
    print(f"  🚀 Run: {run.id}")

    # Poll until complete
    while run.status in ["queued", "in_progress"]:
        time.sleep(1)
        run = agents_client.runs.get(thread_id=thread.id, run_id=run.id)
        print(f"  ⏳ Status: {run.status}")

    if run.status == "completed":
        messages      = list(agents_client.messages.list(thread_id=thread.id))
        response_text = messages[0].content[0].text.value
        print(f"\n✅ PersonalisationAgent decision:\n{response_text}")

        # Parse JSON from response
        try:
            start  = response_text.find("{")
            end    = response_text.rfind("}") + 1
            result = json.loads(response_text[start:end])
            return result
        except json.JSONDecodeError:
            return {"raw_response": response_text, "fan_id": fan_id}

    print(f"  ❌ Run failed: {run.status}")
    return {"error": f"Run ended with status: {run.status}", "fan_id": fan_id}
