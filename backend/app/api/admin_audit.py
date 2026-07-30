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
