# test_churn_agent.py
# Tests ChurnAgent in isolation — simulates what Orchestrator passes
from churn_agent import run_churn_agent

# Exact FanContext the Orchestrator assembled for FAN-d65867e0
fan_context = {
    "fan_id":                  "FAN-d65867e0",
    "fan_segment":             "VIP Diehard",
    "fan_email":               "aoife.brennan36@outlook.com",
    "marketing_opt_in":        True,
    "push_opt_in":             True,
    "churn_score":             None,
    "days_since_app":          None,
    "days_since_purchase":     None,
    "is_season_ticket_holder": False,
    "total_ticket_spend_eur":  0.0,
    "favourite_player":        "Jamison Gibson-Park",
    "device_type":             "ANDROID"
}

result = run_churn_agent(fan_context)
print("\n🎯 Final offer:", result)
