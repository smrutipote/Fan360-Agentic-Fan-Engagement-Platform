# test_sk_plugins.py — verify all 5 SK plugins resolve correctly
import asyncio
from semantic_kernel import Kernel
from sk_plugins import FabricMCPPlugin, EngagementLogPlugin

async def test():
    kernel = Kernel()
    kernel.add_plugin(FabricMCPPlugin(),     plugin_name="FabricMCP")
    kernel.add_plugin(EngagementLogPlugin(), plugin_name="EngagementLog")

    fan_id = "FAN-d65867e0"

    # Invoke each plugin by name — exactly as SK kernel would call them
    profile  = await kernel.invoke(kernel.plugins["FabricMCP"]["get_fan_profile"],  fan_id=fan_id)
    segment  = await kernel.invoke(kernel.plugins["FabricMCP"]["get_fan_segment"],  fan_id=fan_id)
    churn    = await kernel.invoke(kernel.plugins["FabricMCP"]["get_churn_score"],  fan_id=fan_id)
    contact  = await kernel.invoke(kernel.plugins["FabricMCP"]["get_last_contact"], fan_id=fan_id)

    print("✅ get_fan_profile:  ", str(profile)[:120])
    print("✅ get_fan_segment:  ", str(segment)[:120])
    print("✅ get_churn_score:  ", str(churn)[:120])
    print("✅ get_last_contact: ", str(contact)[:120])

    # Test log_action plugin
    log = await kernel.invoke(
        kernel.plugins["EngagementLog"]["log_action"],
        fan_id="FAN-d65867e0",
        offer_type="ExclusiveExperience",
        agent_name="ChurnAgent",
        channel="push",
        reasoning="VIP Diehard with null churn score — HIGH risk retention offer"
    )
    print("✅ log_action:       ", str(log))

asyncio.run(test())
