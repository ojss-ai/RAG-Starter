# phase-03-ingestion

- Status: READY
- Inputs: `docs/srs.md` (READY), ADRs: ADR-0001
- Stack: python/fastapi/postgres/milvus/nextjs/react/typescript/tailwind · Mode: normal
- Depends on: phase-02
- Created: 2026-07-12

## 1. Goal

Documents flow end-to-end: an authenticated upload (admin JWT or ingest-scoped API key) is
validated, deduplicated by hash, stored, and processed asynchronously — extracted, chunked
with overlap, embedded in batches, and written to the vector store with the two-way UUID
mapping — with every state transition tracked and failures isolated. Deletion purges both
stores. The admin metrics endpoint reports corpus state.

## 2. Scope

| In this phase | Deferred to phase |
|---|---|
| FR-1…FR-7, FR-18, FR-20, NFR-2, NFR-6 | FR-8…11 (retrieval/chat) → phase-04 |
| Vector store gateway (Milvus impl + fake) | upload UI / ledger UI → phase-05 |

## 3. Work Breakdown

| # | Item (imperative) | Traces | Files/areas touched | Future atom? |
|---|---|---|---|---|
| 03.1 | Text extraction (txt/md/pdf), token-based chunker with overlap (Tokenizer interface, whitespace default), embedding provider interface (OpenAI-compatible httpx impl + deterministic fake), batch embed | FR-1, FR-2, NFR-8 | `backend/app/ingest/` | yes |
| 03.2 | VectorStore interface: `upsert(chunks)`, `delete(document_id)`, `search(vector, k, partition)`, `stats()`; Milvus impl (lazy pymilvus import, HNSW M=16/efConstruction=200, partition by `partition_key`, UUID scalar field) + in-memory fake with cosine search | FR-3, NFR-1, NFR-3, NFR-8 | `backend/app/vectorstore/` | yes |
| 03.3 | Upload endpoint (`POST /api/v1/admin/upload`): type/size validation, hash dedupe, zip expansion, persists document rows PENDING, dispatches ingestion worker via TaskQueue interface; worker pipeline drives PENDING→PROCESSING→INDEXED/FAILED, writes chunks + vectors, rollback on vector failure; audited | FR-4, FR-5, FR-6, FR-18, NFR-2, NFR-6, FR-17 | `backend/app/api/admin_upload.py`, `backend/app/ingest/pipeline.py`, `backend/app/services/tasks.py` | yes |
| 03.4 | `DELETE /api/v1/admin/documents/{id}` purging both stores atomically (audited); `GET /api/v1/admin/documents` ledger list (search/paginate); `GET /api/v1/admin/metrics` (counts by state, vector stats, error rate from in-process counters) | FR-7, FR-20, FR-17 | `backend/app/api/admin_documents.py`, `metrics.py` | yes |

## 4. Data & Schema Changes

None (tables created in phase-01). Milvus collection `chunks_v1` created on demand by the
gateway: fields (pk auto, `chunk_id` varchar, `document_id` varchar indexed, `partition_key`
varchar, `embedding` float_vector(dim from config)), HNSW index, partitions by key.

## 5. Risks & Edge Cases

| Risk / edge case | Traces | Mitigation / behavior |
|---|---|---|
| Embedding provider outage mid-document | FR-4, NFR-6 | document → FAILED with error recorded; vectors for that doc deleted (no partial index) |
| Zip bombs / oversized archives | FR-18 | per-entry and total size caps; entry count cap; unsupported entries reported |
| Duplicate upload race | FR-5 | unique constraint on content_hash; violation returns existing document reference |
| Delete while ingesting | FR-7 | status check; PROCESSING documents deleted after worker guard (best-effort vector purge) |

## 6. Test Strategy

Runner: `cd backend && python -m pytest -q`. Unit: chunker sizes/overlap, RRF-free — fake
embedder determinism, vector fake cosine. Integration: upload→INDEXED happy path (fake
providers), provider-down → FAILED with no vectors (NFR-6), duplicate hash acknowledged
without new job, zip with mixed entries, delete purges both stores, metrics counts, rejected
.exe/oversize before buffering.

## 7. Definition of Done

- [ ] Every item in §3 delivered by a COMMITTED atom
- [ ] Full suite green; no OPEN HIGH findings across this phase's atoms
- [ ] FR-1…7, FR-18, FR-20 acceptance scenarios pass as tests
