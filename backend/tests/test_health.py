async def test_healthz_ok(client):
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_readyz_checks_db(client):
    r = await client.get("/readyz")
    assert r.status_code == 200
    assert r.json() == {"status": "ready"}


async def test_request_id_header(client):
    r = await client.get("/healthz")
    assert len(r.headers["x-request-id"]) == 32

    r2 = await client.get("/healthz", headers={"x-request-id": "trace-me"})
    assert r2.headers["x-request-id"] == "trace-me"
