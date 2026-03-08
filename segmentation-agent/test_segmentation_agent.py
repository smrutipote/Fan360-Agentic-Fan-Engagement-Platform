from segmentation_agent import run_segmentation_agent
import json

# Fan with unknown segment — mixed signals
fan_context = {
    "fan_id":            "FAN-unknown01",
    "fan_segment":       "Unknown",
    "favourite_player":  "Jamison Gibson-Park",
    "favourite_team":    "Leinster",
    "push_opt_in":       True,
    "email_opt_in":      True,
    "last_contact_date": "2025-11-01",   # ~126 days ago → Lapsed
    "churn_score":       0.82
}

result = run_segmentation_agent(fan_context)

print("\n🎯 RESULT:")
print(json.dumps(result, indent=2))
