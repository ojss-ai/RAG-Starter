# SRS — RagStarter: 100M-Scale Enterprise RAG System

- Status: READY
- Source: base-requirement.txt (superseded by this document)
- Date: 2026-07-12

> RULES: This document describes WHAT and WHY only. Requirements never name frameworks,
> libraries, file paths, schemas, or algorithms — declared technology goes ONLY in §8. Every
> requirement gets a stable ID (`FR-#`, `NFR-#`) and MUST be independently testable. Removed
> requirements are ~~struck through~~ with a date, never deleted — the SRS is also history.

## 1. Problem Statement

Enterprises hold vast document corpora (target: 100 million documents) that employees cannot
query effectively. This system provides Retrieval-Augmented Generation: documents are
ingested continuously (manually and from watched folders), indexed for hybrid
keyword + semantic search, and exposed through a chat interface that streams grounded,
cited answers. Administrators manage the corpus, monitor system health, and control access.
When this ships, users get sub-second, source-cited answers over the whole corpus, and
admins get an auditable, secure ingestion and management pipeline.

*Gap-filling note: the source document did not specify authentication, authorization,
audit, ingestion state tracking, rate limiting, or operational endpoints. FR-14…FR-20 and
several NFRs were added to close those gaps (per project owner's instruction).*

## 2. In Scope / Out of Scope

| In scope | Out of scope (explicitly) |
|---|---|
| Document ingestion pipeline (chunk → embed → index) | Training or fine-tuning models |
| Hybrid retrieval (keyword + vector, fused ranking) | Non-text media (images, audio, video) |
| Streaming chat with inline source citations | Mobile native apps |
| Admin dashboard: metrics, upload, document ledger | Multi-datacenter replication |
| Folder-watcher daemon with resilient uploads | Billing / usage metering |
| Authentication, role-based access, audit logging | SSO/SAML federation (future) |
| Local dev orchestration for all backing services | Production IaC / Kubernetes manifests |

## 3. Actors

| Actor | Description |
|---|---|
| End User | Authenticated employee; asks questions in the chat UI, reads cited answers |
| Admin | Manages documents, monitors metrics, manages users; full dashboard access |
| Watcher Daemon | Non-human client on file servers; uploads new/changed files via API key |
| Ingestion Worker | Internal async process; chunks, embeds, and indexes uploaded documents |

## 4. Functional Requirements

### Ingestion & Indexing

| ID | Requirement (imperative, testable) | Priority |
|---|---|---|
| FR-1 | The system MUST split ingested document text into fixed-size chunks (default 512 tokens) with a configurable overlapping window (default 10%). | MUST |
| FR-2 | The system MUST generate vector embeddings for chunks in batches via a configurable embedding provider. | MUST |
| FR-3 | The system MUST maintain a two-way mapping between relational records (file path, dates, content hash, chunk map, UUID) and vector records (embedding + the same UUID as a scalar field), so either side can resolve the other. | MUST |
| FR-4 | The system MUST track every document through explicit ingestion states (PENDING → PROCESSING → INDEXED / FAILED) and expose the state per document. *(gap-fill)* | MUST |
| FR-5 | The system MUST reject duplicate ingestion: a file whose content hash already exists is acknowledged but not re-processed. | MUST |
| FR-6 | Admins MUST be able to upload single documents (PDF/TXT/MD) and batch archives (.zip) through the dashboard; archives are unpacked and each entry ingested individually. | MUST |
| FR-7 | Deleting a document MUST purge it atomically from both the relational store and the vector store (no orphans on either side). | MUST |

### Retrieval & Chat

| ID | Requirement | Priority |
|---|---|---|
| FR-8 | The system MUST answer chat queries using hybrid retrieval: keyword search in the relational store and semantic search in the vector store, merged by reciprocal-rank fusion. | MUST |
| FR-9 | Chat responses MUST stream token-by-token to the client in real time. | MUST |
| FR-10 | Every generated answer MUST carry inline citations resolvable to the source documents' metadata. | MUST |
| FR-11 | The system MUST persist chat history per session and return it on request; users can clear the active session or start a new one. | MUST |

### Watcher Daemon

| ID | Requirement | Priority |
|---|---|---|
| FR-12 | A standalone watcher process MUST detect file creation/modification in configured folders and upload the files to the ingestion API. | MUST |
| FR-13 | The watcher MUST keep a local state cache (path, modified time, content hash) and skip files whose hash is unchanged; interrupted uploads MUST resume via automatic exponential back-off retries. | MUST |

### Security & Access Control *(gap-fill)*

| ID | Requirement | Priority |
|---|---|---|
| FR-14 | The system MUST authenticate human users with credentials and issue expiring session tokens; passwords are stored only as strong one-way hashes. | MUST |
| FR-15 | The system MUST enforce role-based access: `admin` and `user` roles. Admin endpoints (upload, delete, metrics, ledger, user management) MUST reject non-admin callers. | MUST |
| FR-16 | Machine clients (watcher) MUST authenticate with revocable API keys scoped to ingestion only; API keys MUST NOT grant access to chat, ledger, or metrics. | MUST |
| FR-17 | The system MUST record an append-only audit log of privileged actions (login, upload, delete, key issuance/revocation, role changes) with actor, action, target, and timestamp. | MUST |
| FR-18 | The system MUST validate uploads: allowed types (PDF/TXT/MD/ZIP), configurable max file size, and reject anything else before buffering to disk. | MUST |
| FR-19 | The system MUST rate-limit chat and upload endpoints per caller with configurable thresholds; excess requests receive an explicit throttling response. | MUST |

### Operations *(gap-fill)*

| ID | Requirement | Priority |
|---|---|---|
| FR-20 | The system MUST expose liveness/readiness endpoints and an admin metrics endpoint reporting document counts by state, vector collection size, and API error rates. | MUST |

## 5. Non-Functional Requirements

| ID | Requirement | Measure |
|---|---|---|
| NFR-1 | Retrieval latency at 100M-vector scale | p95 vector search < 1s (index tuned for memory-efficient approximate search; collections partitioned to avoid full scans) |
| NFR-2 | Ingestion is non-blocking | Upload API acknowledges < 2s; chunk/embed/index runs async in workers |
| NFR-3 | Horizontal scalability | Stateless API processes; vector store shards/partitions by tenant/date/category |
| NFR-4 | Security baseline *(gap-fill)* | Secrets only via environment/config, never in code; all list/detail queries parameterized; CORS restricted to configured origins |
| NFR-5 | Observability *(gap-fill)* | Structured (JSON) logs with request IDs; every 5xx logged with context |
| NFR-6 | Consistency of the dual store | A failed vector write rolls back or marks the document FAILED — never a half-indexed document reported as INDEXED |
| NFR-7 | Local developer experience | One command brings up all backing services for development |
| NFR-8 | Test coverage *(gap-fill)* | Every FR has automated tests; external services (LLM, embeddings, vector DB) are mockable in tests |

## 6. Acceptance Scenarios (Given / When / Then)

```gherkin
Scenario: FR-1/FR-2/FR-3 happy path — document becomes searchable
  Given an authenticated admin and a 3-page text document
  When the admin uploads it and the ingestion worker completes
  Then the relational store holds the document with hash, UUID and chunk map,
    the vector store holds one embedding per chunk tagged with the same UUID,
    and the document state is INDEXED

Scenario: FR-4/NFR-6 failure path — embedding provider is down
  Given the embedding provider returns errors
  When a document is ingested
  Then the document state becomes FAILED with the error recorded,
    and no partial vectors for it exist in the vector store

Scenario: FR-5 duplicate upload
  Given a document already INDEXED with hash H
  When any client uploads a file with the same hash H
  Then the API acknowledges with the existing document reference
    and no new ingestion job is created

Scenario: FR-6 zip batch upload
  Given an admin uploads a .zip containing 3 supported files and 1 unsupported file
  When ingestion completes
  Then 3 documents reach INDEXED and the unsupported entry is reported as rejected

Scenario: FR-7 delete purges both stores
  Given an INDEXED document
  When an admin deletes it
  Then its relational rows and its vectors are both gone
    and the deletion is in the audit log (FR-17)

Scenario: FR-8/FR-10 grounded answer with citations
  Given documents about "vacation policy" are INDEXED
  When a user asks "how many vacation days do I get?"
  Then retrieval merges keyword and vector results by rank fusion
    and the streamed answer includes citations resolving to those documents

Scenario: FR-9 streaming
  Given a user sends a chat query
  When the answer is generated
  Then the client receives incremental token events, then a final event with sources

Scenario: FR-11 history and reset
  Given a session with 4 turns
  When the user requests history, then clears the session
  Then 4 turns are returned, and afterwards the session has no turns

Scenario: FR-12/FR-13 watcher happy + failure path
  Given the watcher monitors a folder and the API is briefly unreachable
  When a new file appears
  Then the watcher records its hash locally, retries with back-off,
    eventually uploads it once, and never re-uploads an unchanged file

Scenario: FR-14 failed login
  Given a registered user
  When they authenticate with a wrong password
  Then access is denied, no token is issued, and the attempt is audit-logged

Scenario: FR-15 role enforcement
  Given an authenticated non-admin user
  When they call any admin endpoint
  Then the request is rejected with a permission error

Scenario: FR-16 API key scope
  Given a valid watcher API key
  When it calls the upload endpoint, then the metrics endpoint
  Then upload succeeds and metrics is rejected

Scenario: FR-18 upload validation
  Given an admin uploads a 2GB .exe file
  When the API validates it
  Then it is rejected before any buffering to permanent storage

Scenario: FR-19 rate limiting
  Given a caller exceeding the chat threshold
  When the next request arrives inside the window
  Then it receives a throttling response and is not processed

Scenario: FR-20 metrics
  Given 5 INDEXED, 1 FAILED, 2 PENDING documents
  When an admin requests metrics
  Then counts by state, vector collection size, and error rates are returned
```

## 7. Open Questions

| # | Question | Blocking? | Resolution |
|---|---|---|---|
| 1 | Which LLM provider for answer generation? | no | Provider-agnostic interface; OpenAI-compatible API default, configurable via env. |
| 2 | Embedding model choice? | no | Configurable; default OpenAI `text-embedding-3-small` (1536-dim); mockable offline provider for dev/tests. |
| 3 | Multi-tenancy required? | no | Single-tenant v1; vector partitioning by category/date keeps the door open. |
| 4 | User self-registration or admin-provisioned? | no | Admin-provisioned users v1 (enterprise assumption); a bootstrap admin is seeded from env config. |

## 8. Tech Stack (declared)

Declared by the requirement source; `define-stack` confirms into `state.json` and ADR-0001.

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router) + React, Tailwind CSS |
| Backend API | FastAPI (Python, async) |
| Relational DB | PostgreSQL (metadata, chat history, users, audit, config) |
| Vector DB | Milvus distributed cluster (HNSW, partitioned collections) |
| Ingestion workers | Async background workers (FastAPI background tasks; Celery-ready design) |
| Keyword search | PostgreSQL full-text (TSVector) / trigram |
| Result fusion | Reciprocal Rank Fusion (RRF) |
| Watcher | Python daemon using `watchdog`, local SQLite state cache |
| Streaming | Server-Sent Events (SSE) |
| Local orchestration | Docker Compose (PostgreSQL, Milvus, API) |

## 9. Readiness

- [x] User ran `mark-ready srs` 2026-07-12 (pre-authorized: "perform all our steps")
