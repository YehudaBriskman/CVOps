"""Router tests for the data-source upload-confirmation flow.

These exercise `POST /data-sources/{id}/confirm-upload`, the backend-owned
trigger point: it registers the uploaded blob, flips the data source to
`uploaded`, and — when the project names a `default_ingest_workflow_id` — auto
-dispatches a workflow run.

Pattern (first router test besides /internal): a minimal FastAPI app mounting
only the data_sources router, with `get_session`/`get_current_user` overridden
onto the testcontainers Postgres, `get_storage` faked, and `execute_workflow`
patched to a recording no-op so the BackgroundTask can't touch the real DB.
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
from unittest.mock import patch

from cvops_api.core.auth import get_current_user
from cvops_api.db.session import get_session
from cvops_api.db.models.auth import Org, User
from cvops_api.db.models.blobs import Blob
from cvops_api.db.models.projects import Project
from cvops_api.db.models.samples import DataSource
from cvops_api.db.models.runs import Run
from cvops_api.db.models.workflows import Workflow
from cvops_api.routers import data_sources


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeStorage:
    """Stand-in for S3Backend. promote_upload returns deterministic metadata
    and the canonical content-addressed key, without touching any store."""

    async def promote_upload(self, upload_id: str, blob_hash: str):
        hex_part = blob_hash.removeprefix("sha256:")
        key = f"blobs/{hex_part[:2]}/{hex_part[2:]}"
        return 4096, "video/mp4", key


_HASH_A = "sha256:" + "a" * 64
_HASH_B = "sha256:" + "b" * 64


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def factory(postgres_url: str):
    engine = create_async_engine(postgres_url, echo=False)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
def patched_storage_and_dispatch():
    """Fake the storage backend and capture background dispatches."""
    dispatched: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def _record(run_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        dispatched.append((run_id, actor_id))

    with (
        patch.object(data_sources, "get_storage", lambda: _FakeStorage()),
        patch.object(data_sources, "execute_workflow", _record),
    ):
        yield dispatched


def _client(factory, current_user: User) -> AsyncClient:
    app = FastAPI()
    app.include_router(data_sources.router)

    async def _get_session_dep():
        async with factory() as sess:
            yield sess

    app.dependency_overrides[get_session] = _get_session_dep
    app.dependency_overrides[get_current_user] = lambda: current_user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed(
    factory,
    *,
    with_workflow: bool,
) -> tuple[User, Project, DataSource]:
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
        if with_workflow:
            wf = Workflow(
                project_id=project.id,
                name=f"ingest-{suffix}",
                definition={"steps": [], "edges": []},
            )
            s.add(wf)
            await s.flush()
            project.default_ingest_workflow_id = wf.id
        ds = DataSource(project_id=project.id, type="video", status="pending")
        s.add(ds)
        await s.commit()
        await s.refresh(user)
        await s.refresh(project)
        await s.refresh(ds)
        return user, project, ds


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_confirm_without_default_workflow_registers_blob(factory) -> None:
    user, _project, ds = await _seed(factory, with_workflow=False)

    async with _client(factory, user) as c:
        res = await c.post(
            f"/data-sources/{ds.id}/confirm-upload", json={"blob_hash": _HASH_A}
        )

    assert res.status_code == 200
    body = res.json()
    assert body["run_id"] is None
    assert body["data_source"]["status"] == "uploaded"
    assert body["data_source"]["blob_hash"] == _HASH_A

    async with factory() as s:
        blob = await s.get(Blob, _HASH_A)
        assert blob is not None
        assert blob.size_bytes == 4096
        assert blob.media_type == "video/mp4"
        runs = (await s.execute(select(Run))).scalars().all()
        assert runs == []


async def test_confirm_with_default_workflow_dispatches_run(
    factory, patched_storage_and_dispatch
) -> None:
    dispatched = patched_storage_and_dispatch
    user, _project, ds = await _seed(factory, with_workflow=True)

    async with _client(factory, user) as c:
        res = await c.post(
            f"/data-sources/{ds.id}/confirm-upload", json={"blob_hash": _HASH_A}
        )

    assert res.status_code == 200
    run_id = res.json()["run_id"]
    assert run_id is not None

    async with factory() as s:
        run = await s.get(Run, uuid.UUID(run_id))
        assert run is not None
        assert run.status == "pending"
        assert run.kind == "workflow"
        assert run.input_refs == {"params": {"source_id": str(ds.id)}}

    # Background task was scheduled exactly once for this run.
    assert [d[0] for d in dispatched] == [uuid.UUID(run_id)]


async def test_confirm_is_idempotent(factory, patched_storage_and_dispatch) -> None:
    dispatched = patched_storage_and_dispatch
    user, project, ds = await _seed(factory, with_workflow=True)

    async with _client(factory, user) as c:
        first = await c.post(
            f"/data-sources/{ds.id}/confirm-upload", json={"blob_hash": _HASH_A}
        )
        second = await c.post(
            f"/data-sources/{ds.id}/confirm-upload", json={"blob_hash": _HASH_A}
        )

    assert first.status_code == second.status_code == 200
    assert first.json()["run_id"] is not None
    assert second.json()["run_id"] is None  # no re-dispatch

    # Scope to this project — the testcontainers DB is shared across the session.
    async with factory() as s:
        runs = (
            (await s.execute(select(Run).where(Run.project_id == project.id)))
            .scalars()
            .all()
        )
        assert len(runs) == 1
    assert len(dispatched) == 1


async def test_confirm_cross_org_returns_404(factory) -> None:
    _owner, _project, ds = await _seed(factory, with_workflow=False)
    # A user from a different org must not be able to confirm this data source.
    other, _p2, _ds2 = await _seed(factory, with_workflow=False)

    async with _client(factory, other) as c:
        res = await c.post(
            f"/data-sources/{ds.id}/confirm-upload", json={"blob_hash": _HASH_A}
        )

    assert res.status_code == 404


async def test_confirm_dedups_blob_across_sources(factory) -> None:
    user, project, ds1 = await _seed(factory, with_workflow=False)
    # Second data source in the same project, same content hash.
    async with factory() as s:
        ds2 = DataSource(project_id=project.id, type="video", status="pending")
        s.add(ds2)
        await s.commit()
        ds2_id = ds2.id

    async with _client(factory, user) as c:
        r1 = await c.post(
            f"/data-sources/{ds1.id}/confirm-upload", json={"blob_hash": _HASH_A}
        )
        r2 = await c.post(
            f"/data-sources/{ds2_id}/confirm-upload", json={"blob_hash": _HASH_A}
        )

    assert r1.status_code == r2.status_code == 200

    async with factory() as s:
        blobs = (
            (await s.execute(select(Blob).where(Blob.hash == _HASH_A)))
            .scalars()
            .all()
        )
        assert len(blobs) == 1  # ON CONFLICT DO NOTHING
