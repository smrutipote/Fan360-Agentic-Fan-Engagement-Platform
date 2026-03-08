# test_orchestrator.py
# Full end-to-end test — Orchestrator → Child Agents → write-back
from orchestrator import run_orchestrator
import json

# Fan 1: HIGH churn risk → should route to ChurnAgent
fan1 = {
    "fan_id":         "FAN-d65867e0",
    "event_type":     "ChurnDrop",
    "trigger_source": "FabricActivator",
    "context":        {}
}

# Fan 2: LOW churn risk, active → should route to PersonalisationAgent
fan2 = {
    "fan_id":         "FAN-5b86fccb",
    "event_type":     "EngagementOpportunity",
    "trigger_source": "FabricActivator",
    "context":        {}
}

for fan in [fan1, fan2]:
    print("\n" + "=" * 60)
    print(f"TEST: {fan['fan_id']} / {fan['event_type']}")
    print("=" * 60)
    result = run_orchestrator(fan)
    print("\n🎯 FULL RESULT:")
    print(json.dumps(result, indent=2, default=str))