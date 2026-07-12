# atom-01-backend-scaffold

- Status: READY
- Phase: phase-01-foundation (`docs/plans/phase-01-foundation.md`, item §01.1 + harness slice of §01.3)
- Traces: NFR-4, NFR-5, NFR-7, NFR-8
- Depends on: none
- Mode: normal
- Created: 2026-07-12

> RULES: An atom is one small, independently implementable and testable unit. Code blocks are
> COMPLETE — no `...`, no "similar to above", no TODOs. Exact paths only.
> Code blocks carry `file=<repo-relative path>`; `implement` writes each block to that path.

## Purpose

The repository skeleton and a running FastAPI backend exist: typed env-driven config,
structured JSON logging with per-request IDs, liveness/readiness endpoints, an app factory
with lifespan-managed async DB engine, and a pytest harness proving it.

## Files

| Path | Action |
|---|---|
| `.gitignore`, `.gitattributes`, `.env.example`, `README.md` | create |
| `backend/requirements.txt`, `backend/requirements-dev.txt`, `backend/pytest.ini` | create |
| `backend/app/__init__.py`, `config.py`, `logging_setup.py`, `db.py`, `main.py` | create |
| `backend/tests/__init__.py`, `conftest.py`, `test_health.py` | create |

## Implementation

```text file=.gitignore
__pycache__/
*.py[cod]
.venv/
venv/
.env
*.db
*.sqlite3
node_modules/
.next/
out/
dist/
coverage/
.pytest_cache/
.mypy_cache/
*.log
volumes/
.DS_Store
```

```text file=.gitattributes
* text=auto eol=lf
*.png binary
*.jpg binary
*.pdf binary
*.ico binary
```

```text file=.env.example
# Copy to .env and adjust. All backend settings use the RAG_ prefix.
RAG_ENV=dev
RAG_DATABASE_URL=postgresql+asyncpg://rag:rag@localhost:5432/rag
RAG_JWT_SECRET=change-me-to-a-long-random-string
RAG_JWT_EXPIRES_MIN=60
RAG_CORS_ORIGINS=["http://localhost:3000"]
RAG_BOOTSTRAP_ADMIN_EMAIL=admin@example.com
RAG_BOOTSTRAP_ADMIN_PASSWORD=change-me-now
# Providers: "fake" needs no network and is deterministic (dev/tests).
RAG_EMBED_PROVIDER=fake
RAG_EMBED_API_BASE=https://api.openai.com/v1
RAG_EMBED_API_KEY=
RAG_EMBED_MODEL=text-embedding-3-small
RAG_EMBED_DIM=1536
RAG_LLM_PROVIDER=fake
RAG_LLM_API_BASE=https://api.openai.com/v1
RAG_LLM_API_KEY=
RAG_LLM_MODEL=gpt-4o-mini
# Vector store: "memory" (dev/tests) or "milvus"
RAG_VECTOR_BACKEND=memory
RAG_MILVUS_URI=http://localhost:19530
# Ingestion
RAG_CHUNK_SIZE_TOKENS=512
RAG_CHUNK_OVERLAP_PCT=10
RAG_UPLOAD_MAX_MB=100
RAG_ZIP_MAX_ENTRIES=1000
# Rate limits (requests per minute per caller)
RAG_RATE_CHAT_RPM=30
RAG_RATE_UPLOAD_RPM=60
```

```markdown file=README.md
# RagStarter — 100M-Scale Enterprise RAG System

FastAPI + PostgreSQL + Milvus + Next.js RAG system: hybrid retrieval (TSVector + HNSW,
RRF-fused), streaming cited chat, admin dashboard, and a resilient folder-watcher daemon.
Built with [AtomForge](docs/srs.md) — see `docs/` for the SRS, phase plans, and atoms.

## Quick start

```bash
cp .env.example .env                     # set secrets
docker compose up -d postgres milvus    # backing services
cd backend && python -m venv .venv && . .venv/Scripts/activate
pip install -r requirements.txt -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload           # http://localhost:8000/docs
```

Tests: `cd backend && python -m pytest -q`

> Built on **AtomForge** by Suraj
```

```text file=backend/requirements.txt
fastapi>=0.115
uvicorn[standard]>=0.30
pydantic-settings>=2.4
SQLAlchemy>=2.0.35
aiosqlite>=0.20
asyncpg>=0.30
alembic>=1.13
httpx>=0.27
PyJWT>=2.9
python-multipart>=0.0.9
pypdf>=5.0
```

```text file=backend/requirements-dev.txt
pytest>=8.3
pytest-asyncio>=0.24
```

```ini file=backend/pytest.ini
[pytest]
asyncio_mode = auto
testpaths = tests
filterwarnings =
    error::RuntimeWarning
```

```python file=backend/app/__init__.py
```

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

    rate_chat_rpm: int = 30
    rate_upload_rpm: int = 60

    retrieval_top_k: int = 8
    rrf_k: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

```python file=backend/app/logging_setup.py
import json
import logging
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(extra)
        return json.dumps(payload, default=str)


def setup_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Assigns a request ID, exposes it as a header, and emits one access log line."""

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_var.set(rid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["x-request-id"] = rid
        logging.getLogger("access").info(
            "%s %s -> %s",
            request.method,
            request.url.path,
            response.status_code,
            extra={"extra_fields": {
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                "request_id": rid,
            }},
        )
        return response
```

```python file=backend/app/db.py
from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def build_engine(database_url: str):
    return create_async_engine(database_url, pool_pre_ping=True)


def build_sessionmaker(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request from the app-state sessionmaker."""
    maker: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    async with maker() as session:
        yield session
```

```python file=backend/app/main.py
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import Settings, get_settings
from app.db import build_engine, build_sessionmaker
from app.logging_setup import RequestIdMiddleware, setup_logging

log = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.engine = build_engine(settings.database_url)
        app.state.sessionmaker = build_sessionmaker(app.state.engine)
        log.info("startup complete", extra={"extra_fields": {"env": settings.env}})
        yield
        await app.state.engine.dispose()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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

```python file=backend/tests/__init__.py
```

## Tests (normal mode: must exist before validate)

```python file=backend/tests/conftest.py
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.db import build_engine, build_sessionmaker
from app.main import create_app


def test_settings(**overrides) -> Settings:
    return Settings(
        database_url="sqlite+aiosqlite://",  # in-memory
        jwt_secret="test-secret",
        env="test",
        **overrides,
    )


@pytest.fixture
async def client():
    # httpx.ASGITransport does NOT run lifespan, so app state is wired explicitly.
    settings = test_settings()
    app = create_app(settings)
    engine = build_engine(settings.database_url)
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = build_sessionmaker(engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()
```

```python file=backend/tests/test_health.py
async def test_healthz_ok(client):
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_readyz_checks_db(client):
    r = await client.get("/readyz")
    assert r.status_code == 200
    assert r.json() == {"status": "ready"}


async def test_request_id_header(client):
    r = await client.get("/healthz")
    assert len(r.headers["x-request-id"]) == 32

    r2 = await client.get("/healthz", headers={"x-request-id": "trace-me"})
    assert r2.headers["x-request-id"] == "trace-me"
```

Notes: `ASGITransport` does NOT execute FastAPI lifespan — the fixture wires
`app.state` itself. Settings never read `.env` in tests because every field is passed
explicitly. `sqlite+aiosqlite://` is a fresh in-memory DB per engine.

## Verification

1. `cd backend && python -m pytest -q` → 3 passed.
2. `uvicorn app.main:app` then `GET /healthz` → `{"status":"ok"}` with `x-request-id` header.

## Review Log

## Implementation Log
