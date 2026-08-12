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
