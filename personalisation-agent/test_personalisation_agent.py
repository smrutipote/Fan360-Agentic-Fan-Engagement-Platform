# test_personalisation_agent.py
# Isolation test — PersonalisationAgent only
from personalisation_agent import run_personalisation_agent
import json

# Simulate the fan_context the Orchestrator would pass
fan_context = {
    "fan_id": "FAN-d65867e0",
    "fan_segment": "VIP Diehard",
    "favourite_player": "Johnny Sexton",
    "favourite_team": "Leinster",
    "push_opt_in": True,
    "email_opt_in": True,
    "last_contact_date": None,
    "churn_score": 0.3
}

print("=" * 60)
print("TEST: PersonalisationAgent isolation")
print("=" * 60)

result = run_personalisation_agent(fan_context)

print("\n" + "=" * 60)
print("🎯 RESULT:")
print(json.dumps(result, indent=2, default=str))
