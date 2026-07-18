from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Chunk, Document, User
from app.schemas import MetricsOut
from app.security.deps import require_admin

router = APIRouter(prefix="/api/v1/admin/metrics", tags=["admin"])


@router.get("", response_model=MetricsOut)
async def metrics(request: Request,
                  admin: Annotated[User, Depends(require_admin)],
                  session: Annotated[AsyncSession, Depends(get_session)]) -> MetricsOut:
    counts = {status: n for status, n in (await session.execute(
        select(Document.status, func.count()).group_by(Document.status))).all()}
    chunk_count = await session.scalar(select(func.count()).select_from(Chunk)) or 0
    vector_stats = await request.app.state.vector_store.stats()
    http = request.app.state.http_metrics
    return MetricsOut(
        documents_by_status=counts,
        documents_total=sum(counts.values()),
        chunks_total=chunk_count,
        vector_backend=vector_stats.get("backend", "unknown"),
        vectors_total=vector_stats.get("vectors", 0),
        http_requests=http.requests,
        http_errors=http.errors,
        error_rate=http.error_rate,
    )
