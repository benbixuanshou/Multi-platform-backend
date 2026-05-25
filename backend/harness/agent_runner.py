"""AgentRunner — orchestration template method (Harness Module 3)."""

from .hook_pipeline import HookPipeline, HookContext


class AgentRunner:
    """observe → plan → act → verify → output"""

    def __init__(self, hooks: HookPipeline):
        self.hooks = hooks

    async def run(self, task: dict) -> dict:
        ctx = HookContext(task=task)
        try:
            await self.hooks.run("pre_model", ctx)
            result = await self._execute(task)
            await self.hooks.run("post_model", ctx)
            return result
        except Exception:
            await self.hooks.run("on_error", ctx)
            raise

    async def _execute(self, task: dict) -> dict:
        raise NotImplementedError
