# atom-04-auth-core

- Status: COMMITTED
- Phase: phase-02-security (`docs/plans/phase-02-security.md`, item §02.1; audit service pulled forward from §02.3 because logins must be audited)
- Traces: FR-14, FR-17
- Depends on: atom-02
- Mode: normal
- Created: 2026-07-12

## Purpose

Human authentication works end-to-end: PBKDF2 password hashing, JWT issue/verify,
`POST /api/v1/auth/login`, `GET /api/v1/auth/me`, bootstrap-admin seeding at startup, and
an audit service that records every login attempt.

## Files

| Path | Action |
|---|---|
| `backend/app/security/__init__.py`, `passwords.py`, `tokens.py`, `deps.py` | create |
| `backend/app/services/__init__.py`, `audit.py`, `bootstrap.py` | create |
| `backend/app/schemas.py` | create |
| `backend/app/api/__init__.py`, `backend/app/api/auth.py` | create |
| `backend/app/main.py` | modify (router, seeding in lifespan) |
| `backend/tests/conftest.py` | modify (seeded admin/user + auth helpers) |
| `backend/tests/test_auth.py` | create |

## Implementation

```python file=backend/app/security/__init__.py
```

```python file=backend/app/security/passwords.py
import hashlib
import hmac
import secrets

_ALGO = "pbkdf2_sha256"
_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt),
                                 _ITERATIONS).hex()
    return f"{_ALGO}${_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt, digest = stored.split("$")
        if algo != _ALGO:
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt),
                                        int(iters)).hex()
        return hmac.compare_digest(candidate, digest)
    except (ValueError, TypeError):
        return False
```

```python file=backend/app/security/tokens.py
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt


class TokenError(Exception):
    pass


@dataclass(frozen=True)
class TokenData:
    user_id: int
    email: str
    role: str


def create_token(user_id: int, email: str, role: str, secret: str, expires_min: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=expires_min),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_token(token: str, secret: str) -> TokenData:
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    return TokenData(user_id=int(payload["sub"]), email=payload["email"],
                     role=payload["role"])
```

```python file=backend/app/security/deps.py
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import User
from app.security.tokens import TokenError, decode_token

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    settings = request.app.state.settings
    try:
        data = decode_token(creds.credentials, settings.jwt_secret)
    except TokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = await session.scalar(select(User).where(User.id == data.user_id))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown user")
    return user


require_user = get_current_user
```

```python file=backend/app/services/__init__.py
```

```python file=backend/app/services/audit.py
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


async def record(session: AsyncSession, actor: str, action: str,
                 target: str = "", detail: dict | None = None) -> None:
    """Append one audit row. Caller owns the transaction (commit with the action itself
    so the audit entry and the audited change are atomic)."""
    session.add(AuditLog(actor=actor, action=action, target=target, detail=detail or {}))
```

```python file=backend/app/services/bootstrap.py
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Settings
from app.models import User
from app.security.passwords import hash_password
from app.services import audit

log = logging.getLogger(__name__)


async def ensure_bootstrap_admin(sessionmaker: async_sessionmaker, settings: Settings) -> None:
    """Idempotent: creates the bootstrap admin only when absent."""
    async with sessionmaker() as session:
        existing = await session.scalar(
            select(User).where(User.email == settings.bootstrap_admin_email))
        if existing:
            return
        session.add(User(email=settings.bootstrap_admin_email,
                         password_hash=hash_password(settings.bootstrap_admin_password),
                         role="admin"))
        await audit.record(session, "system", "bootstrap_admin.created",
                           settings.bootstrap_admin_email)
        await session.commit()
    if settings.bootstrap_admin_password == "change-me-now":
        log.warning("bootstrap admin is using the DEFAULT password — rotate it now")
```

```python file=backend/app/schemas.py
from datetime import datetime

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
```

```python file=backend/app/api/__init__.py
```

```python file=backend/app/api/auth.py
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import User
from app.schemas import LoginRequest, TokenResponse, UserOut
from app.security.deps import require_user
from app.security.passwords import verify_password
from app.security.tokens import create_token
from app.services import audit

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request,
                session: Annotated[AsyncSession, Depends(get_session)]) -> TokenResponse:
    settings = request.app.state.settings
    user = await session.scalar(select(User).where(User.email == body.email))
    ok = user is not None and verify_password(body.password, user.password_hash)
    await audit.record(session, body.email, "auth.login",
                       detail={"success": ok})
    await session.commit()
    if not ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    token = create_token(user.id, user.email, user.role,
                         settings.jwt_secret, settings.jwt_expires_min)
    return TokenResponse(access_token=token, expires_in=settings.jwt_expires_min * 60)


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[User, Depends(require_user)]) -> User:
    return user
```

```python file=backend/app/main.py
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.auth import router as auth_router
from app.config import Settings, get_settings
from app.db import build_engine, build_sessionmaker
from app.logging_setup import RequestIdMiddleware, setup_logging
from app.services.bootstrap import ensure_bootstrap_admin

log = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.engine = build_engine(settings.database_url)
        app.state.sessionmaker = build_sessionmaker(app.state.engine)
        await ensure_bootstrap_admin(app.state.sessionmaker, settings)
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
    app.include_router(auth_router)

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

## Tests (normal mode: must exist before validate)

```python file=backend/tests/conftest.py
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.db import Base, build_engine, build_sessionmaker
from app.main import create_app
from app.models import User
from app.security.passwords import hash_password
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
def app_settings():
    return test_settings()


@pytest.fixture
async def app(db_engine, app_settings):
    # httpx.ASGITransport does NOT run lifespan — wire app state explicitly.
    application = create_app(app_settings)
    application.state.settings = app_settings
    application.state.engine = db_engine
    application.state.sessionmaker = build_sessionmaker(db_engine)
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

```python file=backend/tests/test_auth.py
from sqlalchemy import func, select

from app.models import AuditLog, User
from app.security.passwords import hash_password, verify_password
from app.security.tokens import TokenError, create_token, decode_token
from app.services.bootstrap import ensure_bootstrap_admin
from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, test_settings


def test_password_roundtrip():
    stored = hash_password("s3cret!")
    assert verify_password("s3cret!", stored)
    assert not verify_password("wrong", stored)
    assert not verify_password("s3cret!", "garbage")


def test_token_roundtrip_and_expiry():
    token = create_token(1, "a@x.io", "admin", "k", expires_min=60)
    data = decode_token(token, "k")
    assert (data.user_id, data.email, data.role) == (1, "a@x.io", "admin")

    expired = create_token(1, "a@x.io", "admin", "k", expires_min=-1)
    try:
        decode_token(expired, "k")
        raise AssertionError("expired token accepted")
    except TokenError:
        pass


async def test_login_and_me(client):
    r = await client.post("/api/v1/auth/login",
                          json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200
    token = r.json()["access_token"]

    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == ADMIN_EMAIL
    assert me.json()["role"] == "admin"


async def test_wrong_password_401_and_audited(client, app):
    r = await client.post("/api/v1/auth/login",
                          json={"email": ADMIN_EMAIL, "password": "nope"})
    assert r.status_code == 401
    async with app.state.sessionmaker() as session:
        row = await session.scalar(
            select(AuditLog).where(AuditLog.action == "auth.login")
            .order_by(AuditLog.id.desc()))
        assert row is not None
        assert row.detail == {"success": False}


async def test_me_requires_token(client):
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    bad = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer junk"})
    assert bad.status_code == 401


async def test_bootstrap_admin_idempotent(db_engine):
    from app.db import build_sessionmaker
    maker = build_sessionmaker(db_engine)
    settings = test_settings()
    await ensure_bootstrap_admin(maker, settings)
    await ensure_bootstrap_admin(maker, settings)
    async with maker() as session:
        count = await session.scalar(select(func.count()).select_from(User)
                                     .where(User.email == ADMIN_EMAIL))
        assert count == 1
```

Notes: `pydantic[email]` is needed for `EmailStr` — add `email-validator` to requirements.
The audit row commits in the same transaction as the login attempt handling.

## Verification

1. `cd backend && python -m pytest -q` → all green.
2. Manual: `uvicorn app.main:app` → `POST /api/v1/auth/login` with bootstrap creds → token; `GET /api/v1/auth/me` with it → the admin user.

## Review Log

## Implementation Log

- 2026-07-12 — PAUSED mid-implement (user request). Files extracted to working tree
  (uncommitted). `pytest -q`: 16 passed, 1 FAILED — `test_schema.py::test_chunk_cascade_delete`
  (chunks not cascade-deleted on SQLite; fails even in isolation now, though it passed at
  atom-02 time). Suspect area: SQLite FK pragma vs passive_deletes on the shared in-memory
  engine. Resume: debug cascade test, then finish atom-04 validate/commit.

- 2026-07-17 — RESUMED. Root cause of `test_chunk_cascade_delete`: `build_engine` never
  issued `PRAGMA foreign_keys=ON` on SQLite connections, so `ON DELETE CASCADE`
  (relied on via `passive_deletes=True`) was a no-op. Fixed: `connect` event listener on
  `engine.sync_engine` sets the pragma for sqlite dialect only. Files touched:
  `backend/app/db.py`. Tests: `python -m pytest -q` → 17 passed. Deviation from atom code:
  none beyond db.py (atom-02 file) gaining the pragma listener.
- 2026-07-17 — VALIDATED. Suite 17/17 green. Manual verification executed against
  `uvicorn app.main:app` (sqlite oracle, alembic upgrade head first): POST /auth/login →
  token, GET /auth/me → admin user, /healthz + /readyz OK. No OPEN findings.
