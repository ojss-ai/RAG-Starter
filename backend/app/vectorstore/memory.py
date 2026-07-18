import math

from app.vectorstore import VectorHit, VectorItem


class InMemoryVectorStore:
    """Cosine-similarity store for dev/tests. API-identical to the Milvus gateway."""

    def __init__(self):
        self._items: dict[str, VectorItem] = {}

    async def ensure_ready(self) -> None:
        return None

    async def upsert(self, items: list[VectorItem]) -> None:
        for it in items:
            self._items[it.chunk_id] = it

    async def delete_document(self, document_id: str) -> None:
        self._items = {cid: it for cid, it in self._items.items()
                       if it.document_id != document_id}

    async def search(self, vector: list[float], top_k: int,
                     partition_key: str | None = None) -> list[VectorHit]:
        def cos(a: list[float], b: list[float]) -> float:
            num = sum(x * y for x, y in zip(a, b))
            den = (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))) or 1.0
            return num / den

        pool = [it for it in self._items.values()
                if partition_key is None or it.partition_key == partition_key]
        scored = sorted(((cos(vector, it.embedding), it) for it in pool),
                        key=lambda t: t[0], reverse=True)[:top_k]
        return [VectorHit(chunk_id=it.chunk_id, document_id=it.document_id, score=s)
                for s, it in scored]

    async def stats(self) -> dict:
        return {"backend": "memory", "vectors": len(self._items)}
