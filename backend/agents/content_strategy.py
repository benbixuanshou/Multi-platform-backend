"""ContentStrategyAgent — converts InsightMining output into actionable recommendations."""

from agents.base import BaseAgent


class ContentStrategyAgent(BaseAgent):
    """Consume InsightMiningAgent output and produce content ideas, community actions,
    business opportunities, and risk alerts for the creator.

    Runs weekly (offline, not in real-time pipeline).
    """

    async def build_prompt(self, task: dict) -> list[dict]:
        # TODO: assemble strategy prompt with insight_report + performance data
        ...

    async def parse_response(self, content: str) -> dict:
        # TODO: parse strategy JSON
        ...
