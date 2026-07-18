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
        # SQLite ships with FK enforcement OFF per connection; without this pragma
        # ON DELETE CASCADE (relied on via passive_deletes=True) silently no-ops.
        @event.listens_for(engine.sync_engine, "connect")
        def _sqlite_fk_on(dbapi_conn, _record):  # pragma: no cover - trivial
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


def build_sessionmaker(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request from the app-state sessionmaker."""
    maker: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    async with maker() as session:
        yield session
