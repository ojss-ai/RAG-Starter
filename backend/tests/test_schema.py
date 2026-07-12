import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models import Chunk, Document, User


async def test_metadata_creates_all_tables(db_session):
    count = await db_session.scalar(select(func.count()).select_from(User))
    assert count == 0


async def test_email_unique(db_session):
    db_session.add(User(email="a@x.io", password_hash="h", role="user"))
    await db_session.commit()
    db_session.add(User(email="a@x.io", password_hash="h2", role="user"))
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_document_status_check(db_session):
    db_session.add(Document(path="/f", filename="f", content_hash="h1",
                            size_bytes=1, status="NOT-A-STATUS"))
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_chunk_cascade_delete(db_session):
    doc = Document(path="/f", filename="f", content_hash="h2", size_bytes=1)
    db_session.add(doc)
    await db_session.flush()
    db_session.add_all([Chunk(document_id=doc.id, seq=i, text=f"c{i}") for i in range(3)])
    await db_session.commit()

    await db_session.delete(doc)
    await db_session.commit()
    left = await db_session.scalar(select(func.count()).select_from(Chunk))
    assert left == 0


async def test_content_hash_unique(db_session):
    db_session.add(Document(path="/a", filename="a", content_hash="same", size_bytes=1))
    await db_session.commit()
    db_session.add(Document(path="/b", filename="b", content_hash="same", size_bytes=2))
    with pytest.raises(IntegrityError):
        await db_session.commit()
