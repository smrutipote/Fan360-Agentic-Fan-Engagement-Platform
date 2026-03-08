from dotenv import load_dotenv
load_dotenv()
from orchestrator import get_fan_profile, get_last_contact, get_fan_segment, get_churn_score

FAN = "FAN-d65867e0"

print("--- Step 1: Fan Profile ---")
print(get_fan_profile(FAN))

print("\n--- Step 2: Last Contact ---")
print(get_last_contact(FAN))

print("\n--- Step 3: Fan Segment ---")
print(get_fan_segment(FAN))

print("\n--- Step 4: Churn Score ---")
print(get_churn_score(FAN))
