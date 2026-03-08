# recommendation_agent.py
# ─────────────────────────────────────────────────────────────────────────────
# Fan360 RecommendationAgent (child)
#
# Receives: FanContext payload from Orchestrator via A2A
# Does:     LLM reasons over context → generates re-activation recommendation
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

RECOMMENDATION_AGENT_ID = os.getenv("AZURE_AI_RECOMMENDATION_AGENT_ID")

INSTRUCTIONS = """
You are the Fan360 Recommendation Agent. Your job is to re-activate
an inactive fan by generating a compelling, personalised recommendation.

## YOUR OUTPUT MUST ALWAYS BE VALID JSON — NOTHING ELSE

Return exactly this structure:

{
  "fan_id": "<fan_id>",
  "offer_type": "<MatchTicketOffer|ContentDigest|ReferralIncentive|SeasonPassPromo|WinBackOffer>",
  "offer_detail": "<one sentence, personalised to favourite_player or favourite_team>",
  "channel": "<push|email|sms>",
  "urgency": <true|false>,
  "reasoning": "<one sentence explaining the re-activation decision>"
}

## RECOMMENDATION RULES

| Condition                                        | offer_type          |
|--------------------------------------------------|---------------------|
| last_contact > 60 days OR never contacted        | WinBackOffer        |
| last_contact 30–60 days, has favourite_team      | MatchTicketOffer    |
| last_contact 30–60 days, no team preference      | ContentDigest       |
| fan previously attended matches                  | SeasonPassPromo     |
| fan has social/referral signal                   | ReferralIncentive   |

## CHANNEL RULES
- push_opt_in = true  → prefer push
- email_opt_in = true → use email if no push
- fallback            → email

## HARD RULES — NEVER VIOLATE
1. Output raw JSON only — no markdown, no explanation, no code blocks
2. offer_detail MUST mention favourite_player OR favourite_team if available
3. urgency = true only if there is an upcoming match within 72 hours
4. NEVER return target_child_agent — that is the Orchestrator's field
5. tone must be warm and re-engaging — fan has drifted, not churned
"""


# ── Main RecommendationAgent Runner ──────────────────────────────────────────
# Input:  fan_context dict assembled by Orchestrator
# Output: offer dict returned to Orchestrator
def run_recommendation_agent(fan_context: dict) -> dict:
    fan_id = fan_context.get("fan_id", "UNKNOWN")
    print(f"\n▶ RecommendationAgent processing: {fan_id}")
    print(f"  📦 Context received: {json.dumps(fan_context, indent=2)}")

    # Create a new thread for this fan
    thread = agents_client.threads.create()
    print(f"  📋 Thread: {thread.id}")

    # Send FanContext as the user message — this is ALL the agent sees
    agents_client.messages.create(
        thread_id=thread.id,
        role="user",
        content=(
            f"Generate a re-activation recommendation for this inactive fan.\n\n"
            f"FanContext:\n{json.dumps(fan_context, indent=2)}"
        )
    )

    # Start run — no tools, pure LLM
    run = agents_client.runs.create(
        thread_id=thread.id,
        agent_id=RECOMMENDATION_AGENT_ID
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
        print(f"\n✅ RecommendationAgent decision:\n{response_text}")

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
