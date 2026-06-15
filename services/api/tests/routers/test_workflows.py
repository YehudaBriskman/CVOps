"""Router tests for the workflows router.

Covers list (empty / multiple / soft-delete filtered), create (valid definition
plus unknown-step-type rejection against the registry), get (404 + cross-org
404), patch (rename + definition update with version bump), and delete
(soft-delete then absent from list).

Same pattern as test_projects / test_data_sources: a minimal FastAPI app
mounting only the workflows router (with NO prefix — the router declares full
inline paths like /projects/{id}/workflows and /workflows/{id}), with
get_session / get_current_user overridden onto the testcontainers Postgres.
"""

from __future__ import annotations

import uuid
from datetime import datetime, UTC

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
from cvops_api.db.models.projects import Project
from cvops_api.db.models.workflows import Workflow
from cvops_api.routers import workflows


@pytest_asyncio.fixture
async def factory(postgres_url: str):
    engine = create_async_engine(postgres_url, echo=False)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


def _client(factory, current_user: User) -> AsyncClient:
    app = FastAPI()
    # Router declares full inline paths; mount with no prefix to match prod.
    app.include_router(workflows.router)

    async def _get_session_dep():
        async with factory() as sess:
            yield sess

    app.dependency_overrides[get_session] = _get_session_dep
    app.dependency_overrides[get_current_user] = lambda: current_user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed_project(factory) -> tuple[User, Project]:
    suffix = uuid.uuid4().hex[:8]
    async with factory() as s:
        org = Org(name=f"org-{suffix}")
        s.add(org)
        await s.flush()
        user = User(org_id=org.id, email=f"u-{suffix}@test.com")
        s.add(user)
        project = Project(org_id=org.id, name=f"proj-{suffix}")
        s.add(project)
        await s.commit()
        await s.refresh(user)
        await s.refresh(project)
        return user, project


async def _add_workflow(
    factory, project: Project, *, name: str | None = None, deleted: bool = False
) -> Workflow:
    async with factory() as s:
        wf = Workflow(
            project_id=project.id,
            name=name or f"wf-{uuid.uuid4().hex[:8]}",
            definition={"steps": [], "edges": []},
        )
        if deleted:
            wf.deleted_at = datetime.now(UTC)
        s.add(wf)
        await s.commit()
        await s.refresh(wf)
        return wf


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


async def test_list_empty(factory) -> None:
    user, project = await _seed_project(factory)
    async with _client(factory, user) as c:
        res = await c.get(f"/projects/{project.id}/workflows")
    assert res.status_code == 200, res.text
    assert res.json() == []


async def test_list_returns_multiple(factory) -> None:
    user, project = await _seed_project(factory)
    wf1 = await _add_workflow(factory, project)
    wf2 = await _add_workflow(factory, project)

    async with _client(factory, user) as c:
        res = await c.get(f"/projects/{project.id}/workflows")

    assert res.status_code == 200, res.text
    ids = {item["id"] for item in res.json()}
    assert ids == {str(wf1.id), str(wf2.id)}


async def test_list_filters_soft_deleted(factory) -> None:
    user, project = await _seed_project(factory)
    live = await _add_workflow(factory, project)
    gone = await _add_workflow(factory, project, deleted=True)

    async with _client(factory, user) as c:
        res = await c.get(f"/projects/{project.id}/workflows")

    assert res.status_code == 200, res.text
    ids = {item["id"] for item in res.json()}
    assert str(live.id) in ids
    assert str(gone.id) not in ids


async def test_list_cross_org_project_404(factory) -> None:
    _owner, project = await _seed_project(factory)
    other, _p2 = await _seed_project(factory)
    async with _client(factory, other) as c:
        res = await c.get(f"/projects/{project.id}/workflows")
    assert res.status_code == 404, res.text


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


async def test_create_valid_empty_definition(factory) -> None:
    user, project = await _seed_project(factory)
    async with _client(factory, user) as c:
        res = await c.post(
            f"/projects/{project.id}/workflows",
            json={"name": "my-wf", "definition": {"steps": [], "edges": []}},
        )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["name"] == "my-wf"
    assert body["version"] == 1
    assert body["project_id"] == str(project.id)


async def test_create_valid_with_registered_step(factory, echo_step) -> None:
    user, project = await _seed_project(factory)
    definition = {
        "steps": [{"id": "s1", "type": "test.echo", "config": {}}],
        "edges": [],
    }
    async with _client(factory, user) as c:
        res = await c.post(
            f"/projects/{project.id}/workflows",
            json={"name": "wf-echo", "definition": definition},
        )
    assert res.status_code == 201, res.text
    assert res.json()["definition"] == definition


async def test_create_unknown_step_type_422(factory) -> None:
    user, project = await _seed_project(factory)
    definition = {
        "steps": [{"id": "s1", "type": "does.not.exist", "config": {}}],
        "edges": [],
    }
    async with _client(factory, user) as c:
        res = await c.post(
            f"/projects/{project.id}/workflows",
            json={"name": "wf-bad", "definition": definition},
        )
    assert res.status_code == 422, res.text


async def test_create_cross_org_project_404(factory) -> None:
    _owner, project = await _seed_project(factory)
    other, _p2 = await _seed_project(factory)
    async with _client(factory, other) as c:
        res = await c.post(
            f"/projects/{project.id}/workflows",
            json={"name": "x", "definition": {"steps": [], "edges": []}},
        )
    assert res.status_code == 404, res.text


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


async def test_get_workflow(factory) -> None:
    user, project = await _seed_project(factory)
    wf = await _add_workflow(factory, project, name="findme")
    async with _client(factory, user) as c:
        res = await c.get(f"/workflows/{wf.id}")
    assert res.status_code == 200, res.text
    assert res.json()["name"] == "findme"


async def test_get_unknown_workflow_404(factory) -> None:
    user, _project = await _seed_project(factory)
    async with _client(factory, user) as c:
        res = await c.get(f"/workflows/{uuid.uuid4()}")
    assert res.status_code == 404, res.text


async def test_get_cross_org_404(factory) -> None:
    _owner, project = await _seed_project(factory)
    wf = await _add_workflow(factory, project)
    other, _p2 = await _seed_project(factory)
    async with _client(factory, other) as c:
        res = await c.get(f"/workflows/{wf.id}")
    assert res.status_code == 404, res.text


# ---------------------------------------------------------------------------
# patch
# ---------------------------------------------------------------------------


async def test_patch_rename_keeps_version(factory) -> None:
    user, project = await _seed_project(factory)
    wf = await _add_workflow(factory, project, name="old")
    async with _client(factory, user) as c:
        res = await c.patch(f"/workflows/{wf.id}", json={"name": "new"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["name"] == "new"
    assert body["version"] == 1  # name-only patch must not bump version


async def test_patch_definition_bumps_version(factory) -> None:
    user, project = await _seed_project(factory)
    wf = await _add_workflow(factory, project)
    new_def = {"steps": [], "edges": []}
    async with _client(factory, user) as c:
        res = await c.patch(f"/workflows/{wf.id}", json={"definition": new_def})
    assert res.status_code == 200, res.text
    assert res.json()["version"] == 2  # bumped from 1


async def test_patch_definition_unknown_step_422(factory) -> None:
    user, project = await _seed_project(factory)
    wf = await _add_workflow(factory, project)
    bad_def = {"steps": [{"id": "s1", "type": "nope"}], "edges": []}
    async with _client(factory, user) as c:
        res = await c.patch(f"/workflows/{wf.id}", json={"definition": bad_def})
    assert res.status_code == 422, res.text


async def test_patch_cross_org_404(factory) -> None:
    _owner, project = await _seed_project(factory)
    wf = await _add_workflow(factory, project)
    other, _p2 = await _seed_project(factory)
    async with _client(factory, other) as c:
        res = await c.patch(f"/workflows/{wf.id}", json={"name": "x"})
    assert res.status_code == 404, res.text


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


async def test_delete_soft_deletes_and_absent_from_list(factory) -> None:
    user, project = await _seed_project(factory)
    wf = await _add_workflow(factory, project)

    async with _client(factory, user) as c:
        res = await c.delete(f"/workflows/{wf.id}")
        assert res.status_code == 204, res.text

        listed = await c.get(f"/projects/{project.id}/workflows")
        assert listed.status_code == 200, listed.text
        ids = {item["id"] for item in listed.json()}
        assert str(wf.id) not in ids

        # Direct get still resolves the row (handler doesn't filter deleted),
        # but the list view excludes it.
        got = await c.get(f"/workflows/{wf.id}")
        assert got.status_code == 200, got.text


async def test_delete_unknown_404(factory) -> None:
    user, _project = await _seed_project(factory)
    async with _client(factory, user) as c:
        res = await c.delete(f"/workflows/{uuid.uuid4()}")
    assert res.status_code == 404, res.text


async def test_delete_cross_org_404(factory) -> None:
    _owner, project = await _seed_project(factory)
    wf = await _add_workflow(factory, project)
    other, _p2 = await _seed_project(factory)
    async with _client(factory, other) as c:
        res = await c.delete(f"/workflows/{wf.id}")
    assert res.status_code == 404, res.text
