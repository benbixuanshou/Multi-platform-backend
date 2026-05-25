"""ClassifyRouterAgent — classify comment + intent + route to downstream tasks."""

from agents.base import BaseAgent


class ClassifyRouterAgent(BaseAgent):
    """Classify a comment into category + intent + sentiment + urgency.

    If confidence is high → update comment + create downstream task (reply/insight/spam-end).
    If confidence is low → mark pending_manual_review.
    On failure → fallback to rule engine.
    """

    async def build_prompt(self, task: dict) -> list[dict]:
        # TODO: assemble classify prompt with comment + post context + parent comment
        ...

    async def parse_response(self, content: str) -> dict:
        # TODO: parse classification JSON (category, intent, intent_detail, sentiment, urgency, needs_reply, suggested_tone, key_points, reasoning, confidence)
        ...
