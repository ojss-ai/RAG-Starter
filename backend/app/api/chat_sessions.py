import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import ChatMessage, ChatSession, User
from app.schemas import ChatMessageOut, ChatSessionOut
from app.security.deps import require_user

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


async def _owned_session(session: AsyncSession, user: User,
                         session_id: uuid.UUID) -> ChatSession:
    chat_session = await session.get(ChatSession, session_id)
    if chat_session is None or chat_session.user_id != user.id:
        # 404 (not 403) so foreign session ids are not confirmed to exist
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return chat_session


@router.get("/sessions", response_model=list[ChatSessionOut])
async def list_sessions(user: Annotated[User, Depends(require_user)],
                        session: Annotated[AsyncSession, Depends(get_session)]):
    rows = await session.scalars(select(ChatSession)
                                 .where(ChatSession.user_id == user.id)
                                 .order_by(ChatSession.created_at.desc()))
    return list(rows)


@router.post("/sessions", response_model=ChatSessionOut, status_code=201)
async def create_session(user: Annotated[User, Depends(require_user)],
                         session: Annotated[AsyncSession, Depends(get_session)]):
    chat_session = ChatSession(user_id=user.id)
    session.add(chat_session)
    await session.commit()
    return chat_session


@router.get("/history/{session_id}", response_model=list[ChatMessageOut])
async def history(session_id: uuid.UUID,
                  user: Annotated[User, Depends(require_user)],
                  session: Annotated[AsyncSession, Depends(get_session)]):
    await _owned_session(session, user, session_id)
    rows = await session.scalars(select(ChatMessage)
                                 .where(ChatMessage.session_id == session_id)
                                 .order_by(ChatMessage.id))
    return list(rows)


@router.delete("/sessions/{session_id}", status_code=204)
async def clear_session(session_id: uuid.UUID,
                        user: Annotated[User, Depends(require_user)],
                        session: Annotated[AsyncSession, Depends(get_session)]) -> None:
    chat_session = await _owned_session(session, user, session_id)
    await session.delete(chat_session)  # messages cascade (schema atom-02)
    await session.commit()
