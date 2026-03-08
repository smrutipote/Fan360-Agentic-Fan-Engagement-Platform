# test_chain.py — tests multi-agent chaining for BirthdayEvent
from orchestrator import run_orchestrator
import json

payload = {
    "fan_id":         "FAN-d65867e0",
    "event_type":     "BirthdayEvent",
    "trigger_source": "FabricActivator",
    "context":        {}
}

print("=" * 60)
print("TEST: Multi-Agent Chain — BirthdayEvent")
print("=" * 60)

result = run_orchestrator(payload)

print("\n" + "=" * 60)
print("🎯 FULL CHAIN RESULT:")
print(json.dumps(result, indent=2, default=str))
