# atom-11-hybrid-retrieval

- Status: COMMITTED
- Phase: phase-04-chat (`docs/plans/phase-04-chat.md`, item §04.1)
- Traces: FR-8, NFR-1
- Depends on: atom-10
- Mode: normal
- Created: 2026-07-12

## Purpose

Hybrid retrieval works: keyword search (PostgreSQL `websearch_to_tsquery`/`ts_rank` on the
generated tsvector; LIKE-overlap fallback on SQLite), vector search through the VectorStore,
and Reciprocal Rank Fusion merging both rankings into scored, metadata-joined chunks.

## Files

| Path | Action |
|---|---|
| `backend/app/retrieval/__init__.py`, `keyword.py`, `fusion.py`, `service.py` | create |
| `backend/tests/test_retrieval.py` | create |

## Implementation

```python file=backend/app/retrieval/__init__.py
```

```python file=backend/app/retrieval/keyword.py
import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chunk


async def keyword_search(session: AsyncSession, query: str, top_k: int) -> list[uuid.UUID]:
    """Ranked chunk ids by keyword relevance (FR-8, keyword leg).

    PostgreSQL: raw SQL against the generated `ts` tsvector — raw because the column is
    deliberately unmapped in the ORM (dialect-specific, see atom-02); fully parameterized.
    Other dialects (tests): LIKE-candidate fetch, ranked by distinct-word overlap.
    """
    words = [w for w in query.lower().split() if w]
    if not words:
        return []

    if session.bind.dialect.name == "postgresql":
        rows = await session.execute(text(
            "SELECT id FROM chunks "
            "WHERE ts @@ websearch_to_tsquery('english', :q) "
            "ORDER BY ts_rank(ts, websearch_to_tsquery('english', :q)) DESC "
            "LIMIT :k"), {"q": query, "k": top_k})
        return [r[0] for r in rows]

    # fallback: fetch LIKE candidates, rank by how many query words each chunk contains
    from sqlalchemy import or_
    cond = or_(*[Chunk.text.ilike(f"%{w}%") for w in words])
    candidates = (await session.scalars(select(Chunk).where(cond).limit(500))).all()

    def overlap(chunk: Chunk) -> int:
        lowered = chunk.text.lower()
        return sum(1 for w in words if w in lowered)

    ranked = sorted(candidates, key=overlap, reverse=True)[:top_k]
    return [c.id for c in ranked]
```

```python file=backend/app/retrieval/fusion.py
from collections import defaultdict
from typing import Hashable


def rrf(rankings: list[list[Hashable]], k: int = 60) -> list[tuple[Hashable, float]]:
    """Reciprocal Rank Fusion (FR-8): score(d) = Σ over rankings 1/(k + rank(d)),
    rank starting at 1. Returns (id, score) sorted descending; deterministic tie-break
    on the string form of the id."""
    scores: dict[Hashable, float] = defaultdict(float)
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] += 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda t: (-t[1], str(t[0])))
```

```python file=backend/app/retrieval/service.py
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.ingest.embeddings import EmbeddingProvider
from app.models import Chunk, Document
from app.retrieval.fusion import rrf
from app.retrieval.keyword import keyword_search
from app.vectorstore import VectorStore


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    seq: int
    text: str
    score: float


async def retrieve(session: AsyncSession, vector_store: VectorStore,
                   embedder: EmbeddingProvider, settings: Settings,
                   query: str) -> list[RetrievedChunk]:
    """Hybrid retrieval: keyword + vector legs fused by RRF, joined with metadata."""
    top_k = settings.retrieval_top_k

    kw_ids = await keyword_search(session, query, top_k * 2)

    [query_vec] = await embedder.embed([query])
    hits = await vector_store.search(query_vec, top_k * 2)
    vec_ids = [uuid.UUID(h.chunk_id) for h in hits]

    fused = rrf([kw_ids, vec_ids], k=settings.rrf_k)[:top_k]
    if not fused:
        return []

    wanted = [cid for cid, _ in fused]
    rows = (await session.execute(
        select(Chunk, Document.filename)
        .join(Document, Chunk.document_id == Document.id)
        .where(Chunk.id.in_(wanted)))).all()
    by_id = {chunk.id: (chunk, filename) for chunk, filename in rows}

    out: list[RetrievedChunk] = []
    for cid, score in fused:
        if cid not in by_id:  # vector store may lag a deletion; skip ghosts
            continue
        chunk, filename = by_id[cid]
        out.append(RetrievedChunk(chunk_id=chunk.id, document_id=chunk.document_id,
                                  filename=filename, seq=chunk.seq, text=chunk.text,
                                  score=score))
    return out
```

## Tests (normal mode: must exist before validate)

```python file=backend/tests/test_retrieval.py
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
```

Notes: the PG leg is exercised only against real PostgreSQL (phase DoD verification with
the compose stack); tests here cover the fallback leg, the fusion math, and the join. The
`if cid not in by_id: continue` guard covers vector-store/DB drift after deletions.

## Verification

1. `cd backend && python -m pytest -q` → all green.
2. Against compose PG + seeded docs: the raw tsquery leg returns ranked ids (`EXPLAIN ANALYZE` uses the GIN index — postgres skill check).

## Review Log

- 2026-07-17 — review-atom: freshness ✓ (retrieval_top_k/rrf_k in config; VectorStore/EmbeddingProvider signatures match atoms 07/08; ts column unmapped as expected), completeness ✓, traceability ✓ (FR-8, NFR-1 / plan §04.1). PG tsquery leg verification is compose-environment-dependent. Certified READY.

## Implementation Log

- 2026-07-17 — Verification 2 executed on embedded PostgreSQL 16 (pgserver): tsquery leg returns ranked ids; EXPLAIN shows Bitmap Index Scan on ix_chunks_ts (GIN).

- 2026-07-17 — Implemented per atom. Two test deviations (atom updated to match):
  (1) test_rrf_known_fusion asserted B > A for symmetric rankings, which contradicts the
  RRF formula (A = 1/2 + 1/4 = 0.75 > B = 2/3 at k=1); rewritten to assert the correct
  scores plus a proper consensus-wins case. (2) e2e relevance assertion was an RRF tie
  broken by random uuid strings at dim=8 (hash collisions invert the vector leg, verified
  numerically); test now uses FakeEmbeddingProvider(dim=32). Implementation code unchanged.
  `pytest -q` → 52 passed.
- 2026-07-17 — VALIDATED. Fusion math, keyword fallback, hybrid e2e, empty corpus all
  green. PG tsquery leg deferred to compose verification. No OPEN findings.
  review-change clean.
