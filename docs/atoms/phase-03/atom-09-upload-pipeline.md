# atom-09-upload-pipeline

- Status: COMMITTED
- Phase: phase-03-ingestion (`docs/plans/phase-03-ingestion.md`, item §03.3)
- Traces: FR-4, FR-5, FR-6, FR-18, FR-17, NFR-2, NFR-6
- Depends on: atom-08
- Mode: normal
- Created: 2026-07-12

## Purpose

Documents flow in: `POST /api/v1/admin/upload` (admin JWT or ingest API key) validates type
and size, deduplicates by SHA-256, expands zip batches, persists PENDING rows, and hands off
to an async worker that drives PENDING → PROCESSING → INDEXED/FAILED — extracting, chunking,
embedding, and writing vectors with rollback on failure so no document is half-indexed.

## Files

| Path | Action |
|---|---|
| `backend/app/config.py` | modify (upload_dir) |
| `backend/app/services/tasks.py` | create |
| `backend/app/ingest/pipeline.py` | create |
| `backend/app/api/admin_upload.py` | create |
| `backend/app/schemas.py` | modify (upload schemas — full file below) |
| `backend/app/main.py` | modify (providers + queue in lifespan, router) |
| `backend/tests/conftest.py` | modify (fake providers, eager queue, tmp upload dir) |
| `backend/tests/test_upload_pipeline.py` | create |

## Implementation

Add to `Settings` in `backend/app/config.py` (one new field, after `zip_max_entries`):

```python file=backend/app/config.py
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RAG_", env_file=".env", extra="ignore")

    app_name: str = "RagStarter"
    env: str = "dev"

    database_url: str = "sqlite+aiosqlite:///./ragstarter.db"

    jwt_secret: str = "change-me-to-a-long-random-string"
    jwt_expires_min: int = 60
    cors_origins: list[str] = ["http://localhost:3000"]
    bootstrap_admin_email: str = "admin@example.com"
    bootstrap_admin_password: str = "change-me-now"

    embed_provider: str = "fake"  # fake | openai
    embed_api_base: str = "https://api.openai.com/v1"
    embed_api_key: str = ""
    embed_model: str = "text-embedding-3-small"
    embed_dim: int = 1536
    embed_batch: int = 64

    llm_provider: str = "fake"  # fake | openai
    llm_api_base: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    vector_backend: str = "memory"  # memory | milvus
    milvus_uri: str = "http://localhost:19530"
    milvus_collection: str = "chunks_v1"

    chunk_size_tokens: int = 512
    chunk_overlap_pct: int = 10
    upload_max_mb: int = 100
    upload_allowed_ext: list[str] = [".pdf", ".txt", ".md", ".zip"]
    zip_max_entries: int = 1000
    upload_dir: str = "./data/uploads"

    rate_chat_rpm: int = 30
    rate_upload_rpm: int = 60

    retrieval_top_k: int = 8
    rrf_k: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

```python file=backend/app/services/tasks.py
import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Protocol

log = logging.getLogger(__name__)


class TaskQueue(Protocol):
    """Boundary for async work dispatch (ADR-0001: Celery-swappable)."""

    def spawn(self, factory: Callable[[], Awaitable[None]]) -> None: ...


class BackgroundTaskQueue:
    """In-process asyncio tasks. Strong refs held until completion so tasks are never GC'd."""

    def __init__(self):
        self._tasks: set[asyncio.Task] = set()

    def spawn(self, factory: Callable[[], Awaitable[None]]) -> None:
        task = asyncio.create_task(self._run(factory))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    @staticmethod
    async def _run(factory: Callable[[], Awaitable[None]]) -> None:
        try:
            await factory()
        except Exception:
            log.exception("background task failed")


class EagerTaskQueue:
    """Test double: runs the work inline at spawn-await point via a drain() call."""

    def __init__(self):
        self.pending: list[Callable[[], Awaitable[None]]] = []

    def spawn(self, factory: Callable[[], Awaitable[None]]) -> None:
        self.pending.append(factory)

    async def drain(self) -> None:
        while self.pending:
            await self.pending.pop(0)()
```

```python file=backend/app/ingest/pipeline.py
import logging
import uuid
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Settings
from app.ingest.chunker import chunk_text
from app.ingest.embeddings import EmbeddingProvider
from app.ingest.extract import extract_text
from app.models import Chunk, Document
from app.vectorstore import VectorItem, VectorStore

log = logging.getLogger(__name__)


async def ingest_document(sessionmaker: async_sessionmaker, vector_store: VectorStore,
                          embedder: EmbeddingProvider, settings: Settings,
                          document_id: uuid.UUID) -> None:
    """Drives one document PENDING → PROCESSING → INDEXED/FAILED (FR-4). On any failure the
    document's vectors are purged so a FAILED document never has partial vectors (NFR-6)."""
    async with sessionmaker() as session:
        doc = await session.scalar(select(Document).where(Document.id == document_id))
        if doc is None:
            log.error("ingest: document %s vanished", document_id)
            return
        doc.status = "PROCESSING"
        await session.commit()

        try:
            data = Path(doc.path).read_bytes()
            text = extract_text(doc.filename, data)
            pieces = chunk_text(text, settings.chunk_size_tokens, settings.chunk_overlap_pct)
            if not pieces:
                raise ValueError("document produced no text chunks")

            embeddings = await embedder.embed(pieces)

            # replace any prior chunks (safe re-ingest), then write rows + vectors
            await session.execute(delete(Chunk).where(Chunk.document_id == doc.id))
            chunk_rows = [Chunk(id=uuid.uuid4(), document_id=doc.id, seq=i, text=p)
                          for i, p in enumerate(pieces)]
            session.add_all(chunk_rows)
            await session.flush()

            await vector_store.upsert([
                VectorItem(chunk_id=str(c.id), document_id=str(doc.id),
                           partition_key=doc.partition_key, embedding=e)
                for c, e in zip(chunk_rows, embeddings)
            ])

            doc.status = "INDEXED"
            doc.error = None
            await session.commit()
        except Exception as exc:
            await session.rollback()
            await vector_store.delete_document(str(doc.id))  # NFR-6: no partial index
            doc.status = "FAILED"
            doc.error = str(exc)[:2000]
            await session.commit()
            log.warning("ingest failed for %s: %s", doc.filename, exc)
```

```python file=backend/app/api/admin_upload.py
import hashlib
import io
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.ingest.pipeline import ingest_document
from app.models import Document
from app.schemas import UploadedDoc, UploadResponse
from app.security.deps import Principal, require_ingest
from app.security.ratelimit import rate_limit
from app.services import audit

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

DOC_EXTS = {".pdf", ".txt", ".md"}


def _ext(filename: str) -> str:
    return PurePosixPath(filename.replace("\\", "/")).suffix.lower()


async def _register(session: AsyncSession, request: Request, filename: str,
                    data: bytes) -> tuple[UploadedDoc, bool]:
    """Create (or dedupe) one document row + saved file. Returns (result, created)."""
    settings = request.app.state.settings
    content_hash = hashlib.sha256(data).hexdigest()
    existing = await session.scalar(
        select(Document).where(Document.content_hash == content_hash))
    if existing:  # FR-5: acknowledged, not re-processed
        return UploadedDoc(id=existing.id, filename=existing.filename,
                           status=existing.status, duplicate=True), False

    doc_id = uuid.uuid4()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / f"{doc_id}{_ext(filename)}"
    dest.write_bytes(data)

    doc = Document(id=doc_id, path=str(dest), filename=filename,
                   content_hash=content_hash, size_bytes=len(data),
                   mime="", status="PENDING")
    session.add(doc)
    await session.flush()
    return UploadedDoc(id=doc.id, filename=doc.filename, status="PENDING",
                       duplicate=False), True


@router.post("/upload", response_model=UploadResponse,
             dependencies=[Depends(rate_limit("upload"))])
async def upload(request: Request, file: UploadFile,
                 principal: Annotated[Principal, Depends(require_ingest)],
                 session: Annotated[AsyncSession, Depends(get_session)]) -> UploadResponse:
    settings = request.app.state.settings
    filename = file.filename or "upload"
    ext = _ext(filename)
    if ext not in settings.upload_allowed_ext:
        raise HTTPException(415, f"unsupported file type: {ext or '(none)'}")

    max_bytes = settings.upload_max_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:  # FR-18: rejected before permanent buffering
        raise HTTPException(413, f"file exceeds {settings.upload_max_mb} MB limit")

    documents: list[UploadedDoc] = []
    rejected: list[str] = []
    created_ids: list[uuid.UUID] = []

    if ext == ".zip":  # FR-6: batch archives
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            raise HTTPException(400, "corrupt zip archive")
        infos = [i for i in zf.infolist() if not i.is_dir()]
        if len(infos) > settings.zip_max_entries:
            raise HTTPException(413, f"zip exceeds {settings.zip_max_entries} entries")
        for info in infos:
            name = PurePosixPath(info.filename).name
            if _ext(name) not in DOC_EXTS:
                rejected.append(f"{info.filename}: unsupported type")
                continue
            if info.file_size > max_bytes:
                rejected.append(f"{info.filename}: exceeds size limit")
                continue
            entry, created = await _register(session, request, name, zf.read(info))
            documents.append(entry)
            if created:
                created_ids.append(entry.id)
    else:
        entry, created = await _register(session, request, filename, data)
        documents.append(entry)
        if created:
            created_ids.append(entry.id)

    await audit.record(session, principal.label, "document.uploaded", filename,
                       {"created": len(created_ids), "rejected": len(rejected)})
    await session.commit()

    state = request.app.state
    for doc_id in created_ids:  # NFR-2: ack now, work async
        state.task_queue.spawn(
            lambda d=doc_id: ingest_document(state.sessionmaker, state.vector_store,
                                             state.embedder, state.settings, d))
    return UploadResponse(documents=documents, rejected=rejected)
```

Schemas — full file (adds `UploadedDoc`, `UploadResponse`):

```python file=backend/app/schemas.py
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    role: Literal["admin", "user"] = "user"


class CreateApiKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ApiKeyOut(BaseModel):
    id: int
    name: str
    scope: str
    revoked_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreated(BaseModel):
    id: int
    name: str
    scope: str
    api_key: str  # plaintext — returned exactly once at creation


class AuditOut(BaseModel):
    id: int
    actor: str
    action: str
    target: str
    detail: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class UploadedDoc(BaseModel):
    id: uuid.UUID
    filename: str
    status: str
    duplicate: bool = False


class UploadResponse(BaseModel):
    documents: list[UploadedDoc]
    rejected: list[str]
```

`backend/app/main.py` — full file (wires providers, queue, upload router):

```python file=backend/app/main.py
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.admin_audit import router as admin_audit_router
from app.api.admin_keys import router as admin_keys_router
from app.api.admin_upload import router as admin_upload_router
from app.api.admin_users import router as admin_users_router
from app.api.auth import router as auth_router
from app.config import Settings, get_settings
from app.db import build_engine, build_sessionmaker
from app.ingest.embeddings import get_embedding_provider
from app.logging_setup import RequestIdMiddleware, setup_logging
from app.security.ratelimit import RateLimiter
from app.services.bootstrap import ensure_bootstrap_admin
from app.services.tasks import BackgroundTaskQueue
from app.vectorstore import get_vector_store

log = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.engine = build_engine(settings.database_url)
        app.state.sessionmaker = build_sessionmaker(app.state.engine)
        app.state.vector_store = get_vector_store(settings)
        await app.state.vector_store.ensure_ready()
        app.state.embedder = get_embedding_provider(settings)
        app.state.task_queue = BackgroundTaskQueue()
        await ensure_bootstrap_admin(app.state.sessionmaker, settings)
        log.info("startup complete", extra={"extra_fields": {"env": settings.env}})
        yield
        await app.state.engine.dispose()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.rate_limiter = RateLimiter()
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_router)
    app.include_router(admin_keys_router)
    app.include_router(admin_users_router)
    app.include_router(admin_audit_router)
    app.include_router(admin_upload_router)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict[str, str]:
        async with app.state.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ready"}

    return app


app = create_app()
```

`backend/tests/conftest.py` — full file (fake providers, eager queue, tmp upload dir):

```python file=backend/tests/conftest.py
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.db import Base, build_engine, build_sessionmaker
from app.ingest.embeddings import FakeEmbeddingProvider
from app.main import create_app
from app.models import User
from app.security.passwords import hash_password
from app.services.tasks import EagerTaskQueue
from app.vectorstore.memory import InMemoryVectorStore
from app import models  # noqa: F401  (registers tables)

ADMIN_EMAIL = "admin@test.io"
ADMIN_PASSWORD = "admin-pass-123"
USER_EMAIL = "user@test.io"
USER_PASSWORD = "user-pass-123"


def test_settings(**overrides) -> Settings:
    return Settings(
        database_url="sqlite+aiosqlite://",  # in-memory
        jwt_secret="test-secret",
        env="test",
        bootstrap_admin_email=ADMIN_EMAIL,
        bootstrap_admin_password=ADMIN_PASSWORD,
        embed_dim=8,
        **overrides,
    )


@pytest.fixture
async def db_engine():
    engine = build_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    maker = build_sessionmaker(db_engine)
    async with maker() as session:
        yield session


@pytest.fixture
def app_settings(tmp_path):
    return test_settings(upload_dir=str(tmp_path / "uploads"))


@pytest.fixture
async def app(db_engine, app_settings):
    # httpx.ASGITransport does NOT run lifespan — wire app state explicitly.
    application = create_app(app_settings)
    application.state.settings = app_settings
    application.state.engine = db_engine
    application.state.sessionmaker = build_sessionmaker(db_engine)
    application.state.vector_store = InMemoryVectorStore()
    application.state.embedder = FakeEmbeddingProvider(dim=app_settings.embed_dim)
    application.state.task_queue = EagerTaskQueue()
    # seed the two standard test accounts
    async with application.state.sessionmaker() as session:
        session.add(User(email=ADMIN_EMAIL, password_hash=hash_password(ADMIN_PASSWORD),
                         role="admin"))
        session.add(User(email=USER_EMAIL, password_hash=hash_password(USER_PASSWORD),
                         role="user"))
        await session.commit()
    return application


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def login(client: AsyncClient, email: str, password: str) -> dict[str, str]:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
async def admin_headers(client):
    return await login(client, ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture
async def user_headers(client):
    return await login(client, USER_EMAIL, USER_PASSWORD)
```

## Tests (normal mode: must exist before validate)

```python file=backend/tests/test_upload_pipeline.py
import io
import zipfile

from sqlalchemy import func, select

from app.models import AuditLog, Chunk, Document


def _txt_file(name="doc.txt", content=b"vacation policy grants twenty days"):
    return {"file": (name, io.BytesIO(content), "text/plain")}


async def _drain(app):
    await app.state.task_queue.drain()


async def test_upload_txt_reaches_indexed(client, app, admin_headers):
    r = await client.post("/api/v1/admin/upload", headers=admin_headers,
                          files=_txt_file())
    assert r.status_code == 200, r.text
    doc = r.json()["documents"][0]
    assert doc["status"] == "PENDING"
    await _drain(app)

    async with app.state.sessionmaker() as session:
        row = await session.scalar(select(Document))
        assert row.status == "INDEXED"
        n_chunks = await session.scalar(select(func.count()).select_from(Chunk))
        assert n_chunks >= 1
    assert (await app.state.vector_store.stats())["vectors"] == n_chunks


async def test_duplicate_hash_acknowledged_not_reprocessed(client, app, admin_headers):
    await client.post("/api/v1/admin/upload", headers=admin_headers, files=_txt_file())
    await _drain(app)
    r2 = await client.post("/api/v1/admin/upload", headers=admin_headers,
                           files=_txt_file(name="same-bytes-other-name.txt"))
    assert r2.json()["documents"][0]["duplicate"] is True
    assert app.state.task_queue.pending == []  # FR-5: no new job
    async with app.state.sessionmaker() as session:
        count = await session.scalar(select(func.count()).select_from(Document))
        assert count == 1


async def test_embedding_failure_marks_failed_no_vectors(client, app, admin_headers):
    class DownEmbedder:
        dim = 8
        async def embed(self, texts):
            raise RuntimeError("provider down")

    app.state.embedder = DownEmbedder()
    await client.post("/api/v1/admin/upload", headers=admin_headers, files=_txt_file())
    await _drain(app)

    async with app.state.sessionmaker() as session:
        row = await session.scalar(select(Document))
        assert row.status == "FAILED"
        assert "provider down" in row.error
        n_chunks = await session.scalar(select(func.count()).select_from(Chunk))
        assert n_chunks == 0
    assert (await app.state.vector_store.stats())["vectors"] == 0  # NFR-6


async def test_zip_mixed_entries(client, app, admin_headers):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("a.txt", "alpha document text")
        zf.writestr("b.md", "beta document text")
        zf.writestr("c.txt", "gamma document text")
        zf.writestr("virus.exe", "MZ")
    buf.seek(0)
    r = await client.post("/api/v1/admin/upload", headers=admin_headers,
                          files={"file": ("batch.zip", buf, "application/zip")})
    body = r.json()
    assert len(body["documents"]) == 3
    assert body["rejected"] == ["virus.exe: unsupported type"]
    await _drain(app)
    async with app.state.sessionmaker() as session:
        indexed = await session.scalar(select(func.count()).select_from(Document)
                                       .where(Document.status == "INDEXED"))
        assert indexed == 3


async def test_upload_validation(client, app, admin_headers, app_settings):
    r = await client.post("/api/v1/admin/upload", headers=admin_headers,
                          files=_txt_file(name="tool.exe"))
    assert r.status_code == 415

    app_settings.upload_max_mb = 0  # every non-empty file now exceeds the cap
    r = await client.post("/api/v1/admin/upload", headers=admin_headers,
                          files=_txt_file())
    assert r.status_code == 413
    app_settings.upload_max_mb = 100


async def test_upload_requires_auth_and_audits(client, app, admin_headers, user_headers):
    assert (await client.post("/api/v1/admin/upload",
                              files=_txt_file())).status_code == 401
    assert (await client.post("/api/v1/admin/upload", headers=user_headers,
                              files=_txt_file())).status_code == 403
    await client.post("/api/v1/admin/upload", headers=admin_headers, files=_txt_file())
    async with app.state.sessionmaker() as session:
        row = await session.scalar(select(AuditLog)
                                   .where(AuditLog.action == "document.uploaded"))
        assert row is not None
```

Notes: the spawn lambda binds `doc_id` via a default argument (`lambda d=doc_id:`) — without
it every task would ingest the last id. `EagerTaskQueue.drain()` runs the worker inline so
tests are deterministic; production uses `BackgroundTaskQueue`.

## Verification

1. `cd backend && python -m pytest -q` → all green.
2. Manual: upload a .txt via `/docs` → response PENDING; `GET /api/v1/admin/documents` (atom-10) shows INDEXED shortly after.

## Review Log

- 2026-07-17 — review-atom: freshness ✓ (config/main/conftest full-file blocks match current tree state + additions; require_ingest & rate_limit exist from atoms 05/06), completeness ✓, traceability ✓ (FR-4/5/6/17/18, NFR-2/6 / plan §03.3). Certified READY.

## Implementation Log

- 2026-07-17 — Implemented per atom, zero deviations. `pytest -q` → 44 passed.
- 2026-07-17 — VALIDATED. Upload → INDEXED flow, dedupe, zip batch, size/type limits,
  auth+audit all covered over HTTP; NFR-6 rollback verified (FAILED doc has zero
  vectors/chunks). Manual /docs check equivalent covered by tests; documents listing
  endpoint arrives in atom-10. No OPEN findings. review-change clean.
