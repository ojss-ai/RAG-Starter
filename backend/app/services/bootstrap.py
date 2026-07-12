import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Settings
from app.models import User
from app.security.passwords import hash_password
from app.services import audit

log = logging.getLogger(__name__)


async def ensure_bootstrap_admin(sessionmaker: async_sessionmaker, settings: Settings) -> None:
    """Idempotent: creates the bootstrap admin only when absent."""
    async with sessionmaker() as session:
        existing = await session.scalar(
            select(User).where(User.email == settings.bootstrap_admin_email))
        if existing:
            return
        session.add(User(email=settings.bootstrap_admin_email,
                         password_hash=hash_password(settings.bootstrap_admin_password),
                         role="admin"))
        await audit.record(session, "system", "bootstrap_admin.created",
                           settings.bootstrap_admin_email)
        await session.commit()
    if settings.bootstrap_admin_password == "change-me-now":
        log.warning("bootstrap admin is using the DEFAULT password — rotate it now")
