# atom-13-sessions-history

- Status: COMMITTED
- Phase: phase-04-chat (`docs/plans/phase-04-chat.md`, item §04.3)
- Traces: FR-11, FR-15
- Depends on: atom-12
- Mode: normal
- Created: 2026-07-12

## Purpose

Session management completes FR-11: list own sessions, create a new one, fetch a session's
history (owner-scoped — admins are NOT exempt, chat privacy per plan §5), and clear a
session (cascade-deletes its messages).

## Files

| Path | Action |
|---|---|
| `backend/app/api/chat_sessions.py` | create |
| `backend/app/schemas.py` | modify (append session/message schemas — see block) |
| `backend/app/main.py` | modify (router) |
| `backend/tests/test_chat_sessions.py` | create |

## Implementation

```python file=backend/app/api/chat_sessions.py
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
```

Append to `backend/app/schemas.py` (implement merges, then deletes the helper file):

```python file=backend/app/schemas_atom13_append.py
# --- APPEND to backend/app/schemas.py ---
import uuid
from datetime import datetime

from pydantic import BaseModel


class ChatSessionOut(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageOut(BaseModel):
    id: int
    role: str
    content: str
    sources: list
    truncated: bool
    created_at: datetime

    model_config = {"from_attributes": True}
```

`backend/app/main.py` — changes vs atom-12 version:

1. import: `from app.api.chat_sessions import router as chat_sessions_router`
2. `app.include_router(chat_sessions_router)`

## Tests (normal mode: must exist before validate)

```python file=backend/tests/test_chat_sessions.py
import uuid


async def _talk(client, headers, message, session_id=None):
    body = {"message": message}
    if session_id:
        body["session_id"] = session_id
    r = await client.post("/api/v1/chat/stream", headers=headers, json=body)
    assert r.status_code == 200
    for block in r.text.split("\n\n"):
        if block.startswith("event: session"):
            import json
            return json.loads(block.split("\ndata: ", 1)[1])["session_id"]
    raise AssertionError("no session event in stream")


async def test_history_four_turns_then_clear(client, user_headers):
    sid = await _talk(client, user_headers, "first question")
    await _talk(client, user_headers, "second question", session_id=sid)

    r = await client.get(f"/api/v1/chat/history/{sid}", headers=user_headers)
    assert r.status_code == 200
    msgs = r.json()
    assert len(msgs) == 4  # 2 user + 2 assistant
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]

    assert (await client.delete(f"/api/v1/chat/sessions/{sid}",
                                headers=user_headers)).status_code == 204
    assert (await client.get(f"/api/v1/chat/history/{sid}",
                             headers=user_headers)).status_code == 404


async def test_new_session_endpoint_and_listing(client, user_headers):
    r = await client.post("/api/v1/chat/sessions", headers=user_headers)
    assert r.status_code == 201
    sid = r.json()["id"]

    listed = await client.get("/api/v1/chat/sessions", headers=user_headers)
    assert sid in [s["id"] for s in listed.json()]


async def test_sessions_are_private_even_from_admin(client, user_headers, admin_headers):
    sid = await _talk(client, user_headers, "private question")
    assert (await client.get(f"/api/v1/chat/history/{sid}",
                             headers=admin_headers)).status_code == 404
    assert (await client.delete(f"/api/v1/chat/sessions/{sid}",
                                headers=admin_headers)).status_code == 404
    # unknown id also 404s (no existence oracle)
    assert (await client.get(f"/api/v1/chat/history/{uuid.uuid4()}",
                             headers=user_headers)).status_code == 404


async def test_endpoints_require_auth(client):
    assert (await client.get("/api/v1/chat/sessions")).status_code == 401
    assert (await client.post("/api/v1/chat/sessions")).status_code == 401
```

## Verification

1. `cd backend && python -m pytest -q` → all green.
2. Manual: chat via `/docs`, list sessions, fetch history, delete, fetch again → 404.

## Review Log

- 2026-07-17 — review-atom: freshness ✓ (chat stream + models as landed in atom-12; cascade delete verified working since atom-04 fk-pragma fix), completeness ✓, traceability ✓ (FR-11/15 / plan §04.3). Certified READY.

## Implementation Log

- 2026-07-17 — Implemented per atom (helper merged + deleted; main.py delta applied).
  Zero deviations. `pytest -q` → 61 passed.
- 2026-07-17 — VALIDATED. History (4 turns), cascade clear → 404, owner-privacy incl.
  admin, no-existence-oracle 404s, auth gates all green over HTTP. No OPEN findings.
  review-change clean.
