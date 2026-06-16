"""Router tests for the tags surface.

Covers list, create (incl. per-project uniqueness behaviour), patch, delete
(soft-delete), and removing a tag from a sample (DELETE
/samples/{id}/tags/{tag_id}). The add-tag path is already covered in
test_samples_curation; not duplicated here.

Pattern mirrors test_projects/test_data_sources: a minimal app mounting the
tags (and samples, for tag application) routers with get_session/
get_current_user overridden onto the testcontainers Postgres.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from cvops_api.core.auth import get_current_user
from cvops_api.db.session import get_session
from cvops_api.db.models.auth import Org, User
from cvops_api.db.models.blobs import Blob
from cvops_api.db.models.projects import Project
from cvops_api.db.models.samples import DataSource, Sample
from cvops_api.db.models.tags import SampleTag, Tag
from cvops_api.routers import tags, samples


@pytest_asyncio.fixture
async def factory(postgres_url: str):
    engine = create_async_engine(postgres_url, echo=False)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


def _client(factory, current_user: User) -> AsyncClient:
    app = FastAPI()
    app.include_router(tags.router)
    app.include_router(samples.router)

    async def _get_session_dep():
        async with factory() as sess:
            yield sess

    app.dependency_overrides[get_session] = _get_session_dep
    app.dependency_overrides[get_current_user] = lambda: current_user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _hash() -> str:
    return "sha256:" + uuid.uuid4().hex.ljust(64, "0")


async def _seed(factory, *, n_samples: int = 0):
    """Create org/user/project/source and n samples. Returns (user, project, [sample_ids])."""
    suffix = uuid.uuid4().hex[:8]
    async with factory() as s:
        org = Org(name=f"org-{suffix}")
        s.add(org)
        await s.flush()
        user = User(org_id=org.id, email=f"u-{suffix}@test.com")
        s.add(user)
        project = Project(org_id=org.id, name=f"proj-{suffix}")
        s.add(project)
        await s.flush()
        source = DataSource(project_id=project.id, type="video")
        s.add(source)
        await s.flush()
        sample_ids: list[uuid.UUID] = []
        for i in range(n_samples):
            h = _hash()
            s.add(
                Blob(
                    hash=h,
                    storage_backend="s3",
                    storage_key=f"k/{h}",
                    size_bytes=1,
                    media_type="image/jpeg",
                )
            )
            await s.flush()
            smp = Sample(
                project_id=project.id,
                blob_hash=h,
                source_id=source.id,
                width=100,
                height=100,
                frame_index=i,
            )
            s.add(smp)
            await s.flush()
            sample_ids.append(smp.id)
        await s.commit()
        await s.refresh(user)
        await s.refresh(project)
        return user, project, sample_ids


async def test_create_and_list_tags(factory) -> None:
    user, project, _ = await _seed(factory)
    async with _client(factory, user) as c:
        a = await c.post(f"/projects/{project.id}/tags", json={"name": "zeta", "color": "#f00"})
        assert a.status_code == 201, a.text
        assert a.json()["name"] == "zeta"
        assert a.json()["color"] == "#f00"

        # Default color when omitted.
        b = await c.post(f"/projects/{project.id}/tags", json={"name": "alpha"})
        assert b.status_code == 201, b.text
        assert b.json()["color"] == "#888888"

        listed = await c.get(f"/projects/{project.id}/tags")
        assert listed.status_code == 200, listed.text
        names = [t["name"] for t in listed.json()]
        # Ordered by name.
        assert names == ["alpha", "zeta"]


async def test_create_duplicate_name_conflicts(factory) -> None:
    """Tag name is unique per project (uq_tags_project_name). A second create
    with the same name in the same project must not silently succeed as a
    duplicate row."""
    user, project, _ = await _seed(factory)
    async with _client(factory, user) as c:
        first = await c.post(f"/projects/{project.id}/tags", json={"name": "dup"})
        assert first.status_code == 201, first.text
        # KNOWN PRODUCT BUG (see report): create_tag does not catch the unique
        # constraint violation, so the second create raises an uncaught
        # IntegrityError instead of returning a 409/422. The ASGI transport
        # re-raises app exceptions, so the request errors out here. Pinning the
        # current behaviour; the fix is to map the IntegrityError to a 409.
        with pytest.raises(IntegrityError):
            await c.post(f"/projects/{project.id}/tags", json={"name": "dup"})

    # Only one row exists for that name in the project.
    async with factory() as s:
        rows = (
            (await s.execute(select(Tag).where(Tag.project_id == project.id, Tag.name == "dup")))
            .scalars()
            .all()
        )
        assert len(rows) == 1


async def test_patch_tag(factory) -> None:
    user, project, _ = await _seed(factory)
    async with _client(factory, user) as c:
        created = await c.post(f"/projects/{project.id}/tags", json={"name": "old"})
        tid = created.json()["id"]

        res = await c.patch(f"/tags/{tid}", json={"name": "new", "color": "#0f0"})
        assert res.status_code == 200, res.text
        assert res.json()["name"] == "new"
        assert res.json()["color"] == "#0f0"

    async with factory() as s:
        refreshed = await s.get(Tag, uuid.UUID(tid))
        assert refreshed.name == "new"
        assert refreshed.color == "#0f0"


async def test_delete_tag_soft_deletes(factory) -> None:
    user, project, _ = await _seed(factory)
    async with _client(factory, user) as c:
        created = await c.post(f"/projects/{project.id}/tags", json={"name": "gone"})
        tid = created.json()["id"]

        d = await c.delete(f"/tags/{tid}")
        assert d.status_code == 204, d.text

        listed = await c.get(f"/projects/{project.id}/tags")
        assert [t["id"] for t in listed.json()] == []

    async with factory() as s:
        row = await s.get(Tag, uuid.UUID(tid))
        assert row is not None
        assert row.deleted_at is not None


async def test_remove_tag_from_sample(factory) -> None:
    user, project, ids = await _seed(factory, n_samples=1)
    sid = ids[0]
    async with _client(factory, user) as c:
        tag = await c.post(f"/projects/{project.id}/tags", json={"name": "blurry"})
        tid = tag.json()["id"]

        # Apply the tag (covered elsewhere, used here as setup).
        applied = await c.post(f"/samples/{sid}/tags", json={"tag_ids": [tid]})
        assert applied.status_code == 200, applied.text
        assert [t["id"] for t in applied.json()["tags"]] == [tid]

        # Remove it.
        rm = await c.delete(f"/samples/{sid}/tags/{tid}")
        assert rm.status_code == 204, rm.text

        got = await c.get(f"/samples/{sid}")
        assert got.json()["tags"] == []

    async with factory() as s:
        rows = (
            (
                await s.execute(
                    select(SampleTag).where(
                        SampleTag.sample_id == sid, SampleTag.tag_id == uuid.UUID(tid)
                    )
                )
            )
            .scalars()
            .all()
        )
        assert rows == []
