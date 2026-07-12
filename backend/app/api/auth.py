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
