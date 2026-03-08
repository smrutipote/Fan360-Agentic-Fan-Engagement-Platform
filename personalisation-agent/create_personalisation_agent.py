# One-time script — creates the PersonalisationAgent in Azure AI Foundry
import os
from dotenv import load_dotenv
from azure.identity import AzureCliCredential
from azure.ai.agents import AgentsClient
from personalisation_agent import INSTRUCTIONS

load_dotenv()

agents_client = AgentsClient(
    endpoint=os.getenv("AZURE_AI_FOUNDRY_ENDPOINT"),
    credential=AzureCliCredential()
)

agent = agents_client.create_agent(
    model=os.getenv("AZURE_AI_MODEL"),
    name="Fan360-PersonalisationAgent",
    instructions=INSTRUCTIONS
)

print(f"✅ PersonalisationAgent created: {agent.id}")
print(f"Add to .env:  AZURE_AI_PERSONALISATION_AGENT_ID={agent.id}")
