"""ToolRegistry — centralized tool registration (Harness Module 2)."""

from dataclasses import dataclass


@dataclass
class Tool:
    name: str
    description: str
    readonly: bool
    timeout_seconds: int

    async def execute(self, **params) -> dict:
        raise NotImplementedError


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    async def execute(self, name: str, **params) -> dict:
        tool = self.get(name)
        if tool is None:
            raise KeyError(f"Tool '{name}' not found")
        return await tool.execute(**params)
