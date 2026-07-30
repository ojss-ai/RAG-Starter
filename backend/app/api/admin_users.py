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
