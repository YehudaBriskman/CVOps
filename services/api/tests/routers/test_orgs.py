"""Router tests for the orgs router — current org, members CRUD.

Same pattern as test_projects/test_data_sources: a minimal FastAPI app mounting
only the orgs router under `/orgs` (mirroring main.py's `/api/v1/orgs`), with
`get_session` overridden onto the testcontainers Postgres and `get_current_user`
overridden to return a seeded user. Multi-tenancy is enforced at the query level
(every handler filters on `current_user.org_id`), so cross-org isolation is
checked by acting as a user in a different org.
"""

from __future__ import annotations

import uuid

import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from cvops_api.core.auth import get_current_user
from cvops_api.db.models.auth import Membership, Org, User
from cvops_api.db.session import get_session
from cvops_api.routers import orgs


@pytest_asyncio.fixture
async def factory(postgres_url: str):
    engine = create_async_engine(postgres_url, echo=False)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


def _client(factory, current_user: User) -> AsyncClient:
    app = FastAPI()
    app.include_router(orgs.router, prefix="/orgs")

    async def _get_session_dep():
        async with factory() as sess:
            yield sess

    app.dependency_overrides[get_session] = _get_session_dep
    app.dependency_overrides[get_current_user] = lambda: current_user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _make_org_with_owner(factory) -> tuple[Org, User]:
    """An org with one owner-member user."""
    suffix = uuid.uuid4().hex[:8]
    async with factory() as s:
        org = Org(name=f"org-{suffix}")
        s.add(org)
        await s.flush()
        user = User(org_id=org.id, email=f"owner-{suffix}@test.com", is_active=True)
        s.add(user)
        await s.flush()
        s.add(Membership(org_id=org.id, user_id=user.id, role="owner"))
        await s.commit()
        await s.refresh(org)
        await s.refresh(user)
        return org, user


async def _make_user(factory, org_id: uuid.UUID | None = None) -> User:
    """A bare user, optionally in an existing org (else a fresh org)."""
    suffix = uuid.uuid4().hex[:8]
    async with factory() as s:
        if org_id is None:
            org = Org(name=f"org-{suffix}")
            s.add(org)
            await s.flush()
            org_id = org.id
        user = User(org_id=org_id, email=f"u-{suffix}@test.com", is_active=True)
        s.add(user)
        await s.commit()
        await s.refresh(user)
        return user


# ---------------------------------------------------------------------------
# get / patch current org
# ---------------------------------------------------------------------------


async def test_get_current_org(factory) -> None:
    org, owner = await _make_org_with_owner(factory)

    async with _client(factory, owner) as c:
        res = await c.get("/orgs/current")

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["id"] == str(org.id)
    assert body["name"] == org.name


async def test_patch_current_org_name(factory) -> None:
    org, owner = await _make_org_with_owner(factory)
    new_name = f"renamed-{uuid.uuid4().hex[:8]}"

    async with _client(factory, owner) as c:
        res = await c.patch("/orgs/current", json={"name": new_name})

    assert res.status_code == 200, res.text
    assert res.json()["name"] == new_name

    async with factory() as s:
        refreshed = await s.get(Org, org.id)
        assert refreshed is not None
        assert refreshed.name == new_name


async def test_patch_current_org_settings(factory) -> None:
    org, owner = await _make_org_with_owner(factory)

    async with _client(factory, owner) as c:
        res = await c.patch("/orgs/current", json={"settings": {"theme": "dark"}})

    assert res.status_code == 200, res.text
    assert res.json()["settings"] == {"theme": "dark"}


# ---------------------------------------------------------------------------
# list members
# ---------------------------------------------------------------------------


async def test_list_members_returns_only_own_org(factory) -> None:
    org, owner = await _make_org_with_owner(factory)
    # A member in a different org must not appear in this org's listing.
    _other_org, _other_owner = await _make_org_with_owner(factory)

    async with _client(factory, owner) as c:
        res = await c.get("/orgs/current/members")

    assert res.status_code == 200, res.text
    members = res.json()
    assert len(members) == 1
    assert members[0]["user_id"] == str(owner.id)
    assert members[0]["email"] == owner.email
    assert members[0]["role"] == "owner"


# ---------------------------------------------------------------------------
# invite member
# ---------------------------------------------------------------------------


async def test_invite_existing_user(factory) -> None:
    org, owner = await _make_org_with_owner(factory)
    invitee = await _make_user(factory)  # exists, in another org

    async with _client(factory, owner) as c:
        res = await c.post(
            "/orgs/current/members",
            json={"email": invitee.email, "role": "member"},
        )

    assert res.status_code == 201, res.text
    body = res.json()
    assert body["user_id"] == str(invitee.id)
    assert body["email"] == invitee.email
    assert body["role"] == "member"

    async with factory() as s:
        membership = (
            await s.execute(
                select(Membership).where(
                    Membership.org_id == org.id, Membership.user_id == invitee.id
                )
            )
        ).scalar_one_or_none()
        assert membership is not None


async def test_invite_unknown_user_404(factory) -> None:
    _org, owner = await _make_org_with_owner(factory)

    async with _client(factory, owner) as c:
        res = await c.post(
            "/orgs/current/members",
            json={"email": f"ghost-{uuid.uuid4().hex[:8]}@test.com", "role": "member"},
        )

    assert res.status_code == 404, res.text


async def test_invite_duplicate_membership_409(factory) -> None:
    _org, owner = await _make_org_with_owner(factory)

    # The owner is already a member of their own org → 409 on re-invite.
    async with _client(factory, owner) as c:
        res = await c.post(
            "/orgs/current/members",
            json={"email": owner.email, "role": "member"},
        )

    assert res.status_code == 409, res.text


# ---------------------------------------------------------------------------
# update member role
# ---------------------------------------------------------------------------


async def test_update_member_role(factory) -> None:
    org, owner = await _make_org_with_owner(factory)
    member = await _make_user(factory, org_id=org.id)
    async with factory() as s:
        s.add(Membership(org_id=org.id, user_id=member.id, role="member"))
        await s.commit()

    async with _client(factory, owner) as c:
        res = await c.patch(
            f"/orgs/current/members/{member.id}",
            json={"role": "admin"},
        )

    assert res.status_code == 200, res.text
    assert res.json()["role"] == "admin"

    async with factory() as s:
        m = (
            await s.execute(
                select(Membership).where(
                    Membership.org_id == org.id, Membership.user_id == member.id
                )
            )
        ).scalar_one()
        assert m.role == "admin"


async def test_update_member_not_in_org_404(factory) -> None:
    _org, owner = await _make_org_with_owner(factory)
    stranger = await _make_user(factory)  # member of a different org

    async with _client(factory, owner) as c:
        res = await c.patch(
            f"/orgs/current/members/{stranger.id}",
            json={"role": "admin"},
        )

    assert res.status_code == 404, res.text


# ---------------------------------------------------------------------------
# remove member
# ---------------------------------------------------------------------------


async def test_remove_member(factory) -> None:
    org, owner = await _make_org_with_owner(factory)
    member = await _make_user(factory, org_id=org.id)
    async with factory() as s:
        s.add(Membership(org_id=org.id, user_id=member.id, role="member"))
        await s.commit()

    async with _client(factory, owner) as c:
        res = await c.delete(f"/orgs/current/members/{member.id}")

    assert res.status_code == 204, res.text

    async with factory() as s:
        m = (
            await s.execute(
                select(Membership).where(
                    Membership.org_id == org.id, Membership.user_id == member.id
                )
            )
        ).scalar_one_or_none()
        assert m is None


async def test_remove_member_not_in_org_404(factory) -> None:
    _org, owner = await _make_org_with_owner(factory)
    stranger = await _make_user(factory)

    async with _client(factory, owner) as c:
        res = await c.delete(f"/orgs/current/members/{stranger.id}")

    assert res.status_code == 404, res.text


# ---------------------------------------------------------------------------
# cross-org isolation
# ---------------------------------------------------------------------------


async def test_cross_org_cannot_remove_other_orgs_member(factory) -> None:
    # Org A has owner + member; a user from org B tries to evict A's member.
    org_a, _owner_a = await _make_org_with_owner(factory)
    member_a = await _make_user(factory, org_id=org_a.id)
    async with factory() as s:
        s.add(Membership(org_id=org_a.id, user_id=member_a.id, role="member"))
        await s.commit()

    _org_b, owner_b = await _make_org_with_owner(factory)

    async with _client(factory, owner_b) as c:
        res = await c.delete(f"/orgs/current/members/{member_a.id}")

    # owner_b's org has no such membership → 404, and A's row is untouched.
    assert res.status_code == 404, res.text
    async with factory() as s:
        m = (
            await s.execute(
                select(Membership).where(
                    Membership.org_id == org_a.id, Membership.user_id == member_a.id
                )
            )
        ).scalar_one_or_none()
        assert m is not None
