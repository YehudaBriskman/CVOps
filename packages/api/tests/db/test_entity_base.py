import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from cvops_api.db.models.auth import Org
from tests.db.conftest import make_org


async def test_id_auto_generated(session: AsyncSession):
    org = await make_org(session)
    session.add(org)
    await session.flush()
    assert org.id is not None
    assert isinstance(org.id, uuid.UUID)


async def test_created_at_set_on_insert(session: AsyncSession):
    org = await make_org(session)
    session.add(org)
    await session.flush()
    await session.refresh(org)
    assert org.created_at is not None
    assert org.created_at.tzinfo is not None


async def test_updated_at_set_on_insert(session: AsyncSession):
    org = await make_org(session)
    session.add(org)
    await session.flush()
    await session.refresh(org)
    assert org.updated_at is not None


async def test_created_by_defaults_none(session: AsyncSession):
    org = await make_org(session)
    session.add(org)
    await session.flush()
    await session.refresh(org)
    assert org.created_by is None


async def test_deleted_at_defaults_none(session: AsyncSession):
    org = await make_org(session)
    session.add(org)
    await session.flush()
    await session.refresh(org)
    assert org.deleted_at is None


async def test_soft_delete_sets_deleted_at(session: AsyncSession):
    org = await make_org(session)
    session.add(org)
    await session.flush()

    org.deleted_at = datetime.now(UTC)
    await session.flush()
    await session.refresh(org)

    assert org.deleted_at is not None
    result = await session.get(Org, org.id)
    assert result is not None


async def test_explicit_id_accepted(session: AsyncSession):
    explicit_id = uuid.uuid4()
    org = await make_org(session, id=explicit_id)
    session.add(org)
    await session.flush()
    await session.refresh(org)
    assert org.id == explicit_id


async def test_two_orgs_get_different_ids(session: AsyncSession):
    org_a = await make_org(session)
    org_b = await make_org(session)
    session.add(org_a)
    session.add(org_b)
    await session.flush()
    assert org_a.id != org_b.id
