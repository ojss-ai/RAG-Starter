from dataclasses import dataclass
from typing import Protocol

from app.config import Settings


@dataclass(frozen=True)
class VectorItem:
    chunk_id: str
    document_id: str
    partition_key: str
    embedding: list[float]


@dataclass(frozen=True)
class VectorHit:
    chunk_id: str
    document_id: str
    score: float


class VectorStore(Protocol):
    async def ensure_ready(self) -> None: ...

    async def upsert(self, items: list[VectorItem]) -> None: ...

    async def delete_document(self, document_id: str) -> None: ...

    async def search(self, vector: list[float], top_k: int,
                     partition_key: str | None = None) -> list[VectorHit]: ...

    async def stats(self) -> dict: ...


def get_vector_store(settings: Settings) -> VectorStore:
    if settings.vector_backend == "memory":
        from app.vectorstore.memory import InMemoryVectorStore
        return InMemoryVectorStore()
    if settings.vector_backend == "milvus":
        from app.vectorstore.milvus import MilvusVectorStore
        return MilvusVectorStore(settings.milvus_uri, settings.milvus_collection,
                                 settings.embed_dim)
    raise ValueError(f"unknown vector backend: {settings.vector_backend}")
