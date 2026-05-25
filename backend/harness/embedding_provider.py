"""EmbeddingProvider — replaceable embedding abstraction (same pattern as ModelProvider)."""

import asyncio
from abc import ABC, abstractmethod

import torch
from transformers import AutoTokenizer, AutoModel


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...

    @abstractmethod
    def dim(self) -> int:
        ...


class LocalEmbeddingProvider(EmbeddingProvider):
    """bge-large-zh-v1.5 via HuggingFace transformers — free, best Chinese support, 1024-dim.

    Uses direct transformers API (not FlagEmbedding/sentence-transformers) because those
    wrappers have segfault issues on some Windows machines.
    """

    def __init__(self, model_name: str = "BAAI/bge-large-zh-v1.5"):
        self._tokenizer = AutoTokenizer.from_pretrained(model_name)
        self._model = AutoModel.from_pretrained(model_name)
        self._model.eval()
        self._dim = 1024

    def _mean_pooling(self, model_output, attention_mask):
        """Mean pooling — take attention mask into account for correct averaging."""
        token_embeddings = model_output[0]
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(
            input_mask_expanded.sum(1), min=1e-9
        )

    async def embed(self, text: str) -> list[float]:
        return await self.embed_batch([text])[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        encoded = self._tokenizer(
            texts, padding=True, truncation=True, return_tensors="pt", max_length=512,
        )
        with torch.no_grad():
            model_output = self._model(**encoded)
            embeddings = self._mean_pooling(model_output, encoded["attention_mask"])
            embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
        return embeddings.tolist()

    def dim(self) -> int:
        return self._dim
