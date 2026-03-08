# churn_agent.py
# ─────────────────────────────────────────────────────────────────────────────
# Fan360 ChurnAgent
#
# Receives: FanContext payload from Orchestrator
# Does:     LLM reasons over context → picks retention offer
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

CHURN_AGENT_ID = os.getenv("AZURE_AI_AGENT_ID")


# ── Main ChurnAgent Runner ────────────────────────────────────────────────────
# Input:  fan_context dict assembled by Orchestrator
# Output: offer dict returned to Orchestrator
def run_churn_agent(fan_context: dict) -> dict:
    fan_id = fan_context.get("fan_id")
    print(f"\n▶ ChurnAgent processing: {fan_id}")
    print(f"  📦 Context received: {json.dumps(fan_context, indent=2)}")

    # Create a new thread for this fan
    thread = agents_client.threads.create()
    print(f"  📋 Thread: {thread.id}")

    # Send FanContext as the user message — this is ALL the agent sees
    agents_client.messages.create(
        thread_id=thread.id,
        role="user",
        content=(
            f"Please decide the retention offer for this fan.\n\n"
            f"FanContext:\n{json.dumps(fan_context, indent=2)}"
        )
    )

    # Start run — no tools, pure LLM
    run = agents_client.runs.create(
        thread_id=thread.id,
        agent_id=CHURN_AGENT_ID
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
        print(f"\n✅ ChurnAgent decision:\n{response_text}")

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
