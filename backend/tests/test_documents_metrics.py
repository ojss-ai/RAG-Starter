import io

from sqlalchemy import func, select

from app.models import AuditLog, Chunk, Document


def _txt(name, content):
    return {"file": (name, io.BytesIO(content), "text/plain")}


async def _seed_docs(client, app, admin_headers):
    for name, content in [("alpha.txt", b"alpha content one"),
                          ("beta.txt", b"beta content two"),
                          ("gamma.md", b"gamma content three")]:
        await client.post("/api/v1/admin/upload", headers=admin_headers,
                          files=_txt(name, content))
    await app.state.task_queue.drain()


async def test_ledger_search_filter_paginate(client, app, admin_headers):
    await _seed_docs(client, app, admin_headers)
    r = await client.get("/api/v1/admin/documents", headers=admin_headers)
    assert r.json()["total"] == 3

    r = await client.get("/api/v1/admin/documents?q=alp", headers=admin_headers)
    assert [d["filename"] for d in r.json()["documents"]] == ["alpha.txt"]

    r = await client.get("/api/v1/admin/documents?status=INDEXED&limit=2",
                         headers=admin_headers)
    assert r.json()["total"] == 3
    assert len(r.json()["documents"]) == 2

    assert (await client.get("/api/v1/admin/documents")).status_code == 401


async def test_delete_purges_both_stores_and_audits(client, app, admin_headers):
    await _seed_docs(client, app, admin_headers)
    async with app.state.sessionmaker() as session:
        doc = await session.scalar(select(Document)
                                   .where(Document.filename == "alpha.txt"))
        doc_id = doc.id
    before = (await app.state.vector_store.stats())["vectors"]

    r = await client.delete(f"/api/v1/admin/documents/{doc_id}", headers=admin_headers)
    assert r.status_code == 204

    async with app.state.sessionmaker() as session:
        assert await session.get(Document, doc_id) is None
        orphan_chunks = await session.scalar(
            select(func.count()).select_from(Chunk).where(Chunk.document_id == doc_id))
        assert orphan_chunks == 0
        row = await session.scalar(select(AuditLog)
                                   .where(AuditLog.action == "document.deleted"))
        assert row is not None
    assert (await app.state.vector_store.stats())["vectors"] < before

    missing = await client.delete(f"/api/v1/admin/documents/{doc_id}",
                                  headers=admin_headers)
    assert missing.status_code == 404


async def test_metrics_counts_and_error_rate(client, app, admin_headers):
    await _seed_docs(client, app, admin_headers)
    r = await client.get("/api/v1/admin/metrics", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["documents_by_status"]["INDEXED"] == 3
    assert body["documents_total"] == 3
    assert body["chunks_total"] == body["vectors_total"] >= 3
    assert body["vector_backend"] == "memory"
    assert body["http_requests"] > 0
    assert body["error_rate"] == 0.0

    assert (await client.get("/api/v1/admin/metrics")).status_code == 401
