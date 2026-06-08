import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from cvops_api.db.models.auth import Membership, Org, User
from tests.db.conftest import make_org, make_user


# ---------------------------------------------------------------------------
# Org tests
# ---------------------------------------------------------------------------


async def test_org_create(session: AsyncSession):
    org = Org(name=f"org-{uuid.uuid4().hex[:8]}")
    session.add(org)
    await session.flush()
    assert org.name.startswith("org-")


async def test_org_name_unique(session: AsyncSession):
    shared_name = f"org-{uuid.uuid4().hex[:8]}"
    session.add(Org(name=shared_name))
    await session.flush()

    session.add(Org(name=shared_name))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


async def test_org_name_required(session: AsyncSession):
    session.add(Org(name=None))  # type: ignore[arg-type]
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


async def test_org_settings_nullable(session: AsyncSession):
    org = Org(name=f"org-{uuid.uuid4().hex[:8]}")
    session.add(org)
    await session.flush()
    assert org.settings is None


async def test_org_settings_stored_as_jsonb(session: AsyncSession):
    org = Org(name=f"org-{uuid.uuid4().hex[:8]}", settings={"key": "val"})
    session.add(org)
    await session.flush()
    await session.refresh(org)
    assert org.settings["key"] == "val"


# ---------------------------------------------------------------------------
# User tests
# ---------------------------------------------------------------------------


async def test_user_create(session: AsyncSession):
    org = await make_org(session)
    email = f"user-{uuid.uuid4().hex[:8]}@test.com"
    user = User(org_id=org.id, email=email)
    session.add(user)
    await session.flush()
    assert user.email == email


async def test_user_email_unique(session: AsyncSession):
    org = await make_org(session)
    email = f"user-{uuid.uuid4().hex[:8]}@test.com"

    session.add(User(org_id=org.id, email=email))
    await session.flush()

    session.add(User(org_id=org.id, email=email))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


async def test_user_is_active_default(session: AsyncSession):
    org = await make_org(session)
    user = User(org_id=org.id, email=f"user-{uuid.uuid4().hex[:8]}@test.com")
    session.add(user)
    await session.flush()
    await session.refresh(user)
    assert user.is_active is True


async def test_user_org_id_fk(session: AsyncSession):
    nonexistent_org_id = uuid.uuid4()
    session.add(User(org_id=nonexistent_org_id, email=f"user-{uuid.uuid4().hex[:8]}@test.com"))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


async def test_user_password_hash_nullable(session: AsyncSession):
    org = await make_org(session)
    user = User(org_id=org.id, email=f"user-{uuid.uuid4().hex[:8]}@test.com")
    session.add(user)
    await session.flush()
    assert user.password_hash is None


# ---------------------------------------------------------------------------
# Membership tests
# ---------------------------------------------------------------------------


async def test_membership_create(session: AsyncSession):
    org = await make_org(session)
    user = await make_user(session, org_id=org.id)
    membership = Membership(org_id=org.id, user_id=user.id, role="admin")
    session.add(membership)
    await session.flush()
    assert membership.role == "admin"


async def test_membership_unique_org_user(session: AsyncSession):
    org = await make_org(session)
    user = await make_user(session, org_id=org.id)

    session.add(Membership(org_id=org.id, user_id=user.id, role="admin"))
    await session.flush()

    session.add(Membership(org_id=org.id, user_id=user.id, role="viewer"))
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


async def test_membership_different_orgs_same_user(session: AsyncSession):
    org_a = await make_org(session)
    org_b = await make_org(session)
    user = await make_user(session, org_id=org_a.id)

    session.add(Membership(org_id=org_a.id, user_id=user.id, role="admin"))
    session.add(Membership(org_id=org_b.id, user_id=user.id, role="viewer"))
    await session.flush()  # must not raise
