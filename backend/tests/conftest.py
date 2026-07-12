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
