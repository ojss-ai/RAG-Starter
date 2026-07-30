# atom-10-ledger-delete-metrics

- Status: COMMITTED
- Phase: phase-03-ingestion (`docs/plans/phase-03-ingestion.md`, item §03.4)
- Traces: FR-7, FR-20, FR-17
- Depends on: atom-09
- Mode: normal
- Created: 2026-07-12

## Purpose

Admins can manage and observe the corpus: a searchable, paginated document ledger; deletion
that purges PostgreSQL rows and vectors together (audited); and the metrics endpoint
reporting document counts by state, chunk/vector totals, and API error rate.

## Files

| Path | Action |
|---|---|
| `backend/app/services/metrics.py` | create |
| `backend/app/api/admin_documents.py`, `backend/app/api/metrics.py` | create |
| `backend/app/schemas.py` | modify (document/metrics schemas — appended classes below) |
| `backend/app/main.py` | modify (routers + http metrics middleware) |
| `backend/tests/test_documents_metrics.py` | create |

## Implementation

```python file=backend/app/services/metrics.py
from dataclasses import dataclass, field

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


@dataclass
class HttpMetrics:
    """In-process request/error counters (FR-20). Single-process like the rate limiter;
    swap for Prometheus in multi-worker deployments."""

    requests: int = 0
    errors: int = 0
    by_status: dict[int, int] = field(default_factory=dict)

    def observe(self, status_code: int) -> None:
        self.requests += 1
        self.by_status[status_code] = self.by_status.get(status_code, 0) + 1
        if status_code >= 500:
            self.errors += 1

    @property
    def error_rate(self) -> float:
        return round(self.errors / self.requests, 4) if self.requests else 0.0


class HttpMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
        except Exception:
            request.app.state.http_metrics.observe(500)
            raise
        request.app.state.http_metrics.observe(response.status_code)
        return response
```

```python file=backend/app/api/admin_documents.py
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Chunk, Document, User
from app.schemas import DocumentList, DocumentOut
from app.security.deps import require_admin
from app.services import audit

router = APIRouter(prefix="/api/v1/admin/documents", tags=["admin"])


@router.get("", response_model=DocumentList)
async def list_documents(admin: Annotated[User, Depends(require_admin)],
                         session: Annotated[AsyncSession, Depends(get_session)],
                         q: Annotated[str | None, Query(max_length=200)] = None,
                         doc_status: Annotated[str | None, Query(alias="status")] = None,
                         limit: Annotated[int, Query(ge=1, le=200)] = 50,
                         offset: Annotated[int, Query(ge=0)] = 0) -> DocumentList:
    base = select(Document)
    if q:
        base = base.where(Document.filename.ilike(f"%{q}%"))
    if doc_status:
        base = base.where(Document.status == doc_status)
    total = await session.scalar(
        select(func.count()).select_from(base.subquery()))
    rows = await session.scalars(base.order_by(Document.created_at.desc())
                                 .limit(limit).offset(offset))
    return DocumentList(total=total or 0, documents=list(rows))


@router.delete("/{doc_id}", status_code=204)
async def delete_document(doc_id: uuid.UUID, request: Request,
                          admin: Annotated[User, Depends(require_admin)],
                          session: Annotated[AsyncSession, Depends(get_session)]) -> None:
    doc = await session.get(Document, doc_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    # FR-7: purge vectors first, then rows, in one request; a vector-store failure aborts
    # before any relational delete so no orphan vectors can exist.
    await request.app.state.vector_store.delete_document(str(doc_id))
    await session.execute(delete(Chunk).where(Chunk.document_id == doc_id))
    await session.delete(doc)
    await audit.record(session, admin.email, "document.deleted", doc.filename,
                       {"document_id": str(doc_id)})
    await session.commit()
```

```python file=backend/app/api/metrics.py
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
```

Append these classes to `backend/app/schemas.py` (keep every existing class; new ones go at
the end of the file):

```python file=backend/app/schemas_atom10_append.py
# --- APPEND the classes below to backend/app/schemas.py (implement merges; this helper
# --- filename exists only so the extractor can carry the block; delete after merging).
import uuid
from datetime import datetime

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: uuid.UUID
    filename: str
    status: str
    error: str | None
    size_bytes: int
    partition_key: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentList(BaseModel):
    total: int
    documents: list[DocumentOut]


class MetricsOut(BaseModel):
    documents_by_status: dict[str, int]
    documents_total: int
    chunks_total: int
    vector_backend: str
    vectors_total: int
    http_requests: int
    http_errors: int
    error_rate: float
```

`backend/app/main.py` — add these pieces to the atom-09 version (three changes):

1. imports: `from app.api.admin_documents import router as admin_documents_router`,
   `from app.api.metrics import router as metrics_router`,
   `from app.services.metrics import HttpMetrics, HttpMetricsMiddleware`
2. after `app.state.rate_limiter = RateLimiter()`: add `app.state.http_metrics = HttpMetrics()`
   and `app.add_middleware(HttpMetricsMiddleware)` (before RequestIdMiddleware so it wraps
   outermost… order note: starlette applies middleware in reverse-add order; add
   HttpMetricsMiddleware AFTER RequestIdMiddleware in code so RequestId stays outermost).
3. `app.include_router(admin_documents_router)` and `app.include_router(metrics_router)`.

## Tests (normal mode: must exist before validate)

```python file=backend/tests/test_documents_metrics.py
import io

from sqlalchemy import func, select

from app.models import AuditLog, Chunk, Document


def _txt(name, content):
    return {"file": (name, io.BytesIO(content), "text/plain")}


async def _seed_docs(client, app, admin_headers):
    for name, content in [("alpha.txt", b"alpha content one"),
                          ("beta.txt", b"beta content two"),
                          ("gamma.md", b"gamma content three")]:
        await client.post("/api/v1/admin/upload", headers=admin_headers,
                          files=_txt(name, content))
    await app.state.task_queue.drain()


async def test_ledger_search_filter_paginate(client, app, admin_headers):
    await _seed_docs(client, app, admin_headers)
    r = await client.get("/api/v1/admin/documents", headers=admin_headers)
    assert r.json()["total"] == 3

    r = await client.get("/api/v1/admin/documents?q=alp", headers=admin_headers)
    assert [d["filename"] for d in r.json()["documents"]] == ["alpha.txt"]

    r = await client.get("/api/v1/admin/documents?status=INDEXED&limit=2",
                         headers=admin_headers)
    assert r.json()["total"] == 3
    assert len(r.json()["documents"]) == 2

    assert (await client.get("/api/v1/admin/documents")).status_code == 401


async def test_delete_purges_both_stores_and_audits(client, app, admin_headers):
    await _seed_docs(client, app, admin_headers)
    async with app.state.sessionmaker() as session:
        doc = await session.scalar(select(Document)
                                   .where(Document.filename == "alpha.txt"))
        doc_id = doc.id
    before = (await app.state.vector_store.stats())["vectors"]

    r = await client.delete(f"/api/v1/admin/documents/{doc_id}", headers=admin_headers)
    assert r.status_code == 204

    async with app.state.sessionmaker() as session:
        assert await session.get(Document, doc_id) is None
        orphan_chunks = await session.scalar(
            select(func.count()).select_from(Chunk).where(Chunk.document_id == doc_id))
        assert orphan_chunks == 0
        row = await session.scalar(select(AuditLog)
                                   .where(AuditLog.action == "document.deleted"))
        assert row is not None
    assert (await app.state.vector_store.stats())["vectors"] < before

    missing = await client.delete(f"/api/v1/admin/documents/{doc_id}",
                                  headers=admin_headers)
    assert missing.status_code == 404


async def test_metrics_counts_and_error_rate(client, app, admin_headers):
    await _seed_docs(client, app, admin_headers)
    r = await client.get("/api/v1/admin/metrics", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["documents_by_status"]["INDEXED"] == 3
    assert body["documents_total"] == 3
    assert body["chunks_total"] == body["vectors_total"] >= 3
    assert body["vector_backend"] == "memory"
    assert body["http_requests"] > 0
    assert body["error_rate"] == 0.0

    assert (await client.get("/api/v1/admin/metrics")).status_code == 401
```

Notes: the schemas append-block ships as `schemas_atom10_append.py` purely for extraction —
`implement` merges its classes into `schemas.py` and deletes the helper file. Middleware
order matters: keep `RequestIdMiddleware` added last so it is outermost and every metrics
observation happens inside a request-id context.

## Verification

1. `cd backend && python -m pytest -q` → all green.
2. Manual: `/docs` → upload, list ledger, delete one, `GET /api/v1/admin/metrics` shows updated counts.

## Review Log

- 2026-07-17 — review-atom: freshness ✓ (atom-09 main.py/schemas.py are the exact base these instructions modify; vector_store/http state names match), completeness ✓ (append-helper + 3-step main.py edit are explicit), traceability ✓ (FR-7/17/20 / plan §03.4). Certified READY.

## Implementation Log

- 2026-07-17 — Implemented per atom: helper block merged into schemas.py and deleted;
  main.py 3-step wiring applied (HttpMetricsMiddleware added before RequestIdMiddleware in
  code, so RequestId is outermost). `pytest -q` → 47 passed. Zero deviations.
- 2026-07-17 — VALIDATED. Ledger search/filter/pagination, dual-store delete + audit,
  metrics counts + error-rate all verified over HTTP. No OPEN findings. review-change clean.
