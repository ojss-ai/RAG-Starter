# phase-05-clients

- Status: READY
- Inputs: `docs/srs.md` (READY), ADRs: ADR-0001
- Stack: python/fastapi/postgres/milvus/nextjs/react/typescript/tailwind · Mode: normal
- Depends on: phase-04
- Created: 2026-07-12

## 1. Goal

The system has its clients: the watcher daemon ships new/changed files resiliently from
watched folders, and the Next.js frontend delivers the login page, the streaming chat UI
with inline citations and session controls, and the admin dashboard (metrics, drag-drop
upload, searchable document ledger with delete).

## 2. Scope

| In this phase | Deferred to phase |
|---|---|
| FR-12, FR-13 (watcher) | — |
| UI surfaces for FR-6, FR-9, FR-10, FR-11, FR-14, FR-20 (APIs delivered in phases 2–4) | |

## 3. Work Breakdown

| # | Item (imperative) | Traces | Files/areas touched | Future atom? |
|---|---|---|---|---|
| 05.1 | Watcher daemon: `watchdog` observer + debounce, SQLite state cache (path, mtime, sha256), skip unchanged hashes, multipart upload with API key, exponential back-off retry queue, CLI entry (`python -m ragwatcher`) | FR-12, FR-13 | `watcher/ragwatcher/`, `watcher/tests/` | yes |
| 05.2 | Next.js scaffold: App Router, Tailwind v4, typed API client (JWT storage, SSE reader), login page + auth guard, layout/nav | FR-14 (UI), NFR-7 | `frontend/` | yes |
| 05.3 | Chat UI: streaming rendering from SSE, inline citation chips with source hover/panel, session list, new/clear session controls | FR-9, FR-10, FR-11 (UI) | `frontend/app/chat/` | yes |
| 05.4 | Admin dashboard: metrics cards + simple charts (counts by state, vector size, error rate), drag-drop upload (single/zip) with progress, document ledger table (search, paginate, delete with confirm) | FR-6, FR-20 (UI), FR-7 (UI) | `frontend/app/admin/` | yes |

## 4. Data & Schema Changes

None server-side. Watcher creates its local SQLite cache file on first run.

## 5. Risks & Edge Cases

| Risk / edge case | Traces | Mitigation / behavior |
|---|---|---|
| Editor writes trigger duplicate events | FR-12 | debounce window; hash check makes retries idempotent |
| API down for hours | FR-13 | persistent retry queue in SQLite; capped back-off, resumes on restart |
| Token expiry mid-session in UI | FR-14 | 401 interceptor redirects to login preserving route |
| Large ledger | FR-20 | server-side pagination + search |

## 6. Test Strategy

Watcher: `cd watcher && python -m pytest -q` — hash cache skip, retry back-off (fake
transport), event→upload flow with tmp dirs. Frontend: `npm run build` + `tsc --noEmit` as
the compile oracle; component logic kept in pure functions (SSE frame parser, citation
splitter) unit-tested with `node --test` via `tsx` — no browser E2E in v1 (documented).

## 7. Definition of Done

- [ ] Every item in §3 delivered by a COMMITTED atom
- [ ] Watcher + backend suites green; frontend builds clean; no OPEN HIGH findings
- [ ] FR-12/13 scenarios pass as tests; UI surfaces manually verifiable against running API
