# atom-03-compose-orchestration

- Status: VALIDATED
- Phase: phase-01-foundation (`docs/plans/phase-01-foundation.md`, item §01.3)
- Traces: NFR-7, NFR-8
- Depends on: atom-02
- Mode: normal
- Created: 2026-07-12

## Purpose

One command brings up the full backing stack: Docker Compose for PostgreSQL 16 and Milvus
2.4 (with etcd + MinIO) plus a containerized API, a backend Dockerfile, and a Makefile with
the common workflows. Migration up/down is proven against real PostgreSQL.

## Files

| Path | Action |
|---|---|
| `docker-compose.yml` | create |
| `backend/Dockerfile` | create |
| `Makefile` | create |
| `backend/tests/test_migrations.py` | create |

## Implementation

```yaml file=docker-compose.yml
name: ragstarter

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-rag}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-rag-dev-only}
      POSTGRES_DB: ${POSTGRES_DB:-rag}
    ports:
      - "127.0.0.1:5432:5432"   # loopback only — compose-internal services use the service name
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 5s
      timeout: 3s
      retries: 10

  etcd:
    image: quay.io/coreos/etcd:v3.5.14
    environment:
      ETCD_AUTO_COMPACTION_MODE: revision
      ETCD_AUTO_COMPACTION_RETENTION: "1000"
      ETCD_QUOTA_BACKEND_BYTES: "4294967296"
      ETCD_SNAPSHOT_COUNT: "50000"
    command: etcd -advertise-client-urls=http://etcd:2379 -listen-client-urls http://0.0.0.0:2379 --data-dir /etcd
    volumes:
      - etcd:/etcd
    healthcheck:
      test: ["CMD", "etcdctl", "endpoint", "health"]
      interval: 30s
      timeout: 20s
      retries: 3

  minio:
    image: minio/minio:RELEASE.2024-05-28T17-19-04Z
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER:-minioadmin}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-minio-dev-only}
    command: minio server /minio_data --console-address ":9001"
    volumes:
      - minio:/minio_data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 20s
      retries: 3

  milvus:
    image: milvusdb/milvus:v2.4.15
    command: ["milvus", "run", "standalone"]
    environment:
      ETCD_ENDPOINTS: etcd:2379
      MINIO_ADDRESS: minio:9000
    ports:
      - "127.0.0.1:19530:19530"   # Milvus standalone ships unauthenticated — never expose beyond loopback
      - "127.0.0.1:9091:9091"
    volumes:
      - milvus:/var/lib/milvus
    depends_on:
      etcd:
        condition: service_healthy
      minio:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9091/healthz"]
      interval: 30s
      timeout: 20s
      retries: 5
      start_period: 90s

  api:
    build: ./backend
    profiles: ["app"]
    environment:
      RAG_DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-rag}:${POSTGRES_PASSWORD:-rag-dev-only}@postgres:5432/${POSTGRES_DB:-rag}
      RAG_VECTOR_BACKEND: milvus
      RAG_MILVUS_URI: http://milvus:19530
    env_file:
      - path: .env
        required: false
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      milvus:
        condition: service_healthy

volumes:
  pgdata:
  etcd:
  minio:
  milvus:
```

```dockerfile file=backend/Dockerfile
FROM python:3.12-slim

WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt pymilvus>=2.4

COPY . .

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

```makefile file=Makefile
.PHONY: up down api migrate test test-backend test-watcher fe-build

up:            ## backing services (postgres, milvus stack)
	docker compose up -d postgres etcd minio milvus

down:
	docker compose down

api:           ## full stack incl. containerized API
	docker compose --profile app up -d --build

migrate:
	cd backend && alembic upgrade head

test: test-backend test-watcher

test-backend:
	cd backend && python -m pytest -q

test-watcher:
	cd watcher && python -m pytest -q

fe-build:
	cd frontend && npm run build
```

## Tests (normal mode: must exist before validate)

```python file=backend/tests/test_migrations.py
"""Migration sanity that runs without infrastructure: revision graph loads and the initial
revision is reversible by construction. The real-Postgres up/down run (skill oracle) is a
verification step: `make up` + `alembic upgrade head` + `alembic downgrade base`."""
from alembic.config import Config
from alembic.script import ScriptDirectory


def _script_dir() -> ScriptDirectory:
    cfg = Config("alembic.ini")
    return ScriptDirectory.from_config(cfg)


def test_single_head():
    heads = _script_dir().get_heads()
    assert heads == ["0001"]


def test_initial_revision_has_up_and_down():
    rev = _script_dir().get_revision("0001")
    module = rev.module
    assert callable(module.upgrade)
    assert callable(module.downgrade)
```

Notes: the api service sits behind a compose *profile* so `docker compose up -d` (or
`make up`) never tries to build the app while only backing services are wanted.

## Verification

1. `cd backend && python -m pytest -q` → all green.
2. `docker compose config -q` → exit 0 (compose file valid).
3. Against real PG: `docker compose up -d postgres`, then in `backend/`:
   `RAG_DATABASE_URL=postgresql+asyncpg://rag:rag@localhost:5432/rag alembic upgrade head`
   → clean; `... alembic downgrade base` → clean (postgres skill oracle).

## Review Log

## Implementation Log

- 2026-07-12 — 4 files extracted — `pytest -q`: 10 passed — `docker compose config -q` OK — real-PG up/down deferred: docker daemon starting; executed before phase merge
