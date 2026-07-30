import logging
import uuid
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Settings
from app.ingest.chunker import chunk_text
from app.ingest.embeddings import EmbeddingProvider
from app.ingest.extract import extract_text
from app.models import Chunk, Document
from app.vectorstore import VectorItem, VectorStore

log = logging.getLogger(__name__)


async def ingest_document(sessionmaker: async_sessionmaker, vector_store: VectorStore,
                          embedder: EmbeddingProvider, settings: Settings,
                          document_id: uuid.UUID) -> None:
    """Drives one document PENDING → PROCESSING → INDEXED/FAILED (FR-4). On any failure the
    document's vectors are purged so a FAILED document never has partial vectors (NFR-6)."""
    async with sessionmaker() as session:
        doc = await session.scalar(select(Document).where(Document.id == document_id))
        if doc is None:
            log.error("ingest: document %s vanished", document_id)
            return
        doc.status = "PROCESSING"
        await session.commit()

        try:
            data = Path(doc.path).read_bytes()
            text = extract_text(doc.filename, data)
            pieces = chunk_text(text, settings.chunk_size_tokens, settings.chunk_overlap_pct)
            if not pieces:
                raise ValueError("document produced no text chunks")

            embeddings = await embedder.embed(pieces)

            # replace any prior chunks (safe re-ingest), then write rows + vectors
            await session.execute(delete(Chunk).where(Chunk.document_id == doc.id))
            chunk_rows = [Chunk(id=uuid.uuid4(), document_id=doc.id, seq=i, text=p)
                          for i, p in enumerate(pieces)]
            session.add_all(chunk_rows)
            await session.flush()

            await vector_store.upsert([
                VectorItem(chunk_id=str(c.id), document_id=str(doc.id),
                           partition_key=doc.partition_key, embedding=e)
                for c, e in zip(chunk_rows, embeddings)
            ])

            doc.status = "INDEXED"
            doc.error = None
            await session.commit()
        except Exception as exc:
            await session.rollback()
            await vector_store.delete_document(str(doc.id))  # NFR-6: no partial index
            doc.status = "FAILED"
            doc.error = str(exc)[:2000]
            await session.commit()
            log.warning("ingest failed for %s: %s", doc.filename, exc)
