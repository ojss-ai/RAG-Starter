# phase-04-chat

- Status: READY
- Inputs: `docs/srs.md` (READY), ADRs: ADR-0001
- Stack: python/fastapi/postgres/milvus/nextjs/react/typescript/tailwind · Mode: normal
- Depends on: phase-03
- Created: 2026-07-12

## 1. Goal

Users get grounded, cited, streaming answers: a chat query runs hybrid retrieval (keyword in
PostgreSQL + vector in the vector store, merged by RRF), the LLM streams tokens over SSE
with a final sources event, citations resolve to document metadata, and history is persisted
per session with clear/new-session support.

## 2. Scope

| In this phase | Deferred to phase |
|---|---|
| FR-8, FR-9, FR-10, FR-11, NFR-1 (query path), NFR-3 | chat UI rendering → phase-05 |

## 3. Work Breakdown

| # | Item (imperative) | Traces | Files/areas touched | Future atom? |
|---|---|---|---|---|
| 04.1 | Retrieval service: keyword search (PG `websearch_to_tsquery` + `ts_rank`; LIKE fallback on SQLite), vector search via VectorStore, RRF merge (k=60), top-N context assembly with source metadata | FR-8, NFR-1 | `backend/app/retrieval/` | yes |
| 04.2 | LLM provider interface (OpenAI-compatible streaming via httpx + deterministic fake); `POST /api/v1/chat/stream` SSE: token events then final `sources` event; grounded prompt with numbered citations; rate-limited; persists both turns | FR-9, FR-10, FR-19 | `backend/app/llm/`, `backend/app/api/chat.py` | yes |
| 04.3 | Sessions & history: `GET /api/v1/chat/history/{session_id}` (owner-scoped), `POST /api/v1/chat/sessions` (new), `DELETE /api/v1/chat/sessions/{session_id}` (clear); messages store sources JSONB | FR-11, FR-15 | `backend/app/api/chat_sessions.py` | yes |

## 4. Data & Schema Changes

None (tables created in phase-01).

## 5. Risks & Edge Cases

| Risk / edge case | Traces | Mitigation / behavior |
|---|---|---|
| No relevant documents retrieved | FR-10 | answer states no sources found; empty sources event; no fabricated citations |
| Client disconnects mid-stream | FR-9 | generator cancellation handled; partial turn still persisted with `truncated` flag |
| Cross-user session access | FR-11, FR-15 | history/clear verify session ownership; admins are not exempt (privacy) |
| LLM provider outage | NFR-5 | SSE `error` event; 502 semantics; logged with request ID |

## 6. Test Strategy

Runner: `cd backend && python -m pytest -q`. Unit: RRF math (known ranks → known fusion),
prompt assembly includes numbered sources. Integration (fake LLM/embedder/vector store):
stream yields token events then sources event; citations resolve to seeded documents;
history returns 4 turns then clears; foreign session → 404/403; rate limit 429.

## 7. Definition of Done

- [ ] Every item in §3 delivered by a COMMITTED atom
- [ ] Full suite green; no OPEN HIGH findings across this phase's atoms
- [ ] FR-8…11 acceptance scenarios pass as tests
