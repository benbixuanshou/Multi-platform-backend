"""ReplyCriticAgent — evaluates ReplyGenerateAgent output quality (Harness Module 3: Generator→Critic→Generator)."""

from agents.base import BaseAgent


class ReplyCriticAgent(BaseAgent):
    """Evaluate reply drafts and recommend: all_good / review_recommended / needs_regeneration.

    If needs_regeneration, provides a regeneration_hint that feeds back to ReplyGenerateAgent.
    Maximum 1 regeneration cycle per comment.
    """

    async def build_prompt(self, task: dict) -> list[dict]:
        # TODO: assemble critic prompt with comment + drafts + creator persona
        ...

    async def parse_response(self, content: str) -> dict:
        # TODO: parse evaluation JSON, return recommendation
        ...
