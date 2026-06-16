"""Router tests for the project-scoped runs list.

Exercises `GET /projects/{id}/runs`: it returns the project's *parent* workflow
runs (`parent_run_id IS NULL`) newest-first, with an optional `?status=` filter
and a keyset cursor on `(created_at, id)`. Child step runs are excluded, and a
cross-org caller gets 404.

Pattern mirrors test_datasets.py: a minimal FastAPI app mounting only the runs
router, with `get_session`/`get_current_user` overridden onto the testcontainers
Postgres. `created_at` is seeded explicitly per run — Postgres `now()` returns
the transaction start time, so rows committed together would otherwise share a
timestamp and defeat chronological ordering.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, UTC

import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from cvops_api.core.auth import get_current_user
from cvops_api.db.session import get_session
from cvops_api.db.models.auth import Org, User
from cvops_api.db.models.labeling import LabelingJob
from cvops_api.db.models.projects import Project
from cvops_api.db.models.runs import Run
from cvops_api.routers import runs


@pytest_asyncio.fixture
async def factory(postgres_url: str):
    engine = create_async_engine(postgres_url, echo=False)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


def _client(factory, current_user: User) -> AsyncClient:
    app = FastAPI()
    app.include_router(runs.router)

    async def _get_session_dep():
        async with factory() as sess:
            yield sess

    app.dependency_overrides[get_session] = _get_session_dep
    app.dependency_overrides[get_current_user] = lambda: current_user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed(factory, *, n_parents: int = 0, statuses: list[str] | None = None):
    """Seed org + user + project. Create `n_parents` parent workflow runs with
    distinct ascending `created_at`, plus one child step run under the first
    parent (must be excluded by the list endpoint).

    Returns (user, project, [parent_run_id newest-first ...]).
    """
    suffix = uuid.uuid4().hex[:8]
    base = datetime(2026, 1, 1, tzinfo=UTC)
    parent_ids: list[uuid.UUID] = []
    async with factory() as s:
        org = Org(name=f"org-{suffix}")
        s.add(org)
        await s.flush()
        user = User(org_id=org.id, email=f"u-{suffix}@test.com")
        s.add(user)
        project = Project(org_id=org.id, name=f"proj-{suffix}")
        s.add(project)
        await s.flush()

        statuses = statuses or ["succeeded"] * n_parents
        for i in range(n_parents):
            parent = Run(
                project_id=project.id,
                kind="workflow",
                status=statuses[i],
                created_at=base + timedelta(minutes=i),
            )
            s.add(parent)
            await s.flush()
            parent_ids.append(parent.id)
            if i == 0:
                # A child step run that must never appear in the list.
                s.add(
                    Run(
                        project_id=project.id,
                        kind="step",
                        parent_run_id=parent.id,
                        step_type="step.extract_frames",
                        status="succeeded",
                        created_at=base + timedelta(minutes=i, seconds=30),
                    )
                )

        await s.commit()
        await s.refresh(user)
        await s.refresh(project)
        # Newest-first
        return user, project, list(reversed(parent_ids))


async def test_list_returns_parents_newest_first(factory) -> None:
    user, project, newest_first = await _seed(factory, n_parents=3)

    async with _client(factory, user) as c:
        res = await c.get(f"/projects/{project.id}/runs")

    assert res.status_code == 200
    body = res.json()
    ids = [item["id"] for item in body["items"]]
    assert ids == [str(rid) for rid in newest_first]
    assert all(item["kind"] == "workflow" for item in body["items"])


async def test_child_run_excluded(factory) -> None:
    user, project, _ = await _seed(factory, n_parents=2)

    async with _client(factory, user) as c:
        res = await c.get(f"/projects/{project.id}/runs")

    items = res.json()["items"]
    # 2 parents seeded + 1 child; only the 2 parents come back.
    assert len(items) == 2
    assert all(item["kind"] == "workflow" for item in items)


async def test_status_filter(factory) -> None:
    user, project, _ = await _seed(
        factory, n_parents=3, statuses=["failed", "succeeded", "failed"]
    )

    async with _client(factory, user) as c:
        res = await c.get(f"/projects/{project.id}/runs", params={"status": "failed"})

    items = res.json()["items"]
    assert len(items) == 2
    assert all(item["status"] == "failed" for item in items)


async def test_cursor_paginates(factory) -> None:
    user, project, newest_first = await _seed(factory, n_parents=3)

    async with _client(factory, user) as c:
        first = await c.get(f"/projects/{project.id}/runs", params={"limit": 2})
        assert first.status_code == 200
        page1 = first.json()
        assert [i["id"] for i in page1["items"]] == [str(r) for r in newest_first[:2]]
        assert page1["next_cursor"] is not None

        second = await c.get(
            f"/projects/{project.id}/runs",
            params={"limit": 2, "cursor": page1["next_cursor"]},
        )
        page2 = second.json()
        assert [i["id"] for i in page2["items"]] == [str(newest_first[2])]
        assert page2["next_cursor"] is None


async def test_cross_org_returns_404(factory) -> None:
    _owner, project, _ = await _seed(factory, n_parents=1)
    other, _p2, _ = await _seed(factory, n_parents=0)

    async with _client(factory, other) as c:
        res = await c.get(f"/projects/{project.id}/runs")

    assert res.status_code == 404


async def test_sync_gate_enqueues_doorbell(factory, fake_redis) -> None:
    """POST /runs/{id}/gates/{step}/sync emits the cvat_sync doorbell worker-cvat
    consumes to pull reviewed annotations (the manual webhook replacement)."""
    suffix = uuid.uuid4().hex[:8]
    async with factory() as s:
        org = Org(name=f"org-{suffix}")
        s.add(org)
        await s.flush()
        user = User(org_id=org.id, email=f"u-{suffix}@test.com")
        project = Project(org_id=org.id, name=f"proj-{suffix}")
        s.add_all([user, project])
        await s.flush()
        parent = Run(project_id=project.id, kind="workflow", status="waiting")
        s.add(parent)
        await s.flush()
        child = Run(
            project_id=project.id,
            parent_run_id=parent.id,
            kind="step",
            status="waiting",
            step_id="review_node",
            step_type="step.human_review",
        )
        s.add(child)
        await s.flush()
        s.add(
            LabelingJob(
                project_id=project.id,
                run_id=child.id,
                step_id="review_node",
                cvat_task_id=4242,
                cvat_job_ids=[99],
                status="pushed",
                sample_count=1,
            )
        )
        await s.commit()
        await s.refresh(user)
        parent_id = parent.id

    async with _client(factory, user) as c:
        res = await c.post(f"/runs/{parent_id}/gates/review_node/sync")

    assert res.status_code == 202
    assert res.json()["cvat_task_id"] == 4242
    assert await fake_redis.xlen(runs.CVAT_STREAM) == 1
    _id, fields = (await fake_redis.xrange(runs.CVAT_STREAM))[0]
    assert fields == {"kind": "cvat_sync", "cvat_task_id": "4242"}


async def test_sync_gate_without_waiting_gate_404(factory, fake_redis) -> None:
    user, _project, parents = await _seed(factory, n_parents=1)

    async with _client(factory, user) as c:
        res = await c.post(f"/runs/{parents[0]}/gates/no_such_step/sync")

    assert res.status_code == 404
    assert await fake_redis.xlen(runs.CVAT_STREAM) == 0
