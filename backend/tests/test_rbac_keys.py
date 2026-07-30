from fastapi import Depends
from typing import Annotated

from app.security.deps import Principal, require_ingest


async def test_admin_routes_reject_plain_user(client, user_headers):
    r = await client.get("/api/v1/admin/users", headers=user_headers)
    assert r.status_code == 403
    r = await client.post("/api/v1/admin/keys", headers=user_headers,
                          json={"name": "nope"})
    assert r.status_code == 403


async def test_admin_creates_user_and_key(client, admin_headers, app):
    r = await client.post("/api/v1/admin/users", headers=admin_headers,
                          json={"email": "new@test.io", "password": "longenough1",
                                "role": "user"})
    assert r.status_code == 201
    assert r.json()["role"] == "user"

    dup = await client.post("/api/v1/admin/users", headers=admin_headers,
                            json={"email": "new@test.io", "password": "longenough1"})
    assert dup.status_code == 409

    k = await client.post("/api/v1/admin/keys", headers=admin_headers,
                          json={"name": "watcher-1"})
    assert k.status_code == 201
    assert k.json()["api_key"].startswith("rgs_")

    listed = await client.get("/api/v1/admin/keys", headers=admin_headers)
    assert listed.status_code == 200
    assert "api_key" not in listed.json()[0]  # plaintext never listed


def _ingest_probe(app):
    """Mount a scope probe route so require_ingest is exercised over HTTP."""
    if not any(getattr(r, "path", None) == "/test/ingest-probe" for r in app.routes):
        @app.post("/test/ingest-probe")
        async def probe(principal: Annotated[Principal, Depends(require_ingest)]):
            return {"kind": principal.kind, "label": principal.label}


async def test_api_key_scope_enforced(client, admin_headers, app):
    _ingest_probe(app)
    k = await client.post("/api/v1/admin/keys", headers=admin_headers,
                          json={"name": "watcher-2"})
    key = k.json()["api_key"]

    ok = await client.post("/test/ingest-probe", headers={"X-API-Key": key})
    assert ok.status_code == 200
    assert ok.json() == {"kind": "api_key", "label": "watcher-2"}

    # key must NOT open admin endpoints (FR-16)
    denied = await client.get("/api/v1/admin/keys", headers={"X-API-Key": key})
    assert denied.status_code == 401

    bad = await client.post("/test/ingest-probe", headers={"X-API-Key": "rgs_wrong"})
    assert bad.status_code == 401


async def test_revoked_key_rejected(client, admin_headers, app):
    _ingest_probe(app)
    k = await client.post("/api/v1/admin/keys", headers=admin_headers,
                          json={"name": "watcher-3"})
    key_id, key = k.json()["id"], k.json()["api_key"]

    assert (await client.delete(f"/api/v1/admin/keys/{key_id}",
                                headers=admin_headers)).status_code == 204
    r = await client.post("/test/ingest-probe", headers={"X-API-Key": key})
    assert r.status_code == 401


async def test_admin_jwt_can_ingest(client, admin_headers, user_headers, app):
    _ingest_probe(app)
    ok = await client.post("/test/ingest-probe", headers=admin_headers)
    assert ok.status_code == 200
    assert ok.json()["kind"] == "user"

    denied = await client.post("/test/ingest-probe", headers=user_headers)
    assert denied.status_code == 403
