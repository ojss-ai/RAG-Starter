# atom-02-db-schema

- Status: VALIDATED
- Phase: phase-01-foundation (`docs/plans/phase-01-foundation.md`, item §01.2)
- Traces: FR-3, FR-4, FR-11, FR-14, FR-16, FR-17 (schema only), NFR-1
- Depends on: atom-01
- Mode: normal
- Created: 2026-07-12

## Purpose

The complete relational schema exists as SQLAlchemy 2 async models plus the initial Alembic
migration: users, api_keys, audit_log, documents, chunks (with PG-only generated tsvector +
GIN index), chat_sessions, chat_messages — every FK explicitly indexed, constraints at the
DB level.

## Files

| Path | Action |
|---|---|
| `backend/app/models.py` | create |
| `backend/app/db.py` | modify (SQLite FK pragma) |
| `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako` | create |
| `backend/alembic/versions/0001_initial_schema.py` | create |
| `backend/tests/conftest.py` | modify (db fixtures) |
| `backend/tests/test_schema.py` | create |

## Implementation

```python file=backend/app/models.py
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

JsonB = JSON().with_variant(JSONB(), "postgresql")

DOCUMENT_STATUSES = ("PENDING", "PROCESSING", "INDEXED", "FAILED")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer(), "sqlite"),
                                    primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False, server_default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now(), nullable=False)

    __table_args__ = (CheckConstraint("role IN ('admin','user')", name="ck_users_role"),)


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer(), "sqlite"),
                                    primary_key=True, autoincrement=True)
    key_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False, server_default="ingest")
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now(), nullable=False)

    __table_args__ = (CheckConstraint("scope IN ('ingest')", name="ck_api_keys_scope"),)


class AuditLog(Base):
    """Append-only: no update/delete paths exist in the application."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer(), "sqlite"),
                                    primary_key=True, autoincrement=True)
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    target: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    detail: Mapped[dict] = mapped_column(JsonB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now(), nullable=False)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger().with_variant(Integer(), "sqlite"),
                                            nullable=False)
    mime: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="PENDING")
    error: Mapped[str | None] = mapped_column(Text)
    partition_key: Mapped[str] = mapped_column(Text, nullable=False, server_default="default")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now(),
                                                 onupdate=func.now(), nullable=False)

    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document",
                                                 cascade="all, delete-orphan",
                                                 passive_deletes=True)

    __table_args__ = (
        CheckConstraint("status IN ('PENDING','PROCESSING','INDEXED','FAILED')",
                        name="ck_documents_status"),
        Index("ix_documents_status", "status"),
        Index("ix_documents_partition_key", "partition_key"),
    )


class Chunk(Base):
    """`ts` (generated tsvector) + its GIN index exist only on PostgreSQL — added in the
    migration, deliberately unmapped here so the model stays dialect-portable."""

    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    document: Mapped[Document] = relationship(back_populates="chunks")

    __table_args__ = (Index("ix_chunks_document_id", "document_id"),)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"),
                                         nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, server_default="New chat")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now(), nullable=False)

    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="session",
                                                         cascade="all, delete-orphan",
                                                         passive_deletes=True)

    __table_args__ = (Index("ix_chat_sessions_user_id", "user_id"),)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer(), "sqlite"),
                                    primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[list] = mapped_column(JsonB, nullable=False, default=list)
    truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 server_default=func.now(), nullable=False)

    session: Mapped[ChatSession] = relationship(back_populates="messages")

    __table_args__ = (
        CheckConstraint("role IN ('user','assistant')", name="ck_chat_messages_role"),
        Index("ix_chat_messages_session_id", "session_id"),
    )
```

```python file=backend/app/db.py
from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def build_engine(database_url: str):
    engine = create_async_engine(database_url, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine.sync_engine, "connect")
        def _fk_on(dbapi_conn, _):  # SQLite needs FKs switched on per connection
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
    return engine


def build_sessionmaker(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request from the app-state sessionmaker."""
    maker: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    async with maker() as session:
        yield session
```

```ini file=backend/alembic.ini
[alembic]
script_location = alembic
prepend_sys_path = .
sqlalchemy.url =

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARNING
handlers = console
qualname =

[logger_sqlalchemy]
level = WARNING
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

```python file=backend/alembic/env.py
import asyncio
import os

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.db import Base
from app import models  # noqa: F401  (registers all tables on Base.metadata)

target_metadata = Base.metadata


def _url() -> str:
    return os.environ.get("RAG_DATABASE_URL") or get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def _run_sync(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(_url())
    async with engine.connect() as connection:
        await connection.run_sync(_run_sync)
        await connection.commit()
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

```mako file=backend/alembic/script.py.mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

```python file=backend/alembic/versions/0001_initial_schema.py
"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-12

One concern: the complete initial schema. Table shapes come from Base.metadata (models ==
schema at revision zero by definition; later migrations use explicit ops). The PG-only
pieces — generated tsvector column on chunks + GIN index — are added with dialect-guarded
DDL and dropped symmetrically on downgrade.
"""
from alembic import op

from app.db import Base
from app import models  # noqa: F401

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind)
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE chunks ADD COLUMN ts tsvector "
            "GENERATED ALWAYS AS (to_tsvector('english', text)) STORED"
        )
        op.execute("CREATE INDEX ix_chunks_ts ON chunks USING GIN (ts)")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_chunks_ts")
        op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS ts")
    Base.metadata.drop_all(bind)
```

## Tests (normal mode: must exist before validate)

```python file=backend/tests/conftest.py
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.db import Base, build_engine, build_sessionmaker
from app.main import create_app
from app import models  # noqa: F401  (registers tables)


def test_settings(**overrides) -> Settings:
    return Settings(
        database_url="sqlite+aiosqlite://",  # in-memory
        jwt_secret="test-secret",
        env="test",
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
async def client(db_engine):
    # httpx.ASGITransport does NOT run lifespan — wire app state to the schema-loaded engine.
    settings = test_settings()
    app = create_app(settings)
    app.state.settings = settings
    app.state.engine = db_engine
    app.state.sessionmaker = build_sessionmaker(db_engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
```

```python file=backend/tests/test_schema.py
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models import Chunk, Document, User


async def test_metadata_creates_all_tables(db_session):
    count = await db_session.scalar(select(func.count()).select_from(User))
    assert count == 0


async def test_email_unique(db_session):
    db_session.add(User(email="a@x.io", password_hash="h", role="user"))
    await db_session.commit()
    db_session.add(User(email="a@x.io", password_hash="h2", role="user"))
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_document_status_check(db_session):
    db_session.add(Document(path="/f", filename="f", content_hash="h1",
                            size_bytes=1, status="NOT-A-STATUS"))
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_chunk_cascade_delete(db_session):
    doc = Document(path="/f", filename="f", content_hash="h2", size_bytes=1)
    db_session.add(doc)
    await db_session.flush()
    db_session.add_all([Chunk(document_id=doc.id, seq=i, text=f"c{i}") for i in range(3)])
    await db_session.commit()

    await db_session.delete(doc)
    await db_session.commit()
    left = await db_session.scalar(select(func.count()).select_from(Chunk))
    assert left == 0


async def test_content_hash_unique(db_session):
    db_session.add(Document(path="/a", filename="a", content_hash="same", size_bytes=1))
    await db_session.commit()
    db_session.add(Document(path="/b", filename="b", content_hash="same", size_bytes=2))
    with pytest.raises(IntegrityError):
        await db_session.commit()
```

Notes: `conftest.py` replaces atom-01's version (adds DB fixtures; `client` now shares the
schema-loaded engine so API tests and direct session tests see the same in-memory DB).

## Verification

1. `cd backend && python -m pytest -q` → all green (health + schema).
2. Against dockerized Postgres: `alembic upgrade head` then `alembic downgrade base` — both clean (skill oracle; executed in atom-03 verification).

## Review Log

## Implementation Log

- 2026-07-12 — 8 files extracted (conftest replaced per plan) — `pytest -q`: 8 passed — validate: constraints/cascade/CHECK tests green — PG up/down deferred to atom-03 verification as documented
