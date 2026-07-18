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
