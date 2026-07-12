# ADR-0001 — Tech Stack & Development Mode

- Status: ACCEPTED
- Date: 2026-07-12
- Deciders: project owner (stack declared in base-requirement.txt); mode chosen by agent
  under the owner's "perform all steps" delegation.

## Context

SRS §8 declares the stack; the source requirement is explicit about every layer. AtomForge
requires the stack and a development mode (`tdd` | `normal`) to be fixed before planning.

## Decision

| Layer | Choice | Notes |
|---|---|---|
| Backend API | FastAPI (Python 3.12+, async) | SSE streaming, dependency-injected auth |
| Relational DB | PostgreSQL 16 | metadata, chat history, users, API keys, audit log; TSVector keyword search |
| Vector DB | Milvus 2.4 (standalone for dev, cluster-ready) | HNSW `M=16, efConstruction=200`; partitioned collections; UUID scalar field |
| Ingestion workers | FastAPI background tasks behind a `TaskQueue` interface | Celery-swappable later without touching call sites |
| Frontend | Next.js 15 (App Router) + React 19 + Tailwind CSS v4 + TypeScript | chat UI + admin dashboard |
| Watcher | Standalone Python daemon: `watchdog` + SQLite cache + `httpx` | ships in `watcher/`, no FastAPI dependency |
| Embeddings / LLM | Provider interface; OpenAI-compatible default, deterministic fake provider for dev/tests | SRS Open Q 1–2 |
| ORM / migrations | SQLAlchemy 2 (async) + Alembic | |
| Local orchestration | Docker Compose: postgres, milvus (etcd+minio), api | NFR-7 |

**Mode: `normal`** — implement, then tests before validation. Rationale: the codebase is
integration-heavy (DB, vector store, SSE plumbing) where test-first against unwritten
infrastructure produces churn; every atom still ships tests that must pass before
`validate`, and external services are faked per NFR-8.

**Test runner:** backend `python -m pytest -q` in `backend/` (and `watcher/`); frontend
`npm test` in `frontend/`. `state.json.testRunner` records the backend runner as primary.

## Consequences

- All plans/atoms comply with the installed nextjs/react/typescript/postgres/git skills.
- Milvus and embedding calls go through thin gateways so tests run without infrastructure.
- Celery adoption later = new `TaskQueue` implementation, no endpoint changes.
