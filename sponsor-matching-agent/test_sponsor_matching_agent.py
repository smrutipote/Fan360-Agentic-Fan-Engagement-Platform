from sponsor_matching_agent import run_sponsor_matching_agent
import json

# VIP Diehard — high attendance, season ticket signal
fan_context = {
    "fan_id":            "FAN-vip99001",
    "fan_segment":       "VIP Diehard",
    "favourite_player":  "Jamison Gibson-Park",
    "favourite_team":    "Leinster",
    "push_opt_in":       True,
    "email_opt_in":      True,
    "last_contact_date": "2026-02-20",
    "churn_score":       0.12
}

result = run_sponsor_matching_agent(fan_context)

print("\n🎯 RESULT:")
print(json.dumps(result, indent=2))
