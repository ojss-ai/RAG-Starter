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
