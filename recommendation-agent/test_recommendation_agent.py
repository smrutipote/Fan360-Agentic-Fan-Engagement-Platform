# test_recommendation_agent.py
# Isolation test — RecommendationAgent only
from recommendation_agent import run_recommendation_agent
import json

# Inactive fan — last contact 77 days ago, has favourite team
fan_context = {
    "fan_id":            "FAN-inactive01",
    "fan_segment":       "Lapsed Fan",
    "favourite_player":  "Jamison Gibson-Park",
    "favourite_team":    "Leinster",
    "push_opt_in":       False,
    "email_opt_in":      True,
    "last_contact_date": "2025-12-20",
    "churn_score":       0.71
}

print("=" * 60)
print("TEST: RecommendationAgent isolation")
print("=" * 60)

result = run_recommendation_agent(fan_context)

print("\n" + "=" * 60)
print("🎯 RESULT:")
print(json.dumps(result, indent=2, default=str))
