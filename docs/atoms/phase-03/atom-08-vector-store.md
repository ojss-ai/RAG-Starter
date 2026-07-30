# atom-08-vector-store

- Status: COMMITTED
- Phase: phase-03-ingestion (`docs/plans/phase-03-ingestion.md`, item §03.2)
- Traces: FR-3, NFR-1, NFR-3, NFR-8
- Depends on: atom-07
- Mode: normal
- Created: 2026-07-12

## Purpose

The vector-store boundary exists: a `VectorStore` protocol with `upsert / delete_document /
search / stats`, an in-memory cosine implementation for dev/tests, and the Milvus
implementation (lazy pymilvus import, HNSW `M=16, efConstruction=200`, partition-key field,
document UUID as scalar field — the FR-3 two-way mapping).

## Files

| Path | Action |
|---|---|
| `backend/app/vectorstore/__init__.py`, `memory.py`, `milvus.py` | create |
| `backend/tests/test_vectorstore.py` | create |

## Implementation

```python file=backend/app/vectorstore/__init__.py
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
```

```python file=backend/app/vectorstore/memory.py
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
```

```python file=backend/app/vectorstore/milvus.py
import asyncio

from app.vectorstore import VectorHit, VectorItem

_HNSW_PARAMS = {"M": 16, "efConstruction": 200}  # plan §3 / SRS NFR-1


class MilvusVectorStore:
    """Milvus gateway. pymilvus is imported lazily so environments without it (unit tests,
    memory backend) never pay for or require the dependency. All pymilvus calls are sync —
    they run in a worker thread to keep the event loop free."""

    def __init__(self, uri: str, collection: str, dim: int):
        self._uri = uri
        self._collection = collection
        self._dim = dim
        self._client = None

    def _get_client(self):
        if self._client is None:
            from pymilvus import MilvusClient  # lazy: see class docstring
            self._client = MilvusClient(uri=self._uri)
        return self._client

    async def ensure_ready(self) -> None:
        def _setup():
            from pymilvus import DataType
            client = self._get_client()
            if client.has_collection(self._collection):
                return
            schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
            schema.add_field("pk", DataType.INT64, is_primary=True)
            schema.add_field("chunk_id", DataType.VARCHAR, max_length=64)
            schema.add_field("document_id", DataType.VARCHAR, max_length=64)
            schema.add_field("partition_key", DataType.VARCHAR, max_length=128,
                             is_partition_key=True)  # plan §4: partitioned collections
            schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=self._dim)
            index_params = client.prepare_index_params()
            index_params.add_index(field_name="embedding", index_type="HNSW",
                                   metric_type="COSINE", params=_HNSW_PARAMS)
            client.create_collection(self._collection, schema=schema,
                                     index_params=index_params)
        await asyncio.to_thread(_setup)

    async def upsert(self, items: list[VectorItem]) -> None:
        rows = [{"chunk_id": it.chunk_id, "document_id": it.document_id,
                 "partition_key": it.partition_key, "embedding": it.embedding}
                for it in items]

        def _insert():
            self._get_client().insert(self._collection, rows)
        await asyncio.to_thread(_insert)

    async def delete_document(self, document_id: str) -> None:
        def _delete():
            self._get_client().delete(self._collection,
                                      filter=f'document_id == "{document_id}"')
        await asyncio.to_thread(_delete)

    async def search(self, vector: list[float], top_k: int,
                     partition_key: str | None = None) -> list[VectorHit]:
        def _search():
            kwargs = dict(collection_name=self._collection, data=[vector], limit=top_k,
                          output_fields=["chunk_id", "document_id"])
            if partition_key is not None:
                kwargs["filter"] = f'partition_key == "{partition_key}"'
            return self._get_client().search(**kwargs)
        results = await asyncio.to_thread(_search)
        hits = results[0] if results else []
        return [VectorHit(chunk_id=h["entity"]["chunk_id"],
                          document_id=h["entity"]["document_id"],
                          score=float(h["distance"])) for h in hits]

    async def stats(self) -> dict:
        def _stats():
            client = self._get_client()
            res = client.get_collection_stats(self._collection)
            return int(res.get("row_count", 0))
        return {"backend": "milvus", "vectors": await asyncio.to_thread(_stats)}
```

## Tests (normal mode: must exist before validate)

```python file=backend/tests/test_vectorstore.py
import pytest

from app.config import Settings
from app.vectorstore import VectorItem, get_vector_store
from app.vectorstore.memory import InMemoryVectorStore


def _item(cid, did, vec, pk="default"):
    return VectorItem(chunk_id=cid, document_id=did, partition_key=pk, embedding=vec)


@pytest.fixture
def store():
    return InMemoryVectorStore()


async def test_upsert_search_relevance(store):
    await store.upsert([
        _item("c1", "d1", [1.0, 0.0, 0.0]),
        _item("c2", "d1", [0.0, 1.0, 0.0]),
        _item("c3", "d2", [0.9, 0.1, 0.0]),
    ])
    hits = await store.search([1.0, 0.0, 0.0], top_k=2)
    assert [h.chunk_id for h in hits] == ["c1", "c3"]
    assert hits[0].score > hits[1].score
    assert hits[0].document_id == "d1"


async def test_partition_filter(store):
    await store.upsert([
        _item("c1", "d1", [1.0, 0.0], pk="tenant-a"),
        _item("c2", "d2", [1.0, 0.0], pk="tenant-b"),
    ])
    hits = await store.search([1.0, 0.0], top_k=10, partition_key="tenant-a")
    assert [h.chunk_id for h in hits] == ["c1"]


async def test_delete_document_removes_all_its_vectors(store):
    await store.upsert([
        _item("c1", "d1", [1.0, 0.0]),
        _item("c2", "d1", [0.5, 0.5]),
        _item("c3", "d2", [0.0, 1.0]),
    ])
    await store.delete_document("d1")
    assert (await store.stats())["vectors"] == 1
    hits = await store.search([1.0, 0.0], top_k=10)
    assert {h.document_id for h in hits} == {"d2"}


async def test_upsert_overwrites_same_chunk(store):
    await store.upsert([_item("c1", "d1", [1.0, 0.0])])
    await store.upsert([_item("c1", "d1", [0.0, 1.0])])
    assert (await store.stats())["vectors"] == 1
    hits = await store.search([0.0, 1.0], top_k=1)
    assert hits[0].chunk_id == "c1"


def test_factory_selects_backend():
    s = Settings(database_url="sqlite+aiosqlite://", vector_backend="memory")
    assert isinstance(get_vector_store(s), InMemoryVectorStore)
    with pytest.raises(ValueError):
        get_vector_store(Settings(database_url="sqlite+aiosqlite://",
                                  vector_backend="nope"))


def test_milvus_import_is_lazy():
    """Constructing the Milvus gateway must not import pymilvus (dev machines may lack it)."""
    from app.vectorstore.milvus import MilvusVectorStore
    MilvusVectorStore("http://localhost:19530", "chunks_v1", 8)  # no error without pymilvus
```

Notes: `delete_document` on Milvus uses a filter expression with a UUID string — UUIDs
contain no quotes, so the f-string filter is injection-safe here; anything user-controlled
must never be interpolated into Milvus filters.

## Verification

1. `cd backend && python -m pytest -q` → all green (no pymilvus needed).
2. With the compose stack up and `RAG_VECTOR_BACKEND=milvus` + `pip install pymilvus`:
   `ensure_ready()` creates `chunks_v1` with HNSW/COSINE and partition-key field (inspect via Attu or `client.describe_collection`).

## Review Log

- 2026-07-17 — review-atom: freshness ✓ (vector_backend/milvus_* /embed_dim present in config.py; no import drift), completeness ✓, traceability ✓ (FR-3, NFR-1/3/8 / plan §03.2). Milvus verification step requires the compose stack — recorded as environment-dependent. Certified READY.

## Implementation Log

- 2026-07-17 — Verification 2 executed via milvus-lite (same MilvusClient API): ensure_ready created the collection (partition-key + HNSW/COSINE accepted), upsert/search/partition-filter/delete_document/stats all correct.

- 2026-07-17 — Implemented per atom, zero deviations. `pytest -q` → 38 passed (pymilvus
  not required; lazy-import test green).
- 2026-07-17 — VALIDATED. Suite green; milvus live-check deferred to compose environment
  (documented in Review Log). No OPEN findings. review-change clean.
