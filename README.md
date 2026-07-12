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

> Built on **AtomForge** by Suraj
