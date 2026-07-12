# atom-05-rbac-api-keys

- Status: READY
- Phase: phase-02-security (`docs/plans/phase-02-security.md`, item §02.2)
- Traces: FR-15, FR-16, FR-17
- Depends on: atom-04
- Mode: normal
- Created: 2026-07-12

## Purpose

Authorization exists: `require_admin` guards admin routes, machine clients authenticate via
hashed `X-API-Key` with ingest-only scope, admins can create/revoke keys and create users —
all audited. A shared `Principal` abstraction lets the phase-03 upload endpoint accept
either an admin JWT or an ingest API key.

## Files

| Path | Action |
|---|---|
| `backend/app/security/deps.py` | modify (require_admin, api-key auth, Principal) |
| `backend/app/security/apikeys.py` | create |
| `backend/app/api/admin_keys.py`, `backend/app/api/admin_users.py` | create |
| `backend/app/schemas.py` | modify (key/user admin schemas) |
| `backend/app/main.py` | modify (routers) |
| `backend/tests/test_rbac_keys.py` | create |

## Implementation

```python file=backend/app/security/apikeys.py
import hashlib
import secrets

KEY_PREFIX = "rgs_"


def generate_api_key() -> tuple[str, str]:
    """Returns (plaintext, sha256-hash). Plaintext is shown exactly once."""
    plaintext = KEY_PREFIX + secrets.token_urlsafe(32)
    return plaintext, hash_api_key(plaintext)


def hash_api_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()
```

```python file=backend/app/security/deps.py
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import ApiKey, User
from app.security.apikeys import hash_api_key
from app.security.tokens import TokenError, decode_token

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    """Unified caller identity: a human user (JWT) or a machine key (X-API-Key)."""

    kind: str            # "user" | "api_key"
    id: str              # user id or api key id
    label: str           # email or key name (for audit/rate-limit keys)
    role: str = ""       # user role when kind == "user"
    scope: str = ""      # key scope when kind == "api_key"


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


async def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return user


async def _api_key_principal(session: AsyncSession, raw_key: str) -> Principal:
    row = await session.scalar(select(ApiKey).where(ApiKey.key_hash == hash_api_key(raw_key)))
    if row is None or row.revoked_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or revoked API key")
    return Principal(kind="api_key", id=str(row.id), label=row.name, scope=row.scope)


async def require_ingest(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    x_api_key: Annotated[str | None, Header()] = None,
) -> Principal:
    """Upload authorization (FR-16): an ingest-scoped API key OR an admin JWT."""
    if x_api_key:
        principal = await _api_key_principal(session, x_api_key)
        if principal.scope != "ingest":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Key lacks ingest scope")
        return principal
    if creds is not None:
        user = await get_current_user(request, creds, session)
        if user.role != "admin":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
        return Principal(kind="user", id=str(user.id), label=user.email, role=user.role)
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
```

```python file=backend/app/api/admin_keys.py
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.db import get_session
from app.models import ApiKey, User
from app.schemas import ApiKeyCreated, ApiKeyOut, CreateApiKeyRequest
from app.security.apikeys import generate_api_key
from app.security.deps import require_admin
from app.services import audit

router = APIRouter(prefix="/api/v1/admin/keys", tags=["admin"])


@router.post("", response_model=ApiKeyCreated, status_code=201)
async def create_key(body: CreateApiKeyRequest,
                     admin: Annotated[User, Depends(require_admin)],
                     session: Annotated[AsyncSession, Depends(get_session)]) -> ApiKeyCreated:
    plaintext, key_hash = generate_api_key()
    row = ApiKey(key_hash=key_hash, name=body.name, scope="ingest")
    session.add(row)
    await session.flush()
    await audit.record(session, admin.email, "api_key.created", body.name)
    await session.commit()
    return ApiKeyCreated(id=row.id, name=row.name, scope=row.scope, api_key=plaintext)


@router.get("", response_model=list[ApiKeyOut])
async def list_keys(admin: Annotated[User, Depends(require_admin)],
                    session: Annotated[AsyncSession, Depends(get_session)]) -> list[ApiKey]:
    rows = await session.scalars(select(ApiKey).order_by(ApiKey.id))
    return list(rows)


@router.delete("/{key_id}", status_code=204)
async def revoke_key(key_id: int,
                     admin: Annotated[User, Depends(require_admin)],
                     session: Annotated[AsyncSession, Depends(get_session)]) -> None:
    row = await session.get(ApiKey, key_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Key not found")
    if row.revoked_at is None:
        row.revoked_at = func.now()
        await audit.record(session, admin.email, "api_key.revoked", row.name)
        await session.commit()
```

```python file=backend/app/api/admin_users.py
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import User
from app.schemas import CreateUserRequest, UserOut
from app.security.deps import require_admin
from app.security.passwords import hash_password
from app.services import audit

router = APIRouter(prefix="/api/v1/admin/users", tags=["admin"])


@router.post("", response_model=UserOut, status_code=201)
async def create_user(body: CreateUserRequest,
                      admin: Annotated[User, Depends(require_admin)],
                      session: Annotated[AsyncSession, Depends(get_session)]) -> User:
    exists = await session.scalar(select(User).where(User.email == body.email))
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(email=body.email, password_hash=hash_password(body.password),
                role=body.role)
    session.add(user)
    await session.flush()
    await audit.record(session, admin.email, "user.created", body.email,
                       {"role": body.role})
    await session.commit()
    return user


@router.get("", response_model=list[UserOut])
async def list_users(admin: Annotated[User, Depends(require_admin)],
                     session: Annotated[AsyncSession, Depends(get_session)]) -> list[User]:
    rows = await session.scalars(select(User).order_by(User.id))
    return list(rows)
```

```python file=backend/app/schemas.py
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
```

```python file=backend/app/main.py
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.admin_keys import router as admin_keys_router
from app.api.admin_users import router as admin_users_router
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
    app.include_router(admin_keys_router)
    app.include_router(admin_users_router)

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

```python file=backend/tests/test_rbac_keys.py
from fastapi import Depends
from typing import Annotated

from app.security.deps import Principal, require_ingest


async def test_admin_routes_reject_plain_user(client, user_headers):
    r = await client.get("/api/v1/admin/users", headers=user_headers)
    assert r.status_code == 403
    r = await client.post("/api/v1/admin/keys", headers=user_headers,
                          json={"name": "nope"})
    assert r.status_code == 403


async def test_admin_creates_user_and_key(client, admin_headers, app):
    r = await client.post("/api/v1/admin/users", headers=admin_headers,
                          json={"email": "new@test.io", "password": "longenough1",
                                "role": "user"})
    assert r.status_code == 201
    assert r.json()["role"] == "user"

    dup = await client.post("/api/v1/admin/users", headers=admin_headers,
                            json={"email": "new@test.io", "password": "longenough1"})
    assert dup.status_code == 409

    k = await client.post("/api/v1/admin/keys", headers=admin_headers,
                          json={"name": "watcher-1"})
    assert k.status_code == 201
    assert k.json()["api_key"].startswith("rgs_")

    listed = await client.get("/api/v1/admin/keys", headers=admin_headers)
    assert listed.status_code == 200
    assert "api_key" not in listed.json()[0]  # plaintext never listed


def _ingest_probe(app):
    """Mount a scope probe route so require_ingest is exercised over HTTP."""
    if not any(r.path == "/test/ingest-probe" for r in app.routes):
        @app.post("/test/ingest-probe")
        async def probe(principal: Annotated[Principal, Depends(require_ingest)]):
            return {"kind": principal.kind, "label": principal.label}


async def test_api_key_scope_enforced(client, admin_headers, app):
    _ingest_probe(app)
    k = await client.post("/api/v1/admin/keys", headers=admin_headers,
                          json={"name": "watcher-2"})
    key = k.json()["api_key"]

    ok = await client.post("/test/ingest-probe", headers={"X-API-Key": key})
    assert ok.status_code == 200
    assert ok.json() == {"kind": "api_key", "label": "watcher-2"}

    # key must NOT open admin endpoints (FR-16)
    denied = await client.get("/api/v1/admin/keys", headers={"X-API-Key": key})
    assert denied.status_code == 401

    bad = await client.post("/test/ingest-probe", headers={"X-API-Key": "rgs_wrong"})
    assert bad.status_code == 401


async def test_revoked_key_rejected(client, admin_headers, app):
    _ingest_probe(app)
    k = await client.post("/api/v1/admin/keys", headers=admin_headers,
                          json={"name": "watcher-3"})
    key_id, key = k.json()["id"], k.json()["api_key"]

    assert (await client.delete(f"/api/v1/admin/keys/{key_id}",
                                headers=admin_headers)).status_code == 204
    r = await client.post("/test/ingest-probe", headers={"X-API-Key": key})
    assert r.status_code == 401


async def test_admin_jwt_can_ingest(client, admin_headers, user_headers, app):
    _ingest_probe(app)
    ok = await client.post("/test/ingest-probe", headers=admin_headers)
    assert ok.status_code == 200
    assert ok.json()["kind"] == "user"

    denied = await client.post("/test/ingest-probe", headers=user_headers)
    assert denied.status_code == 403
```

Notes: `revoke_key` uses `func.now()` so revocation time is DB-clock based. The probe route
is test-only and mounted idempotently per test app instance.

## Verification

1. `cd backend && python -m pytest -q` → all green.
2. Manual: create a key via `/docs` as admin → call an ingest-guarded route with `X-API-Key`.

## Review Log

## Implementation Log
