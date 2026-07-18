import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import ChatMessage, ChatSession, User
from app.retrieval.service import RetrievedChunk, retrieve
from app.schemas import ChatStreamRequest
from app.security.deps import require_user
from app.security.ratelimit import rate_limit

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

SYSTEM_PROMPT = (
    "You are an enterprise knowledge assistant. Answer ONLY from the numbered sources "
    "below. Cite sources inline as [n]. If the sources do not contain the answer, say so "
    "plainly — never invent facts.\n\nSources:\n{sources}"
)


def _sources_block(chunks: list[RetrievedChunk]) -> str:
    return "\n".join(f"[{i}] ({c.filename}) {c.text[:1200]}"
                     for i, c in enumerate(chunks, start=1))


def _sources_payload(chunks: list[RetrievedChunk]) -> list[dict]:
    return [{"n": i, "document_id": str(c.document_id), "chunk_id": str(c.chunk_id),
             "filename": c.filename, "snippet": c.text[:300]}
            for i, c in enumerate(chunks, start=1)]


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/stream", dependencies=[Depends(rate_limit("chat"))])
async def chat_stream(body: ChatStreamRequest, request: Request,
                      user: Annotated[User, Depends(require_user)],
                      session: Annotated[AsyncSession, Depends(get_session)]):
    state = request.app.state

    if body.session_id is not None:
        chat_session = await session.get(ChatSession, body.session_id)
        if chat_session is None or chat_session.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
        session_id = chat_session.id
    else:
        chat_session = ChatSession(user_id=user.id, title=body.message[:60])
        session.add(chat_session)
        await session.flush()
        session_id = chat_session.id

    session.add(ChatMessage(session_id=session_id, role="user", content=body.message))
    await session.commit()

    chunks = await retrieve(session, state.vector_store, state.embedder,
                            state.settings, body.message)
    sources = _sources_payload(chunks)
    messages = [
        {"role": "system",
         "content": SYSTEM_PROMPT.format(sources=_sources_block(chunks) or "(none)")},
        {"role": "user", "content": body.message},
    ]

    async def generate():
        collected: list[str] = []
        truncated = False
        try:
            yield _sse("session", {"session_id": str(session_id)})
            async for token in state.llm.stream_chat(messages):
                collected.append(token)
                yield _sse("token", {"t": token})
            yield _sse("sources", sources)
            yield _sse("done", {})
        except BaseException:  # includes client-disconnect cancellation
            truncated = True
            raise
        finally:
            async with state.sessionmaker() as s:  # request session is closed by now
                s.add(ChatMessage(session_id=session_id, role="assistant",
                                  content="".join(collected).strip(),
                                  sources=sources, truncated=truncated))
                await s.commit()

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})
