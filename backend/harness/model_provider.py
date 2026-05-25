"""ModelProvider — replaceable model abstraction (Harness Module 2)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ModelResponse:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    duration_ms: int


class ModelProvider(ABC):
    @abstractmethod
    async def chat(self, messages: list[dict], **kwargs) -> ModelResponse:
        ...

    @abstractmethod
    def count_tokens(self, messages: list[dict]) -> int:
        ...
