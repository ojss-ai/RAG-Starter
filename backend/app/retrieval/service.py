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
