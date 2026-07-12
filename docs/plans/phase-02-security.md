# phase-02-security

- Status: READY
- Inputs: `docs/srs.md` (READY), ADRs: ADR-0001
- Stack: python/fastapi/postgres/milvus/nextjs/react/typescript/tailwind · Mode: normal
- Depends on: phase-01
- Created: 2026-07-12

## 1. Goal

Every later endpoint can be protected: users authenticate with email+password and get
expiring JWTs, roles (`admin`/`user`) are enforced by dependencies, machine clients use
revocable ingest-scoped API keys, privileged actions land in the append-only audit log, and
chat/upload routes are rate-limited. A bootstrap admin is seeded from env config.

## 2. Scope

| In this phase | Deferred to phase |
|---|---|
| FR-14 (auth, password hashing, JWT) | FR-18 upload validation → phase-03 (lives in upload endpoint) |
| FR-15 (RBAC admin/user), FR-16 (API keys, ingest scope) | login UI → phase-05 |
| FR-17 (audit log service), FR-19 (rate limiting) | |

## 3. Work Breakdown

| # | Item (imperative) | Traces | Files/areas touched | Future atom? |
|---|---|---|---|---|
| 02.1 | Password hashing (PBKDF2-HMAC, stdlib), JWT issue/verify, `POST /api/v1/auth/login`, `GET /api/v1/auth/me`, bootstrap-admin seeding on startup, failed/successful logins audited | FR-14, FR-17 | `backend/app/security/`, `backend/app/api/auth.py` | yes |
| 02.2 | RBAC dependencies (`require_user`, `require_admin`), API-key auth (`X-API-Key`, SHA-256 hash lookup, scope check), admin endpoints to create/revoke keys (audited), user management endpoint (create user, audited) | FR-15, FR-16, FR-17 | `backend/app/security/deps.py`, `backend/app/api/admin_keys.py`, `admin_users.py` | yes |
| 02.3 | Rate-limit middleware: in-memory token bucket per caller (user id / api key / IP), configurable rpm per route class (chat, upload), 429 with Retry-After; audit service helper | FR-19, FR-17 | `backend/app/security/ratelimit.py`, `backend/app/services/audit.py` | yes |

## 4. Data & Schema Changes

None (tables created in phase-01).

## 5. Risks & Edge Cases

| Risk / edge case | Traces | Mitigation / behavior |
|---|---|---|
| Token theft / long-lived JWTs | FR-14, NFR-4 | short expiry (configurable, default 60 min); secret from env only |
| API key leak | FR-16 | keys stored hashed; plaintext shown once at creation; revocation immediate |
| In-memory rate limiter across multiple workers | FR-19, NFR-3 | documented limitation; keyed interface allows Redis swap without endpoint changes |
| Bootstrap admin default password left in prod | NFR-4 | seeding logs a warning; `.env.example` documents rotation |

## 6. Test Strategy

Runner: `cd backend && python -m pytest -q`. Unit: hash/verify roundtrip, JWT expiry/claims,
token bucket math. Integration: login happy/wrong-password (audited), `require_admin` rejects
user role, API key upload-scope accepted / metrics-scope rejected, revoked key rejected,
429 after threshold.

## 7. Definition of Done

- [ ] Every item in §3 delivered by a COMMITTED atom
- [ ] Full suite green; no OPEN HIGH findings across this phase's atoms
- [ ] All FR-14…17, FR-19 acceptance scenarios pass as tests
