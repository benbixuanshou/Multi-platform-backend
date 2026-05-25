"""ReplyGenerateAgent — generate 3-style reply drafts matching creator persona."""

from agents.base import BaseAgent


class ReplyGenerateAgent(BaseAgent):
    """Generate 3 reply drafts (warm / casual / professional) based on comment content,
    creator persona, post context, user history, and similar reply patterns.

    Output goes to ReplyCriticAgent before reaching the creator.
    If Critic says needs_regeneration → regenerate once with the critic's hint.
    """

    async def build_prompt(self, task: dict) -> list[dict]:
        # TODO: assemble reply prompt with comment + classification + intent + creator persona
        #       + post context + user history + similar replies + edit log patterns
        ...

    async def parse_response(self, content: str) -> dict:
        # TODO: parse 3 drafts JSON (style, content, recommended, reasoning, risk_warning)
        ...
