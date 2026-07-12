from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


async def record(session: AsyncSession, actor: str, action: str,
                 target: str = "", detail: dict | None = None) -> None:
    """Append one audit row. Caller owns the transaction (commit with the action itself
    so the audit entry and the audited change are atomic)."""
    session.add(AuditLog(actor=actor, action=action, target=target, detail=detail or {}))
