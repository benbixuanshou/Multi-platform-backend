"""EmbeddingProvider — replaceable embedding abstraction (same pattern as ModelProvider)."""

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Return embedding vector for a single text string."""
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...

    @abstractmethod
    def dim(self) -> int:
        """Return embedding dimension (1024 for bge-large-zh)."""
        ...


class LocalEmbeddingProvider(EmbeddingProvider):
    """bge-large-zh via FlagEmbedding — free, best Chinese support."""

    def __init__(self, model_name: str = "BAAI/bge-large-zh-v1.5"):
        from FlagEmbedding import FlagModel
        self._model = FlagModel(model_name, query_instruction_for_retrieval="为这个句子生成向量")
        self._dim = 1024

    async def embed(self, text: str) -> list[float]:
        return self._model.encode(text).tolist()

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts).tolist()

    def dim(self) -> int:
        return self._dim
