import io
import zipfile

from sqlalchemy import func, select

from app.models import AuditLog, Chunk, Document


def _txt_file(name="doc.txt", content=b"vacation policy grants twenty days"):
    return {"file": (name, io.BytesIO(content), "text/plain")}


async def _drain(app):
    await app.state.task_queue.drain()


async def test_upload_txt_reaches_indexed(client, app, admin_headers):
    r = await client.post("/api/v1/admin/upload", headers=admin_headers,
                          files=_txt_file())
    assert r.status_code == 200, r.text
    doc = r.json()["documents"][0]
    assert doc["status"] == "PENDING"
    await _drain(app)

    async with app.state.sessionmaker() as session:
        row = await session.scalar(select(Document))
        assert row.status == "INDEXED"
        n_chunks = await session.scalar(select(func.count()).select_from(Chunk))
        assert n_chunks >= 1
    assert (await app.state.vector_store.stats())["vectors"] == n_chunks


async def test_duplicate_hash_acknowledged_not_reprocessed(client, app, admin_headers):
    await client.post("/api/v1/admin/upload", headers=admin_headers, files=_txt_file())
    await _drain(app)
    r2 = await client.post("/api/v1/admin/upload", headers=admin_headers,
                           files=_txt_file(name="same-bytes-other-name.txt"))
    assert r2.json()["documents"][0]["duplicate"] is True
    assert app.state.task_queue.pending == []  # FR-5: no new job
    async with app.state.sessionmaker() as session:
        count = await session.scalar(select(func.count()).select_from(Document))
        assert count == 1


async def test_embedding_failure_marks_failed_no_vectors(client, app, admin_headers):
    class DownEmbedder:
        dim = 8
        async def embed(self, texts):
            raise RuntimeError("provider down")

    app.state.embedder = DownEmbedder()
    await client.post("/api/v1/admin/upload", headers=admin_headers, files=_txt_file())
    await _drain(app)

    async with app.state.sessionmaker() as session:
        row = await session.scalar(select(Document))
        assert row.status == "FAILED"
        assert "provider down" in row.error
        n_chunks = await session.scalar(select(func.count()).select_from(Chunk))
        assert n_chunks == 0
    assert (await app.state.vector_store.stats())["vectors"] == 0  # NFR-6


async def test_zip_mixed_entries(client, app, admin_headers):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("a.txt", "alpha document text")
        zf.writestr("b.md", "beta document text")
        zf.writestr("c.txt", "gamma document text")
        zf.writestr("virus.exe", "MZ")
    buf.seek(0)
    r = await client.post("/api/v1/admin/upload", headers=admin_headers,
                          files={"file": ("batch.zip", buf, "application/zip")})
    body = r.json()
    assert len(body["documents"]) == 3
    assert body["rejected"] == ["virus.exe: unsupported type"]
    await _drain(app)
    async with app.state.sessionmaker() as session:
        indexed = await session.scalar(select(func.count()).select_from(Document)
                                       .where(Document.status == "INDEXED"))
        assert indexed == 3


async def test_upload_validation(client, app, admin_headers, app_settings):
    r = await client.post("/api/v1/admin/upload", headers=admin_headers,
                          files=_txt_file(name="tool.exe"))
    assert r.status_code == 415

    app_settings.upload_max_mb = 0  # every non-empty file now exceeds the cap
    r = await client.post("/api/v1/admin/upload", headers=admin_headers,
                          files=_txt_file())
    assert r.status_code == 413
    app_settings.upload_max_mb = 100


async def test_upload_requires_auth_and_audits(client, app, admin_headers, user_headers):
    assert (await client.post("/api/v1/admin/upload",
                              files=_txt_file())).status_code == 401
    assert (await client.post("/api/v1/admin/upload", headers=user_headers,
                              files=_txt_file())).status_code == 403
    await client.post("/api/v1/admin/upload", headers=admin_headers, files=_txt_file())
    async with app.state.sessionmaker() as session:
        row = await session.scalar(select(AuditLog)
                                   .where(AuditLog.action == "document.uploaded"))
        assert row is not None
