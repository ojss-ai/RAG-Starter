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
