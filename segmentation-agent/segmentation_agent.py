# segmentation_agent.py
# ─────────────────────────────────────────────────────────────────────────────
# Fan360 SegmentationAgent (child)
#
# Receives: Fan signals from Orchestrator
# Does:     Analyses signals → assigns correct segment + recommends next agent
# Returns:  segment assignment JSON back to Orchestrator
#
# Rules:
#   - NO tools
#   - NO database access
#   - NO MCP access
#   - Pure LLM decision from FanContext only
#   - Orchestrator may re-route to recommended_next_agent after segmentation
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

SEGMENTATION_AGENT_ID = os.getenv("AZURE_AI_SEGMENTATION_AGENT_ID")

INSTRUCTIONS = """
You are the Fan360 Segmentation Agent. Your job is to analyse a fan's
behavioural signals and assign the most accurate segment.

## YOUR OUTPUT MUST ALWAYS BE VALID JSON — NOTHING ELSE

Return exactly this structure:

{
  "fan_id": "<fan_id>",
  "assigned_segment": "<VIP Diehard|Loyal Regular|Casual Fan|Lapsed Fan|New Fan|At Risk>",
  "confidence": "<HIGH|MEDIUM|LOW>",
  "recommended_next_agent": "<ChurnAgent|PersonalisationAgent|RecommendationAgent|none>",
  "reasoning": "<one sentence explaining the segmentation decision>"
}

## SEGMENTATION RULES

| Signal                                              | Segment           |
|-----------------------------------------------------|-------------------|
| churn_score > 0.75 OR null, previously active       | At Risk           |
| last_contact > 90 days, was previously active       | Lapsed Fan        |
| push_opt_in=true, high engagement history           | VIP Diehard       |
| regular attendance, moderate churn_score            | Loyal Regular     |
| 1–2 interactions only                               | New Fan           |
| occasional attendance, low spend                    | Casual Fan        |

## NEXT AGENT RECOMMENDATION RULES

| assigned_segment   | recommended_next_agent   |
|--------------------|--------------------------|
| At Risk            | ChurnAgent               |
| Lapsed Fan         | RecommendationAgent      |
| VIP Diehard        | PersonalisationAgent     |
| Loyal Regular      | PersonalisationAgent     |
| Casual Fan         | RecommendationAgent      |
| New Fan            | PersonalisationAgent     |

## HARD RULES — NEVER VIOLATE
1. Output raw JSON only — no markdown, no explanation, no code blocks
2. ALWAYS include recommended_next_agent — Orchestrator uses it to re-route
3. confidence = HIGH only when 3+ signals align clearly
4. NEVER generate an offer — that is the child offer agent's job
"""


# ── Main SegmentationAgent Runner ─────────────────────────────────────────────
# Input:  fan_context dict assembled by Orchestrator
# Output: segment assignment dict returned to Orchestrator
def run_segmentation_agent(fan_context: dict) -> dict:
    fan_id = fan_context.get("fan_id", "UNKNOWN")
    print(f"\n▶ SegmentationAgent processing: {fan_id}")
    print(f"  📦 Context received: {json.dumps(fan_context, indent=2)}")

    # Create a new thread for this fan
    thread = agents_client.threads.create()
    print(f"  📋 Thread: {thread.id}")

    # Send FanContext as the user message — this is ALL the agent sees
    agents_client.messages.create(
        thread_id=thread.id,
        role="user",
        content=(
            f"Analyse and assign the correct segment for this fan.\n\n"
            f"FanContext:\n{json.dumps(fan_context, indent=2)}"
        )
    )

    # Start run — no tools, pure LLM
    run = agents_client.runs.create(
        thread_id=thread.id,
        agent_id=SEGMENTATION_AGENT_ID
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
        print(f"\n✅ SegmentationAgent decision:\n{response_text}")

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
