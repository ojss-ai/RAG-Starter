# phase-01-foundation

- Status: READY
- Inputs: `docs/srs.md` (READY), ADRs: ADR-0001
- Stack: python/fastapi/postgres/milvus/nextjs/react/typescript/tailwind · Mode: normal
- Depends on: none
- Created: 2026-07-12

> RULES: A phase is a shippable, testable slice. This document says HOW at phase granularity;
> the atoms carry the actual code. Every item traces to FR/NFR ids; every design element that
> traces to nothing gets deleted (YAGNI). Skill-file MUSTs are binding on everything here.

## 1. Goal

The monorepo skeleton exists and runs: a FastAPI app with typed config, structured JSON
logging with request IDs, liveness/readiness endpoints, the complete PostgreSQL schema under
Alembic migrations, and Docker Compose bringing up PostgreSQL + Milvus + API with one
command. The pytest harness runs green against an in-memory database.

## 2. Scope

| In this phase | Deferred to phase |
|---|---|
| NFR-4, NFR-5, NFR-7, NFR-8 (foundations) | FR-14…17, FR-19 → phase-02 |
| DB schema for ALL later phases (users, api_keys, audit_log, documents, chunks, chat) | FR-1…7, FR-18, FR-20 → phase-03 |
| Liveness/readiness endpoints (NFR-5 surface; full metrics = FR-20 → phase-03) | FR-8…11 → phase-04 · FR-12, 13 + UI → phase-05 |

## 3. Work Breakdown

| # | Item (imperative) | Traces | Files/areas touched | Future atom? |
|---|---|---|---|---|
| 01.1 | Scaffold repo layout (`backend/`, `frontend/`, `watcher/`, root README, .gitignore, .gitattributes, .env.example), FastAPI app factory, pydantic-settings config, JSON logging middleware with request IDs, `/healthz` + `/readyz` | NFR-4, NFR-5, NFR-7 | root, `backend/app/` | yes |
| 01.2 | Full relational schema via SQLAlchemy 2 async models + Alembic migration: users, api_keys, audit_log, documents, chunks, chat_sessions, chat_messages (+ TSVector column & GIN index on chunks, FK indexes) | FR-3, FR-4, FR-11, FR-14, FR-16, FR-17 (schema only), NFR-1 | `backend/app/models/`, `backend/alembic/` | yes |
| 01.3 | Docker Compose (postgres:16, milvus standalone + etcd + minio, api service) + Makefile targets + pytest harness (async engine on SQLite in-memory, app fixture) | NFR-7, NFR-8 | `docker-compose.yml`, `backend/tests/` | yes |

## 4. Data & Schema Changes

Initial Alembic migration creates: `users` (id, email unique, password_hash, role, created_at),
`api_keys` (id, key_hash, name, scope, revoked_at, created_at),
`audit_log` (id, actor, action, target, detail, created_at — append-only),
`documents` (id UUID, path, filename, content_hash unique, size, mime, status, error,
partition_key, created_at, updated_at),
`chunks` (id UUID, document_id FK→documents indexed, seq, text, ts tsvector GIN-indexed),
`chat_sessions` (id UUID, user_id FK indexed, title, created_at),
`chat_messages` (id, session_id FK indexed, role, content, sources JSONB, created_at).

## 5. Risks & Edge Cases

| Risk / edge case | Traces | Mitigation / behavior |
|---|---|---|
| TSVector/GIN are PG-only; tests run on SQLite | NFR-8 | dialect-guarded DDL: tsvector column + GIN index created only on PostgreSQL; keyword search falls back to LIKE on SQLite |
| Milvus not running during dev/tests | NFR-8 | no Milvus dependency in this phase; gateway lands in phase-03 behind an interface |
| Windows CRLF churn | NFR-7 | `.gitattributes` normalizes line endings |

## 6. Test Strategy

Runner: `cd backend && python -m pytest -q`. Unit: config loading, logging middleware sets
request ID. Integration (async test client + SQLite): `/healthz` 200, `/readyz` reflects DB
connectivity, migration models create cleanly (`metadata.create_all` smoke).

## 7. Definition of Done

- [ ] Every item in §3 delivered by a COMMITTED atom
- [ ] Full suite green; no OPEN HIGH findings across this phase's atoms
- [ ] `docker compose up` + `alembic upgrade head` yields a working `/readyz` (documented; compose config validated)
