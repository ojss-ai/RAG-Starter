# RagStarter — 100M-Scale Enterprise RAG System

FastAPI + PostgreSQL + Milvus + Next.js RAG system: hybrid retrieval (TSVector + HNSW,
RRF-fused), streaming cited chat, admin dashboard, and a resilient folder-watcher daemon.
Built with [AtomForge](docs/srs.md) — see `docs/` for the SRS, phase plans, and atoms.

## Quick start

    cp .env.example .env                    # set secrets
    make up                                 # postgres + milvus via docker compose
    cd backend && python -m venv .venv && . .venv/Scripts/activate
    pip install -r requirements.txt -r requirements-dev.txt
    alembic upgrade head
    uvicorn app.main:app --reload           # http://localhost:8000/docs

Tests: `cd backend && python -m pytest -q`

## Frontend (Next.js)

    cd frontend && npm install
    cp .env.local.example .env.local        # points at http://localhost:8000
    npm run dev                             # http://localhost:3000

Sign in with the bootstrap admin from `.env`. Chat lives at `/chat`; the admin
dashboard (uploads, ledger, metrics) at `/admin`.
Oracle: `npm run typecheck && npm test && npm run build`

## Folder watcher daemon

    cd watcher && pip install -r requirements.txt
    # create an ingest API key in the admin dashboard first
    RAGWATCH_WATCH_DIR=/path/to/docs RAGWATCH_API_URL=http://localhost:8000 \
    RAGWATCH_API_KEY=rgs_... python -m ragwatcher          # or --once for a single scan

Unchanged files are never re-uploaded (SHA-256 cache in `.ragwatcher.db`);
API outages are retried with exponential back-off.
Tests: `cd watcher && python -m pytest -q`

## Production notes

- Set `RAG_VECTOR_BACKEND=milvus` (+ `pip install pymilvus`) and
  `RAG_EMBED_PROVIDER=openai` / `RAG_LLM_PROVIDER=openai` with real keys.
- Rate limiter and HTTP metrics are in-process: run a single uvicorn worker,
  or swap in Redis/Prometheus for multi-worker deployments.
- Uploaded files persist under `RAG_UPLOAD_DIR` (default `./data/uploads`) —
  mount a volume in containers.

> Built on **AtomForge** by Suraj
