from fastapi import Depends

from app.security.ratelimit import RateLimiter, rate_limit


def test_token_bucket_math():
    rl = RateLimiter()
    t = 1000.0
    # 60 rpm → 1 token/s, bucket starts full with 60
    for _ in range(60):
        allowed, _ = rl.check("k", 60, now=t)
        assert allowed
    allowed, retry = rl.check("k", 60, now=t)
    assert not allowed
    assert 0 < retry <= 1.0
    # one second later exactly one token refilled
    allowed, _ = rl.check("k", 60, now=t + 1.0)
    assert allowed


def test_bucket_isolated_per_key():
    rl = RateLimiter()
    t = 0.0
    assert rl.check("a", 1, now=t)[0]
    assert not rl.check("a", 1, now=t)[0]
    assert rl.check("b", 1, now=t)[0]  # other caller unaffected


def _probe(app):
    if not any(getattr(r, "path", None) == "/test/limited" for r in app.routes):
        @app.get("/test/limited", dependencies=[Depends(rate_limit("chat"))])
        async def limited():
            return {"ok": True}


async def test_rate_limit_429_with_retry_after(client, app, app_settings):
    app_settings.rate_chat_rpm = 3
    _probe(app)
    for _ in range(3):
        assert (await client.get("/test/limited")).status_code == 200
    r = await client.get("/test/limited")
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) >= 1


async def test_audit_endpoint_admin_only_and_paginated(client, admin_headers, user_headers):
    assert (await client.get("/api/v1/admin/audit",
                             headers=user_headers)).status_code == 403
    r = await client.get("/api/v1/admin/audit?limit=5", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body) <= 5
    # the two logins from the fixtures are audited
    assert any(row["action"] == "auth.login" for row in body)
