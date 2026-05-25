"""InsightMiningAgent — batch analyze comments for trends, UGC gold, fan insights."""

from agents.base import BaseAgent


class InsightMiningAgent(BaseAgent):
    """Analyze a batch of comments to extract: sentiment trends, hot topics, emerging trends,
    fan concerns, UGC gold, core fans, content suggestions, unreplied priorities.

    Runs offline every 6 hours or on manual trigger.
    Uses rule-engine aggregation layer (TF-IDF + grouping) before LLM analysis.
    Output consumed by ContentStrategyAgent.
    """

    async def build_prompt(self, task: dict) -> list[dict]:
        # TODO: assemble insight prompt with aggregated stats + top 20 comments + summary
        ...

    async def parse_response(self, content: str) -> dict:
        # TODO: parse insight JSON
        ...
