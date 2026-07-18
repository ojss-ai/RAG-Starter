import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.admin_audit import router as admin_audit_router
from app.api.admin_documents import router as admin_documents_router
from app.api.admin_keys import router as admin_keys_router
from app.api.admin_upload import router as admin_upload_router
from app.api.admin_users import router as admin_users_router
from app.api.auth import router as auth_router
from app.api.metrics import router as metrics_router
from app.config import Settings, get_settings
from app.db import build_engine, build_sessionmaker
from app.ingest.embeddings import get_embedding_provider
from app.logging_setup import RequestIdMiddleware, setup_logging
from app.security.ratelimit import RateLimiter
from app.services.metrics import HttpMetrics, HttpMetricsMiddleware
from app.services.bootstrap import ensure_bootstrap_admin
from app.services.tasks import BackgroundTaskQueue
from app.vectorstore import get_vector_store

log = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.engine = build_engine(settings.database_url)
        app.state.sessionmaker = build_sessionmaker(app.state.engine)
        app.state.vector_store = get_vector_store(settings)
        await app.state.vector_store.ensure_ready()
        app.state.embedder = get_embedding_provider(settings)
        app.state.task_queue = BackgroundTaskQueue()
        await ensure_bootstrap_admin(app.state.sessionmaker, settings)
        log.info("startup complete", extra={"extra_fields": {"env": settings.env}})
        yield
        await app.state.engine.dispose()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.rate_limiter = RateLimiter()
    app.state.http_metrics = HttpMetrics()
    app.add_middleware(HttpMetricsMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_router)
    app.include_router(admin_keys_router)
    app.include_router(admin_users_router)
    app.include_router(admin_audit_router)
    app.include_router(admin_upload_router)
    app.include_router(admin_documents_router)
    app.include_router(metrics_router)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict[str, str]:
        async with app.state.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ready"}

    return app


app = create_app()
