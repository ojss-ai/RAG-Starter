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
