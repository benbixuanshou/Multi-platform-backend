"""HookPipeline — cross-cutting logic injection (Harness Module 5)."""

from dataclasses import dataclass, field


@dataclass
class HookContext:
    task: dict
    compressed: bool = False
    warnings: list[str] = field(default_factory=list)
    budget_remaining: int = 0


class HookPipeline:
    def __init__(self):
        self._hooks: dict[str, list] = {
            "pre_model": [],
            "post_model": [],
            "pre_tool": [],
            "post_tool": [],
            "on_error": [],
        }

    def register(self, phase: str, hook):
        self._hooks[phase].append(hook)

    async def run(self, phase: str, ctx: HookContext):
        for hook in self._hooks[phase]:
            await hook(ctx)
