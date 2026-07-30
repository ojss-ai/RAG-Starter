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
