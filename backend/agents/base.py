"""BaseAgent — agent-specific logic only (delegates harness to components)."""

from dataclasses import dataclass

from harness.hook_pipeline import HookPipeline
from harness.model_provider import ModelProvider
from harness.tool_registry import ToolRegistry
from harness.context_builder import ContextBuilder


@dataclass
class AgentConfig:
    agent_name: str
    provider: str
    model: str
    timeout_seconds: int = 30
    max_retries: int = 3


class BaseAgent:
    def __init__(
        self,
        config: AgentConfig,
        model: ModelProvider,
        tools: ToolRegistry,
        hooks: HookPipeline,
        context_builder: ContextBuilder,
    ):
        self.config = config
        self.model = model
        self.tools = tools
        self.hooks = hooks
        self.context = context_builder

    async def build_prompt(self, task: dict) -> list[dict]:
        """Override in subclass — agent-specific prompt assembly."""
        raise NotImplementedError

    async def parse_response(self, content: str) -> dict:
        """Override in subclass — agent-specific output parsing."""
        raise NotImplementedError
