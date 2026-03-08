# autogen_agents.py
# ─────────────────────────────────────────────────────────────────────────────
# Fan360 AutoGen A2A Dispatch Layer
#
# Wraps each child agent function as a formal AutoGen BaseChatAgent.
# Provides a2a_dispatch() — single-function routing replacing if/elif.
# Uses AutoGen 0.4+ agent-to-agent message passing.
# ─────────────────────────────────────────────────────────────────────────────

import os
import sys
import json
import asyncio
import concurrent.futures
from typing import Sequence, List, Type

from autogen_agentchat.agents import BaseChatAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import BaseChatMessage, TextMessage
from autogen_core import CancellationToken

# ── Import existing child agent runner functions ──────────────────────────────
_base = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(_base, '..', 'churn-agent'))
sys.path.insert(0, os.path.join(_base, '..', 'personalisation-agent'))
sys.path.insert(0, os.path.join(_base, '..', 'recommendation-agent'))
sys.path.insert(0, os.path.join(_base, '..', 'segmentation-agent'))
sys.path.insert(0, os.path.join(_base, '..', 'sponsor-matching-agent'))

from churn_agent import run_churn_agent
from personalisation_agent import run_personalisation_agent
from recommendation_agent import run_recommendation_agent
from segmentation_agent import run_segmentation_agent
from sponsor_matching_agent import run_sponsor_matching_agent

# Live event stream — push_event() sends SSE to Control Room UI
from event_bus import push_event


# ── FunctionWrapperAgent ──────────────────────────────────────────────────────
# Wraps a synchronous child-agent function as an AutoGen BaseChatAgent.
# No extra LLM call — the inner function already uses Azure AI Agent Service.
class FunctionWrapperAgent(BaseChatAgent):
    """
    AutoGen agent that delegates to an existing synchronous function.
    Message in  → JSON fan_context
    Message out → JSON child result
    """

    def __init__(self, name: str, description: str, func):
        super().__init__(name=name, description=description)
        self._func = func

    @property
    def produced_message_types(self) -> List[Type[BaseChatMessage]]:
        return [TextMessage]

    async def on_messages(
        self,
        messages: Sequence[BaseChatMessage],
        cancellation_token: CancellationToken,
    ) -> Response:
        # Last message contains the fan_context JSON
        payload = messages[-1].content
        fan_context = json.loads(payload)

        # Call the wrapped child-agent function (sync — runs in thread)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._func, fan_context)

        return Response(
            chat_message=TextMessage(
                content=json.dumps(result, default=str),
                source=self.name,
            )
        )

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        pass


# ── Agent Registry ────────────────────────────────────────────────────────────
AGENT_REGISTRY: dict[str, FunctionWrapperAgent] = {
    "ChurnAgent": FunctionWrapperAgent(
        name="ChurnAgent",
        description="Fan retention specialist — picks retention offers for high-churn fans",
        func=run_churn_agent,
    ),
    "PersonalisationAgent": FunctionWrapperAgent(
        name="PersonalisationAgent",
        description="Personalises offers, tone, and channel for individual fans",
        func=run_personalisation_agent,
    ),
    "RecommendationAgent": FunctionWrapperAgent(
        name="RecommendationAgent",
        description="Recommends engagement offers for inactive or low-engagement fans",
        func=run_recommendation_agent,
    ),
    "SegmentationAgent": FunctionWrapperAgent(
        name="SegmentationAgent",
        description="Classifies fans into segments and recommends next agent",
        func=run_segmentation_agent,
    ),
    "SponsorMatchingAgent": FunctionWrapperAgent(
        name="SponsorMatchingAgent",
        description="Matches high-value fans with sponsor offers",
        func=run_sponsor_matching_agent,
    ),
}


# ── A2A Dispatch ──────────────────────────────────────────────────────────────
def a2a_dispatch(target: str, fan_context: dict) -> dict:
    """
    Formal AutoGen A2A message-passing dispatch.
    Replaces the if/elif block in the orchestrator.

    Args:
        target:      Child agent name (e.g. "ChurnAgent")
        fan_context:  Dict with fan profile, segment, churn data, etc.

    Returns:
        Dict with the child agent's response (offer_type, offer_detail, etc.)
    """
    agent = AGENT_REGISTRY.get(target)
    if agent is None:
        return {"error": f"Unknown agent: {target}", "status": "not_found"}

    message = TextMessage(
        content=json.dumps(fan_context, default=str),
        source="orchestrator",
    )

    async def _run() -> dict:
        response = await agent.on_messages([message], CancellationToken())
        return json.loads(response.chat_message.content)

    print(f"  🤝 A2A dispatch: Orchestrator → {target} (AutoGen)")

    # Handle both standalone and event-loop contexts (e.g. FastAPI/uvicorn)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Already inside an event loop — run in a separate thread
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, _run())
            return future.result()
    else:
        return asyncio.run(_run())


# ── Chained A2A Dispatch ─────────────────────────────────────────────────────
def a2a_chain_dispatch(fan_id: str, fan_context: dict, event_type: str) -> dict:
    """
    Multi-agent chain via AutoGen A2A:
    SegmentationAgent → RecommendationAgent → PersonalisationAgent

    Each agent's output enriches the context for the next.
    """
    print(f"\n  🔗 CHAIN START (AutoGen A2A): {event_type} for {fan_id}")
    chain_result = {}

    # ── Step A: SegmentationAgent ─────────────────────────────────────────
    print(f"\n  🔗 Chain Step A → SegmentationAgent")
    push_event("A2A", "Chain Step A: Orchestrator → SegmentationAgent", "SegmentationAgent")
    seg = a2a_dispatch("SegmentationAgent", fan_context)
    chain_result["segmentation"] = seg
    fan_context["fan_segment"]   = seg.get("assigned_segment", fan_context.get("fan_segment"))
    fan_context["seg_confidence"] = seg.get("confidence")
    print(f"  ✅ Segment confirmed: {fan_context['fan_segment']} ({fan_context['seg_confidence']})")
    push_event("RESULT", f"SegmentationAgent: {fan_context['fan_segment']} ({fan_context['seg_confidence']})", "SegmentationAgent", seg)

    # ── Step B: RecommendationAgent ───────────────────────────────────────
    print(f"\n  🔗 Chain Step B → RecommendationAgent")
    push_event("A2A", "Chain Step B: Orchestrator → RecommendationAgent", "RecommendationAgent")
    rec = a2a_dispatch("RecommendationAgent", fan_context)
    chain_result["recommendation"] = rec
    fan_context["offer_hook"]      = rec.get("offer_detail")
    fan_context["offer_type_hint"] = rec.get("offer_type")
    print(f"  ✅ Offer hook: {fan_context['offer_hook']}")
    push_event("RESULT", f"RecommendationAgent: {fan_context.get('offer_hook', 'offer')}", "RecommendationAgent", rec)

    # ── Step C: PersonalisationAgent ──────────────────────────────────────
    print(f"\n  🔗 Chain Step C → PersonalisationAgent")
    push_event("A2A", "Chain Step C: Orchestrator → PersonalisationAgent", "PersonalisationAgent")
    pers = a2a_dispatch("PersonalisationAgent", fan_context)
    chain_result["personalisation"] = pers
    push_event("RESULT", f"PersonalisationAgent: {pers.get('offer_detail', 'personalised')}", "PersonalisationAgent", pers)

    print(f"\n  🔗 CHAIN COMPLETE (AutoGen A2A) for {fan_id}")
    return chain_result
