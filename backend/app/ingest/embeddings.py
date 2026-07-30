import hashlib
import math
from typing import Protocol

import httpx

from app.config import Settings


class EmbeddingProvider(Protocol):
    dim: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class EmbeddingError(Exception):
    pass


class FakeEmbeddingProvider:
    """Deterministic, offline: hash n-grams into a fixed-dim unit vector. Similar texts
    share n-grams and therefore direction — good enough for relevance-shaped tests."""

    def __init__(self, dim: int = 32):
        self.dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        words = text.lower().split()
        for w in words:
            h = int.from_bytes(hashlib.sha256(w.encode()).digest()[:4], "big")
            vec[h % self.dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class OpenAIEmbeddingProvider:
    """OpenAI-compatible /embeddings endpoint, batched (FR-2)."""

    def __init__(self, api_base: str, api_key: str, model: str, dim: int, batch: int = 64,
                 client: httpx.AsyncClient | None = None):
        self.dim = dim
        self._model = model
        self._batch = batch
        self._client = client or httpx.AsyncClient(
            base_url=api_base, headers={"Authorization": f"Bearer {api_key}"}, timeout=60)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self._batch):
            batch = texts[i:i + self._batch]
            try:
                r = await self._client.post("/embeddings",
                                            json={"model": self._model, "input": batch})
                r.raise_for_status()
            except httpx.HTTPError as exc:
                raise EmbeddingError(str(exc)) from exc
            data = r.json()["data"]
            out.extend(item["embedding"] for item in sorted(data, key=lambda d: d["index"]))
        return out


def get_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embed_provider == "fake":
        return FakeEmbeddingProvider(dim=settings.embed_dim)
    if settings.embed_provider == "openai":
        return OpenAIEmbeddingProvider(settings.embed_api_base, settings.embed_api_key,
                                       settings.embed_model, settings.embed_dim,
                                       settings.embed_batch)
    raise ValueError(f"unknown embed provider: {settings.embed_provider}")
