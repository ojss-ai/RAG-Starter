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
