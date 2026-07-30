import hashlib
import io
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.ingest.pipeline import ingest_document
from app.models import Document
from app.schemas import UploadedDoc, UploadResponse
from app.security.deps import Principal, require_ingest
from app.security.ratelimit import rate_limit
from app.services import audit

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

DOC_EXTS = {".pdf", ".txt", ".md"}


def _ext(filename: str) -> str:
    return PurePosixPath(filename.replace("\\", "/")).suffix.lower()


async def _register(session: AsyncSession, request: Request, filename: str,
                    data: bytes) -> tuple[UploadedDoc, bool]:
    """Create (or dedupe) one document row + saved file. Returns (result, created)."""
    settings = request.app.state.settings
    content_hash = hashlib.sha256(data).hexdigest()
    existing = await session.scalar(
        select(Document).where(Document.content_hash == content_hash))
    if existing:  # FR-5: acknowledged, not re-processed
        return UploadedDoc(id=existing.id, filename=existing.filename,
                           status=existing.status, duplicate=True), False

    doc_id = uuid.uuid4()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / f"{doc_id}{_ext(filename)}"
    dest.write_bytes(data)

    doc = Document(id=doc_id, path=str(dest), filename=filename,
                   content_hash=content_hash, size_bytes=len(data),
                   mime="", status="PENDING")
    session.add(doc)
    await session.flush()
    return UploadedDoc(id=doc.id, filename=doc.filename, status="PENDING",
                       duplicate=False), True


@router.post("/upload", response_model=UploadResponse,
             dependencies=[Depends(rate_limit("upload"))])
async def upload(request: Request, file: UploadFile,
                 principal: Annotated[Principal, Depends(require_ingest)],
                 session: Annotated[AsyncSession, Depends(get_session)]) -> UploadResponse:
    settings = request.app.state.settings
    filename = file.filename or "upload"
    ext = _ext(filename)
    if ext not in settings.upload_allowed_ext:
        raise HTTPException(415, f"unsupported file type: {ext or '(none)'}")

    max_bytes = settings.upload_max_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:  # FR-18: rejected before permanent buffering
        raise HTTPException(413, f"file exceeds {settings.upload_max_mb} MB limit")

    documents: list[UploadedDoc] = []
    rejected: list[str] = []
    created_ids: list[uuid.UUID] = []

    if ext == ".zip":  # FR-6: batch archives
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            raise HTTPException(400, "corrupt zip archive")
        infos = [i for i in zf.infolist() if not i.is_dir()]
        if len(infos) > settings.zip_max_entries:
            raise HTTPException(413, f"zip exceeds {settings.zip_max_entries} entries")
        for info in infos:
            name = PurePosixPath(info.filename).name
            if _ext(name) not in DOC_EXTS:
                rejected.append(f"{info.filename}: unsupported type")
                continue
            if info.file_size > max_bytes:
                rejected.append(f"{info.filename}: exceeds size limit")
                continue
            entry, created = await _register(session, request, name, zf.read(info))
            documents.append(entry)
            if created:
                created_ids.append(entry.id)
    else:
        entry, created = await _register(session, request, filename, data)
        documents.append(entry)
        if created:
            created_ids.append(entry.id)

    await audit.record(session, principal.label, "document.uploaded", filename,
                       {"created": len(created_ids), "rejected": len(rejected)})
    await session.commit()

    state = request.app.state
    for doc_id in created_ids:  # NFR-2: ack now, work async
        state.task_queue.spawn(
            lambda d=doc_id: ingest_document(state.sessionmaker, state.vector_store,
                                             state.embedder, state.settings, d))
    return UploadResponse(documents=documents, rejected=rejected)
