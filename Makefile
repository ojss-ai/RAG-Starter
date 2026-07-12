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
