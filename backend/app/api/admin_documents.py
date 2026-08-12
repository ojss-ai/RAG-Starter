import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Chunk, Document, User
from app.schemas import DocumentList, DocumentOut
from app.security.deps import require_admin
from app.services import audit

router = APIRouter(prefix="/api/v1/admin/documents", tags=["admin"])


@router.get("", response_model=DocumentList)
async def list_documents(admin: Annotated[User, Depends(require_admin)],
                         session: Annotated[AsyncSession, Depends(get_session)],
                         q: Annotated[str | None, Query(max_length=200)] = None,
                         doc_status: Annotated[str | None, Query(alias="status")] = None,
                         limit: Annotated[int, Query(ge=1, le=200)] = 50,
                         offset: Annotated[int, Query(ge=0)] = 0) -> DocumentList:
    base = select(Document)
    if q:
        base = base.where(Document.filename.ilike(f"%{q}%"))
    if doc_status:
        base = base.where(Document.status == doc_status)
    total = await session.scalar(
        select(func.count()).select_from(base.subquery()))
    rows = await session.scalars(base.order_by(Document.created_at.desc())
                                 .limit(limit).offset(offset))
    return DocumentList(total=total or 0, documents=list(rows))


@router.delete("/{doc_id}", status_code=204)
async def delete_document(doc_id: uuid.UUID, request: Request,
                          admin: Annotated[User, Depends(require_admin)],
                          session: Annotated[AsyncSession, Depends(get_session)]) -> None:
    doc = await session.get(Document, doc_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    # FR-7: purge vectors first, then rows, in one request; a vector-store failure aborts
    # before any relational delete so no orphan vectors can exist.
    await request.app.state.vector_store.delete_document(str(doc_id))
    await session.execute(delete(Chunk).where(Chunk.document_id == doc_id))
    await session.delete(doc)
    await audit.record(session, admin.email, "document.deleted", doc.filename,
                       {"document_id": str(doc_id)})
    await session.commit()
