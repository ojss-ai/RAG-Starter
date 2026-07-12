# atom-06-rate-limit-audit

- Status: READY
- Phase: phase-02-security (`docs/plans/phase-02-security.md`, item §02.3)
- Traces: FR-19, FR-17
- Depends on: atom-05
- Mode: normal
- Created: 2026-07-12

## Purpose

Configurable per-caller rate limiting exists as a reusable dependency (token bucket keyed by
user/API-key/IP, 429 + Retry-After), and admins can read the audit trail
(`GET /api/v1/admin/audit`, paginated) — completing FR-17's visibility.

## Files

| Path | Action |
|---|---|
| `backend/app/security/ratelimit.py` | create |
| `backend/app/api/admin_audit.py` | create |
| `backend/app/schemas.py` | modify (audit schema) |
| `backend/app/main.py` | modify (router, limiter state) |
| `backend/tests/test_ratelimit_audit.py` | create |

## Implementation

```python file=backend/app/security/ratelimit.py
import time
from dataclasses import dataclass, field

from fastapi import HTTPException, Request
from fastapi.responses import Response


@dataclass
class _Bucket:
    tokens: float
    updated: float


@dataclass
class RateLimiter:
    """In-memory token bucket per (route_class, caller). Single-process only — the keyed
    interface is Redis-swappable without touching endpoints (plan §5 limitation)."""

    buckets: dict[str, _Bucket] = field(default_factory=dict)

    def check(self, key: str, rpm: int, now: float | None = None) -> tuple[bool, float]:
        """Returns (allowed, retry_after_seconds)."""
        now = time.monotonic() if now is None else now
        rate = rpm / 60.0
        b = self.buckets.get(key)
        if b is None:
            b = _Bucket(tokens=float(rpm), updated=now)
            self.buckets[key] = b
        b.tokens = min(float(rpm), b.tokens + (now - b.updated) * rate)
        b.updated = now
        if b.tokens >= 1.0:
            b.tokens -= 1.0
            return True, 0.0
        return False, (1.0 - b.tokens) / rate


def _caller_key(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    api_key = request.headers.get("x-api-key", "")
    if api_key:
        return f"key:{api_key[:16]}"
    if auth:
        return f"jwt:{auth[-24:]}"
    client = request.client.host if request.client else "unknown"
    return f"ip:{client}"


def rate_limit(route_class: str):
    """Dependency factory: `Depends(rate_limit("chat"))` / `Depends(rate_limit("upload"))`."""

    async def dependency(request: Request, response: Response) -> None:
        settings = request.app.state.settings
        rpm = {"chat": settings.rate_chat_rpm, "upload": settings.rate_upload_rpm}[route_class]
        limiter: RateLimiter = request.app.state.rate_limiter
        allowed, retry_after = limiter.check(f"{route_class}:{_caller_key(request)}", rpm)
        if not allowed:
            raise HTTPException(status_code=429, detail="Rate limit exceeded",
                                headers={"Retry-After": str(max(1, round(retry_after)))})

    return dependency
```

```python file=backend/app/api/admin_audit.py
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import AuditLog, User
from app.schemas import AuditOut
from app.security.deps import require_admin

router = APIRouter(prefix="/api/v1/admin/audit", tags=["admin"])


@router.get("", response_model=list[AuditOut])
async def list_audit(admin: Annotated[User, Depends(require_admin)],
                     session: Annotated[AsyncSession, Depends(get_session)],
                     limit: Annotated[int, Query(ge=1, le=200)] = 50,
                     offset: Annotated[int, Query(ge=0)] = 0) -> list[AuditLog]:
    rows = await session.scalars(
        select(AuditLog).order_by(AuditLog.id.desc()).limit(limit).offset(offset))
    return list(rows)
```

Append to `backend/app/schemas.py` (full replacement block below keeps the file complete):

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


class AuditOut(BaseModel):
    id: int
    actor: str
    action: str
    target: str
    detail: dict
    created_at: datetime

    model_config = {"from_attributes": True}
```

```python file=backend/app/main.py
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.admin_audit import router as admin_audit_router
from app.api.admin_keys import router as admin_keys_router
from app.api.admin_users import router as admin_users_router
from app.api.auth import router as auth_router
from app.config import Settings, get_settings
from app.db import build_engine, build_sessionmaker
from app.logging_setup import RequestIdMiddleware, setup_logging
from app.security.ratelimit import RateLimiter
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

```python file=backend/tests/test_ratelimit_audit.py
from fastapi import Depends

from app.security.ratelimit import RateLimiter, rate_limit


def test_token_bucket_math():
    rl = RateLimiter()
    t = 1000.0
    # 60 rpm → 1 token/s, bucket starts full with 60
    for _ in range(60):
        allowed, _ = rl.check("k", 60, now=t)
        assert allowed
    allowed, retry = rl.check("k", 60, now=t)
    assert not allowed
    assert 0 < retry <= 1.0
    # one second later exactly one token refilled
    allowed, _ = rl.check("k", 60, now=t + 1.0)
    assert allowed


def test_bucket_isolated_per_key():
    rl = RateLimiter()
    t = 0.0
    assert rl.check("a", 1, now=t)[0]
    assert not rl.check("a", 1, now=t)[0]
    assert rl.check("b", 1, now=t)[0]  # other caller unaffected


def _probe(app):
    if not any(r.path == "/test/limited" for r in app.routes):
        @app.get("/test/limited", dependencies=[Depends(rate_limit("chat"))])
        async def limited():
            return {"ok": True}


async def test_rate_limit_429_with_retry_after(client, app, app_settings):
    app_settings.rate_chat_rpm = 3
    _probe(app)
    for _ in range(3):
        assert (await client.get("/test/limited")).status_code == 200
    r = await client.get("/test/limited")
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) >= 1


async def test_audit_endpoint_admin_only_and_paginated(client, admin_headers, user_headers):
    assert (await client.get("/api/v1/admin/audit",
                             headers=user_headers)).status_code == 403
    r = await client.get("/api/v1/admin/audit?limit=5", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body) <= 5
    # the two logins from the fixtures are audited
    assert any(row["action"] == "auth.login" for row in body)
```

Notes: `Settings` is a pydantic model — mutating `app_settings.rate_chat_rpm` in the test
works because the dependency reads settings per-request from `app.state.settings`.

## Verification

1. `cd backend && python -m pytest -q` → all green.
2. Manual: hammer `/test/limited`-style route or chat (phase-04) past the limit → 429 + Retry-After.

## Review Log

## Implementation Log
