# sk_plugins.py
# ─────────────────────────────────────────────────────────────────────────────
# Formal Semantic Kernel plugins wrapping all DAB/MCP tool calls
# Orchestrator uses these instead of raw requests.get() calls
# ─────────────────────────────────────────────────────────────────────────────

import os, json, requests
from typing import Annotated
from semantic_kernel.functions import kernel_function


class FabricMCPPlugin:
    """
    SK Plugin — wraps all Gold table reads via DAB (MCP layer).
    Each method is a named, typed, discoverable tool for the SK kernel.
    """

    def __init__(self, dab_base_url: str = None):
        self.base = dab_base_url or os.environ.get("DAB_BASE_URL", "http://localhost:5000")

    # ── Tool 1: Fan Profile ───────────────────────────────────────────
    @kernel_function(
        name="get_fan_profile",
        description="Get full fan profile from gold_dim_fan. Returns age, location, preferences, opt-ins."
    )
    def get_fan_profile(
        self,
        fan_id: Annotated[str, "The fan's unique ID e.g. FAN-d65867e0"]
    ) -> Annotated[str, "JSON fan profile or empty"]:
        resp = requests.get(
            f"{self.base}/api/gold_dim_fan",
            params={"$filter": f"fan_id eq '{fan_id}'", "$first": 1}
        )
        data = resp.json().get("value", [])
        return json.dumps(data[0]) if data else json.dumps({})

    # ── Tool 2: Fan Segment ───────────────────────────────────────────
    @kernel_function(
        name="get_fan_segment",
        description="Get fan segment label from gold_fan_segments. Returns VIP Diehard, Casual Fan etc."
    )
    def get_fan_segment(
        self,
        fan_id: Annotated[str, "The fan's unique ID"]
    ) -> Annotated[str, "JSON segment record or empty"]:
        resp = requests.get(
            f"{self.base}/api/gold_fan_segments",
            params={"$filter": f"fan_id eq '{fan_id}'", "$first": 1}
        )
        data = resp.json().get("value", [])
        return json.dumps(data[0]) if data else json.dumps({})

    # ── Tool 3: Churn Score ───────────────────────────────────────────
    @kernel_function(
        name="get_churn_score",
        description="Get churn risk score from gold_churn_score. Score near 0 = high churn risk."
    )
    def get_churn_score(
        self,
        fan_id: Annotated[str, "The fan's unique ID"]
    ) -> Annotated[str, "JSON churn score record or empty"]:
        resp = requests.get(
            f"{self.base}/api/gold_churn_score",
            params={"$filter": f"fan_id eq '{fan_id}'", "$first": 1}
        )
        data = resp.json().get("value", [])
        return json.dumps(data[0]) if data else json.dumps({})

    # ── Tool 4: Last Contact ──────────────────────────────────────────
    @kernel_function(
        name="get_last_contact",
        description="Get most recent engagement record from gold_fact_engagement. Used for suppress/dedup logic."
    )
    def get_last_contact(
        self,
        fan_id: Annotated[str, "The fan's unique ID"]
    ) -> Annotated[str, "JSON last engagement record or empty"]:
        resp = requests.get(
            f"{self.base}/api/gold_fact_engagement",
            params={
                "$filter":  f"fan_id eq '{fan_id}'",
                "$orderby": "event_timestamp desc",
                "$first":     1
            }
        )
        data = resp.json().get("value", [])
        return json.dumps(data[0]) if data else json.dumps({})

    # ── Tool 5: Sponsor Audiences ─────────────────────────────────────
    @kernel_function(
        name="get_sponsor_audiences",
        description="Get GDPR-safe sponsor audience segments from gold_sponsor_audiences."
    )
    def get_sponsor_audiences(
        self,
        segment: Annotated[str, "Fan segment name e.g. VIP Diehard"]
    ) -> Annotated[str, "JSON sponsor audience record or empty"]:
        resp = requests.get(
            f"{self.base}/api/gold_sponsor_audiences",
            params={"$filter": f"segment_name eq '{segment}'", "$first": 5}
        )
        data = resp.json().get("value", [])
        return json.dumps(data)


class EngagementLogPlugin:
    """
    SK Plugin — wraps the write-back action to gold_fact_engagement.
    Separate from FabricMCPPlugin to mirror the doc's log_action() separation.
    """

    @kernel_function(
        name="log_action",
        description="Write an AGENT_ACTION result back to gold_fact_engagement via OneLake."
    )
    def log_action(
        self,
        fan_id:     Annotated[str, "Fan ID"],
        offer_type: Annotated[str, "Offer type returned by child agent"],
        agent_name: Annotated[str, "Name of child agent that acted"],
        channel:    Annotated[str, "Delivery channel: push, email, sms"],
        reasoning:  Annotated[str, "One-sentence reasoning from child agent"]
    ) -> Annotated[str, "Confirmation string"]:
        import uuid
        from datetime import datetime, timezone

        record = {
            "engagement_id":   str(uuid.uuid4()),
            "fan_id":          fan_id,
            "event_type":      "AGENT_ACTION",
            "event_timestamp": datetime.now(timezone.utc).isoformat(),
            "offer_type":      offer_type,
            "agent_name":      agent_name,
            "channel":         channel,
            "reasoning":       reasoning
        }

        # Write to OneLake via Fabric REST API
        token        = os.environ.get("FABRIC_BEARER_TOKEN")
        workspace_id = os.environ.get("FABRIC_WORKSPACE_ID")
        lakehouse_id = os.environ.get("FABRIC_LAKEHOUSE_ID")

        if all([token, workspace_id, lakehouse_id]):
            url = (
                f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}"
                f"/lakehouses/{lakehouse_id}/tables/gold_fact_engagement/rows"
            )
            requests.post(url,
                json={"rows": [record]},
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            )

        return f"✅ Action logged: {agent_name} → {offer_type} for {fan_id}"
