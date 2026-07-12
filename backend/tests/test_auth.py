from sqlalchemy import func, select

from app.models import AuditLog, User
from app.security.passwords import hash_password, verify_password
from app.security.tokens import TokenError, create_token, decode_token
from app.services.bootstrap import ensure_bootstrap_admin
from tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, test_settings


def test_password_roundtrip():
    stored = hash_password("s3cret!")
    assert verify_password("s3cret!", stored)
    assert not verify_password("wrong", stored)
    assert not verify_password("s3cret!", "garbage")


def test_token_roundtrip_and_expiry():
    token = create_token(1, "a@x.io", "admin", "k", expires_min=60)
    data = decode_token(token, "k")
    assert (data.user_id, data.email, data.role) == (1, "a@x.io", "admin")

    expired = create_token(1, "a@x.io", "admin", "k", expires_min=-1)
    try:
        decode_token(expired, "k")
        raise AssertionError("expired token accepted")
    except TokenError:
        pass


async def test_login_and_me(client):
    r = await client.post("/api/v1/auth/login",
                          json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200
    token = r.json()["access_token"]

    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == ADMIN_EMAIL
    assert me.json()["role"] == "admin"


async def test_wrong_password_401_and_audited(client, app):
    r = await client.post("/api/v1/auth/login",
                          json={"email": ADMIN_EMAIL, "password": "nope"})
    assert r.status_code == 401
    async with app.state.sessionmaker() as session:
        row = await session.scalar(
            select(AuditLog).where(AuditLog.action == "auth.login")
            .order_by(AuditLog.id.desc()))
        assert row is not None
        assert row.detail == {"success": False}


async def test_me_requires_token(client):
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    bad = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer junk"})
    assert bad.status_code == 401


async def test_bootstrap_admin_idempotent(db_engine):
    from app.db import build_sessionmaker
    maker = build_sessionmaker(db_engine)
    settings = test_settings()
    await ensure_bootstrap_admin(maker, settings)
    await ensure_bootstrap_admin(maker, settings)
    async with maker() as session:
        count = await session.scalar(select(func.count()).select_from(User)
                                     .where(User.email == ADMIN_EMAIL))
        assert count == 1
