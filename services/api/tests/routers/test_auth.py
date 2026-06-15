"""Router tests for the auth router — register, token, refresh, revoke, me.

Mirrors the data_sources/projects test pattern: a minimal FastAPI app that
mounts only the auth router (under `/auth`, matching main.py's `/api/v1/auth`),
with `get_session` overridden onto the testcontainers Postgres.

Most auth endpoints do NOT depend on `get_current_user` — they run their real
handlers end to end (real bcrypt hashing, real JWT encode/decode). `/me` and
`/revoke` do require an authenticated user; those are exercised with a real
access token so the OAuth2 bearer extraction (`_oauth2_scheme`) sees a header,
and `get_current_user` is overridden to return the seeded user.

The blacklist lives in Redis, so refresh/revoke tests take the `fake_redis`
fixture, which swaps in a fakeredis client as the process-global Redis.
"""

from __future__ import annotations

import uuid

import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from cvops_api.core.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    is_blacklisted,
)
from cvops_api.db.models.auth import Membership, Org, User
from cvops_api.db.session import get_session
from cvops_api.routers import auth


@pytest_asyncio.fixture
async def factory(postgres_url: str):
    engine = create_async_engine(postgres_url, echo=False)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


def _app(factory) -> FastAPI:
    app = FastAPI()
    # main.py mounts auth under /api/v1/auth; mirror as /auth here so the
    # route paths (/auth/token, /auth/register, ...) match production.
    app.include_router(auth.router, prefix="/auth")

    async def _get_session_dep():
        async with factory() as sess:
            yield sess

    app.dependency_overrides[get_session] = _get_session_dep
    return app


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed_user(factory, *, password: str = "hunter2") -> User:
    """Create an org + active user with a real bcrypt password hash."""
    suffix = uuid.uuid4().hex[:8]
    async with factory() as s:
        org = Org(name=f"org-{suffix}")
        s.add(org)
        await s.flush()
        user = User(
            org_id=org.id,
            email=f"u-{suffix}@test.com",
            password_hash=hash_password(password),
            is_active=True,
        )
        s.add(user)
        await s.commit()
        await s.refresh(user)
        return user


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------


async def test_register_creates_org_user_membership(factory) -> None:
    email = f"new-{uuid.uuid4().hex[:8]}@test.com"
    app = _app(factory)

    async with _client(app) as c:
        res = await c.post(
            "/auth/register",
            json={"email": email, "password": "hunter2", "org_name": None},
        )

    assert res.status_code == 201, res.text
    body = res.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"

    # The access token's subject is a real user id; verify the row graph exists.
    sub = decode_token(body["access_token"])["sub"]
    async with factory() as s:
        user = await s.get(User, uuid.UUID(sub))
        assert user is not None
        assert user.email == email
        org = await s.get(Org, user.org_id)
        assert org is not None
        # org_name omitted → derived from the email local-part.
        assert org.name == email.split("@")[0]
        from sqlalchemy import select

        membership = (
            await s.execute(select(Membership).where(Membership.user_id == user.id))
        ).scalar_one_or_none()
        assert membership is not None
        assert membership.org_id == user.org_id
        assert membership.role == "owner"


async def test_register_duplicate_email_returns_409(factory) -> None:
    email = f"dup-{uuid.uuid4().hex[:8]}@test.com"
    app = _app(factory)

    async with _client(app) as c:
        first = await c.post(
            "/auth/register",
            json={"email": email, "password": "hunter2"},
        )
        assert first.status_code == 201, first.text

        second = await c.post(
            "/auth/register",
            json={"email": email, "password": "other", "org_name": f"org-{uuid.uuid4().hex[:6]}"},
        )

    assert second.status_code == 409, second.text


# ---------------------------------------------------------------------------
# token (login)
# ---------------------------------------------------------------------------


async def test_token_valid_credentials(factory) -> None:
    user = await _seed_user(factory, password="hunter2")
    app = _app(factory)

    async with _client(app) as c:
        res = await c.post(
            "/auth/token",
            data={"username": user.email, "password": "hunter2"},
        )

    assert res.status_code == 200, res.text
    body = res.json()
    assert decode_token(body["access_token"])["sub"] == str(user.id)
    assert decode_token(body["refresh_token"])["type"] == "refresh"


async def test_token_wrong_password_rejected(factory) -> None:
    user = await _seed_user(factory, password="hunter2")
    app = _app(factory)

    async with _client(app) as c:
        res = await c.post(
            "/auth/token",
            data={"username": user.email, "password": "wrong"},
        )

    assert res.status_code == 401, res.text


async def test_token_unknown_user_rejected(factory) -> None:
    app = _app(factory)

    async with _client(app) as c:
        res = await c.post(
            "/auth/token",
            data={"username": f"ghost-{uuid.uuid4().hex[:8]}@test.com", "password": "x"},
        )

    assert res.status_code == 401, res.text


# ---------------------------------------------------------------------------
# refresh
# ---------------------------------------------------------------------------


async def test_refresh_valid_issues_new_access(factory, fake_redis) -> None:
    user = await _seed_user(factory)
    refresh_token = create_refresh_token(str(user.id))
    app = _app(factory)

    async with _client(app) as c:
        res = await c.post("/auth/refresh", json={"refresh_token": refresh_token})

    assert res.status_code == 200, res.text
    body = res.json()
    assert decode_token(body["access_token"])["sub"] == str(user.id)
    assert decode_token(body["access_token"])["type"] == "access"

    # Rotation: the consumed refresh token's jti is now blacklisted.
    old_jti = decode_token(refresh_token)["jti"]
    assert await is_blacklisted(old_jti) is True


async def test_refresh_does_not_reject_already_blacklisted_token(factory, fake_redis) -> None:
    """Pins the CURRENT (buggy) behavior: `refresh` rotates the consumed token
    onto the blacklist but never checks `is_blacklisted` on the incoming token,
    so a rotated refresh token can be replayed. See the report — this should be
    a 401 once the handler enforces the blacklist (as `resolve_user` does for
    access tokens).
    """
    user = await _seed_user(factory)
    refresh_token = create_refresh_token(str(user.id))
    app = _app(factory)

    async with _client(app) as c:
        first = await c.post("/auth/refresh", json={"refresh_token": refresh_token})
        assert first.status_code == 200, first.text
        # The token is now blacklisted by the rotation in the first call...
        old_jti = decode_token(refresh_token)["jti"]
        assert await is_blacklisted(old_jti) is True
        # ...yet replaying it still succeeds, because refresh skips the check.
        second = await c.post("/auth/refresh", json={"refresh_token": refresh_token})

    assert second.status_code == 200, second.text


async def test_refresh_with_access_token_rejected(factory, fake_redis) -> None:
    user = await _seed_user(factory)
    access_token = create_access_token(str(user.id))
    app = _app(factory)

    async with _client(app) as c:
        res = await c.post("/auth/refresh", json={"refresh_token": access_token})

    # Wrong token type ("access" instead of "refresh") → 401.
    assert res.status_code == 401, res.text


# ---------------------------------------------------------------------------
# revoke
# ---------------------------------------------------------------------------


async def test_revoke_blacklists_access_jti(factory, fake_redis) -> None:
    user = await _seed_user(factory)
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    app = _app(factory)
    # /revoke depends on get_current_user; override it, but the handler also
    # reads the raw token via _oauth2_scheme, so a real Bearer header is needed.
    app.dependency_overrides[get_current_user] = lambda: user

    async with _client(app) as c:
        res = await c.post(
            "/auth/revoke",
            json={"refresh_token": refresh_token},
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert res.status_code == 204, res.text

    access_jti = decode_token(access_token)["jti"]
    refresh_jti = decode_token(refresh_token)["jti"]
    assert await is_blacklisted(access_jti) is True
    assert await is_blacklisted(refresh_jti) is True


# ---------------------------------------------------------------------------
# me
# ---------------------------------------------------------------------------


async def test_me_returns_current_user(factory) -> None:
    user = await _seed_user(factory)
    app = _app(factory)
    app.dependency_overrides[get_current_user] = lambda: user

    async with _client(app) as c:
        res = await c.get(
            "/auth/me",
            headers={"Authorization": "Bearer dummy"},
        )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["id"] == str(user.id)
    assert body["email"] == user.email
    assert body["org_id"] == str(user.org_id)
