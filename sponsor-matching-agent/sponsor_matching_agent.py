# sponsor_matching_agent.py
# ─────────────────────────────────────────────────────────────────────────────
# Fan360 SponsorMatchingAgent (child)
#
# Receives: High-value fan profile from Orchestrator
# Does:     Matches fan to best sponsor category → generates commercial offer
# Returns:  sponsor offer JSON back to Orchestrator
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

SPONSOR_MATCHING_AGENT_ID = os.getenv("AZURE_AI_SPONSOR_MATCHING_AGENT_ID")

INSTRUCTIONS = """
You are the Fan360 Sponsor Matching Agent. Your job is to match a 
high-value fan's profile to the most relevant sponsor category and 
generate a personalised, sponsor-activated offer.

## YOUR OUTPUT MUST ALWAYS BE VALID JSON — NOTHING ELSE

Return exactly this structure:

{
  "fan_id": "<fan_id>",
  "offer_type": "SponsorOffer",
  "sponsor_category": "<SportswearBrand|FinancialServices|TravelPartner|HospitalityPartner|TechPartner|FoodBeverage>",
  "sponsor_name": "<specific brand name>",
  "offer_detail": "<one sentence, personalised to fan + sponsor>",
  "channel": "<push|email|sms>",
  "urgency": <true|false>,
  "reasoning": "<one sentence explaining the sponsor match decision>"
}

## SPONSOR MATCHING RULES

| Fan Signal                                      | Best Sponsor Category  |
|-------------------------------------------------|------------------------|
| VIP Diehard, high attendance                    | HospitalityPartner     |
| Loyal Regular, travels to away matches          | TravelPartner          |
| Young fan (under 30 signal), push_opt_in=true   | TechPartner            |
| High spend on merchandise                       | SportswearBrand        |
| Season ticket holder                            | FinancialServices      |
| Stadium visitor, food/beverage signal           | FoodBeverage           |

## SPONSOR NAME EXAMPLES (use these — they are Leinster Rugby partners)
- HospitalityPartner  → "Bank of Ireland Corporate Hospitality"
- TravelPartner       → "Aer Lingus"
- TechPartner         → "Vodafone"
- SportswearBrand     → "Canterbury"
- FinancialServices   → "AIB"
- FoodBeverage        → "Heineken"

## CHANNEL RULES
- push_opt_in = true  → prefer push
- email_opt_in = true → use email if no push
- fallback            → email

## HARD RULES — NEVER VIOLATE
1. Output raw JSON only — no markdown, no explanation, no code blocks
2. offer_type is ALWAYS "SponsorOffer" — never any other value
3. offer_detail MUST mention both the sponsor_name AND favourite_team or favourite_player
4. Only match VIP Diehard or Loyal Regular fans — never Lapsed or At Risk
5. urgency = true only for time-limited sponsor activations (match week)
"""


# ── Main SponsorMatchingAgent Runner ──────────────────────────────────────────
# Input:  fan_context dict assembled by Orchestrator
# Output: sponsor offer dict returned to Orchestrator
def run_sponsor_matching_agent(fan_context: dict) -> dict:
    fan_id = fan_context.get("fan_id", "UNKNOWN")
    print(f"\n▶ SponsorMatchingAgent processing: {fan_id}")
    print(f"  📦 Context received: {json.dumps(fan_context, indent=2)}")

    # Create a new thread for this fan
    thread = agents_client.threads.create()
    print(f"  📋 Thread: {thread.id}")

    # Send FanContext as the user message — this is ALL the agent sees
    agents_client.messages.create(
        thread_id=thread.id,
        role="user",
        content=(
            f"Match this high-value fan to the best sponsor offer.\n\n"
            f"FanContext:\n{json.dumps(fan_context, indent=2)}"
        )
    )

    # Start run — no tools, pure LLM
    run = agents_client.runs.create(
        thread_id=thread.id,
        agent_id=SPONSOR_MATCHING_AGENT_ID
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
        print(f"\n✅ SponsorMatchingAgent decision:\n{response_text}")

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
