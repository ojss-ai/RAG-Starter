import uuid

from app.models import Chunk, Document
from app.retrieval.fusion import rrf
from app.retrieval.keyword import keyword_search
from app.retrieval.service import retrieve
from app.vectorstore import VectorItem


def test_rrf_known_fusion():
    # symmetric rankings: A and C swap ranks 1/3, B is #2 in both
    fused = rrf([["A", "B", "C"], ["C", "B", "A"]], k=1)
    scores = dict(fused)
    assert scores["A"] == scores["C"]              # symmetric ranks → equal score
    assert abs(scores["B"] - 2 / 3) < 1e-9         # 2 × 1/(1+2)
    assert fused[0][0] == "A"                      # tie A/C broken on str(id)
    # consensus: an item ranked high in BOTH lists beats single-list items
    fused2 = rrf([["A", "B"], ["B", "C"]], k=1)
    assert fused2[0][0] == "B"


def test_rrf_empty_and_single():
    assert rrf([]) == []
    assert [d for d, _ in rrf([["x", "y"]])] == ["x", "y"]


async def _seed(app, texts: dict[str, str]):
    """Insert one INDEXED document per (filename → text), one chunk each, with vectors."""
    ids = {}
    async with app.state.sessionmaker() as session:
        for filename, content in texts.items():
            doc = Document(id=uuid.uuid4(), path=f"/x/{filename}", filename=filename,
                           content_hash=f"h-{filename}", size_bytes=len(content),
                           status="INDEXED")
            chunk = Chunk(id=uuid.uuid4(), document_id=doc.id, seq=0, text=content)
            session.add_all([doc, chunk])
            ids[filename] = (doc.id, chunk.id)
        await session.commit()
    for filename, content in texts.items():
        [vec] = await app.state.embedder.embed([content])
        doc_id, chunk_id = ids[filename]
        await app.state.vector_store.upsert([VectorItem(
            chunk_id=str(chunk_id), document_id=str(doc_id),
            partition_key="default", embedding=vec)])
    return ids


async def test_keyword_fallback_ranks_by_overlap(app):
    await _seed(app, {
        "policy.txt": "vacation policy grants twenty days vacation",
        "recipe.txt": "chocolate cake recipe with sugar",
    })
    async with app.state.sessionmaker() as session:
        ids = await keyword_search(session, "vacation days", top_k=5)
        assert len(ids) >= 1
        first = await session.get(Chunk, ids[0])
        assert "vacation" in first.text


async def test_hybrid_retrieve_end_to_end(app, app_settings):
    # dim=8 (conftest default) has too many hash collisions for a 3-doc relevance
    # assertion — use a wider fake embedder for this test.
    from app.ingest.embeddings import FakeEmbeddingProvider
    app.state.embedder = FakeEmbeddingProvider(dim=32)
    await _seed(app, {
        "policy.txt": "vacation policy grants twenty days of paid vacation per year",
        "recipe.txt": "chocolate cake recipe with sugar and flour",
        "handbook.txt": "office hours and parking rules for employees",
    })
    async with app.state.sessionmaker() as session:
        results = await retrieve(session, app.state.vector_store, app.state.embedder,
                                 app_settings, "how many vacation days do employees get")
    assert results, "hybrid retrieval returned nothing"
    assert results[0].filename == "policy.txt"
    assert results[0].score >= results[-1].score
    assert all(r.filename for r in results)


async def test_retrieve_empty_corpus(app, app_settings):
    async with app.state.sessionmaker() as session:
        assert await retrieve(session, app.state.vector_store, app.state.embedder,
                              app_settings, "anything") == []
