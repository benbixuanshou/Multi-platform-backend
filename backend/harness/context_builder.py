"""ContextBuilder — three-layer context assembly (Harness Module 1)."""


class ContextBuilder:
    def __init__(self, max_tokens: int = 4000):
        self.max_tokens = max_tokens

    def build(self, static: dict, dynamic: dict) -> dict:
        """Assemble context from static (cached) + dynamic (per-request) layers."""
        context = {**static, **dynamic}
        return self.fit_to_budget(context)

    def fit_to_budget(self, context: dict) -> dict:
        """Tiered compression: summarize P2 first, then P1, then hard truncate."""
        # TODO: implement token counting + tiered compression
        return context
