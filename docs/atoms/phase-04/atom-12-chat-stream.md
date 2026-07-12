# atom-12-chat-stream

- Status: DRAFT
- Phase: phase-04-chat (`docs/plans/phase-04-chat.md`, item §04.2)
- Traces: FR-9, FR-10, FR-19
- Depends on: atom-11
- Mode: normal
- Created: 2026-07-12

## Purpose

Grounded streaming chat works: `POST /api/v1/chat/stream` retrieves hybrid context, streams
LLM tokens as SSE `token` events, finishes with a `sources` event (numbered citations
resolvable to document metadata) and `done`, persists both turns (assistant turn carries its
sources; disconnects persist a truncated turn), and is rate-limited.

## Files

| Path | Action |
|---|---|
| `backend/app/llm/__init__.py`, `providers.py` | create |
| `backend/app/api/chat.py` | create |
| `backend/app/schemas.py` | modify (append ChatStreamRequest — see block) |
| `backend/app/main.py` | modify (llm in lifespan, chat router) |
| `backend/tests/conftest.py` | modify (fake llm on app.state) |
| `backend/tests/test_chat_stream.py` | create |

## Implementation

```python file=backend/app/llm/__init__.py
from typing import AsyncIterator, Protocol

from app.config import Settings


class LLMProvider(Protocol):
    def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]: ...


def get_llm_provider(settings: Settings) -> LLMProvider:
    from app.llm.providers import FakeLLMProvider, OpenAILLMProvider
    if settings.llm_provider == "fake":
        return FakeLLMProvider()
    if settings.llm_provider == "openai":
        return OpenAILLMProvider(settings.llm_api_base, settings.llm_api_key,
                                 settings.llm_model)
    raise ValueError(f"unknown llm provider: {settings.llm_provider}")
```

```python file=backend/app/llm/providers.py
import json
from typing import AsyncIterator

import httpx


class LLMError(Exception):
    pass


class FakeLLMProvider:
    """Deterministic offline provider: answers reference source [1] when sources exist
    (the system prompt contains 'Sources:'), matching how tests assert citations."""

    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        has_sources = any("Sources:" in m.get("content", "") for m in messages)
        if has_sources:
            reply = "Based on the provided sources, the answer is grounded in [1]."
        else:
            reply = "I could not find relevant sources for this question."
        for word in reply.split(" "):
            yield word + " "


class OpenAILLMProvider:
    """OpenAI-compatible /chat/completions with stream=true."""

    def __init__(self, api_base: str, api_key: str, model: str,
                 client: httpx.AsyncClient | None = None):
        self._model = model
        self._client = client or httpx.AsyncClient(
            base_url=api_base, headers={"Authorization": f"Bearer {api_key}"}, timeout=120)

    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        payload = {"model": self._model, "messages": messages, "stream": True}
        try:
            async with self._client.stream("POST", "/chat/completions",
                                           json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    delta = (json.loads(data)["choices"][0].get("delta") or {})
                    content = delta.get("content")
                    if content:
                        yield content
        except httpx.HTTPError as exc:
            raise LLMError(str(exc)) from exc
```

```python file=backend/app/api/chat.py
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
```

Append to `backend/app/schemas.py` (implement merges, then deletes the helper file):

```python file=backend/app/schemas_atom12_append.py
# --- APPEND to backend/app/schemas.py ---
import uuid

from pydantic import BaseModel, Field


class ChatStreamRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: uuid.UUID | None = None
```

`backend/app/main.py` — changes vs atom-10 version:

1. imports: `from app.api.chat import router as chat_router`,
   `from app.llm import get_llm_provider`
2. in lifespan after `app.state.embedder = ...`: `app.state.llm = get_llm_provider(settings)`
3. `app.include_router(chat_router)`

`backend/tests/conftest.py` — one change: in the `app` fixture, after
`application.state.task_queue = EagerTaskQueue()` add:

```python
from app.llm.providers import FakeLLMProvider
application.state.llm = FakeLLMProvider()
```

(import goes at the top of conftest with the others).

## Tests (normal mode: must exist before validate)

```python file=backend/tests/test_chat_stream.py
import json
import uuid

from sqlalchemy import select

from app.models import ChatMessage, ChatSession, Chunk, Document
from app.vectorstore import VectorItem


def _events(sse_text: str) -> list[tuple[str, dict | list]]:
    out = []
    for block in sse_text.strip().split("\n\n"):
        lines = dict(l.split(": ", 1) for l in block.split("\n") if ": " in l)
        if "event" in lines:
            out.append((lines["event"], json.loads(lines.get("data", "null"))))
    return out


async def _seed_policy_doc(app):
    async with app.state.sessionmaker() as session:
        doc = Document(id=uuid.uuid4(), path="/x/policy.txt", filename="policy.txt",
                       content_hash="h-pol", size_bytes=10, status="INDEXED")
        chunk = Chunk(id=uuid.uuid4(), document_id=doc.id, seq=0,
                      text="vacation policy grants twenty days of paid vacation")
        session.add_all([doc, chunk])
        await session.commit()
        [vec] = await app.state.embedder.embed([chunk.text])
        await app.state.vector_store.upsert([VectorItem(
            chunk_id=str(chunk.id), document_id=str(doc.id),
            partition_key="default", embedding=vec)])


async def test_stream_tokens_then_sources_then_done(client, app, user_headers):
    await _seed_policy_doc(app)
    r = await client.post("/api/v1/chat/stream", headers=user_headers,
                          json={"message": "how many vacation days do we get"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")

    events = _events(r.text)
    names = [e for e, _ in events]
    assert names[0] == "session"
    assert "token" in names
    assert names[-2:] == ["sources", "done"]
    assert names.index("sources") > max(i for i, n in enumerate(names) if n == "token")

    sources = dict(events)["sources"]
    assert sources[0]["n"] == 1
    assert sources[0]["filename"] == "policy.txt"
    assert uuid.UUID(sources[0]["document_id"])  # resolvable metadata (FR-10)

    answer = "".join(d["t"] for e, d in events if e == "token")
    assert "[1]" in answer  # inline citation


async def test_both_turns_persisted_with_sources(client, app, user_headers):
    await _seed_policy_doc(app)
    r = await client.post("/api/v1/chat/stream", headers=user_headers,
                          json={"message": "vacation days?"})
    session_id = dict(_events(r.text))["session"]["session_id"]

    async with app.state.sessionmaker() as s:
        msgs = (await s.scalars(select(ChatMessage)
                                .where(ChatMessage.session_id == uuid.UUID(session_id))
                                .order_by(ChatMessage.id))).all()
        assert [m.role for m in msgs] == ["user", "assistant"]
        assert msgs[1].sources and msgs[1].sources[0]["filename"] == "policy.txt"
        assert msgs[1].truncated is False


async def test_existing_session_reused_and_foreign_session_404(client, app,
                                                               user_headers,
                                                               admin_headers):
    r1 = await client.post("/api/v1/chat/stream", headers=user_headers,
                           json={"message": "first"})
    sid = dict(_events(r1.text))["session"]["session_id"]
    r2 = await client.post("/api/v1/chat/stream", headers=user_headers,
                           json={"message": "second", "session_id": sid})
    assert dict(_events(r2.text))["session"]["session_id"] == sid

    foreign = await client.post("/api/v1/chat/stream", headers=admin_headers,
                                json={"message": "hi", "session_id": sid})
    assert foreign.status_code == 404


async def test_chat_requires_auth_and_rate_limits(client, app, user_headers,
                                                  app_settings):
    assert (await client.post("/api/v1/chat/stream",
                              json={"message": "x"})).status_code == 401
    app_settings.rate_chat_rpm = 2
    for _ in range(2):
        assert (await client.post("/api/v1/chat/stream", headers=user_headers,
                                  json={"message": "x"})).status_code == 200
    r = await client.post("/api/v1/chat/stream", headers=user_headers,
                          json={"message": "x"})
    assert r.status_code == 429
    app_settings.rate_chat_rpm = 30


async def test_no_sources_answer_is_honest(client, app, user_headers):
    r = await client.post("/api/v1/chat/stream", headers=user_headers,
                          json={"message": "completely unknown topic"})
    events = _events(r.text)
    assert dict(events)["sources"] == []
    answer = "".join(d["t"] for e, d in events if e == "token")
    assert "could not find" in answer
```

Notes: the assistant turn is persisted in the generator's `finally` with a FRESH session —
the request-scoped session is closed once the response starts streaming. `BaseException`
catch is deliberate: client disconnects surface as CancelledError, which must still mark the
turn truncated before re-raising. The `session` SSE event leads the stream so clients learn
the session id created for a first message.

## Verification

1. `cd backend && python -m pytest -q` → all green.
2. Manual: `curl -N -X POST .../api/v1/chat/stream -H "Authorization: Bearer <t>" -d '{"message":"..."}' -H 'Content-Type: application/json'` → live token events, sources, done.

## Review Log

## Implementation Log
