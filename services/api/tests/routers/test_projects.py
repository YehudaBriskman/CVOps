"""Router tests for `PATCH /projects/{id}`, focused on the partial-update
semantics of `default_ingest_workflow_id`.

The field is nullable, so the handler must distinguish three request shapes:
omitted (leave untouched), an explicit workflow id (set), and an explicit null
(clear). The last is the one that's easy to get wrong with an `is not None`
guard — these tests pin all three.

Same pattern as test_data_sources: a minimal FastAPI app mounting only the
projects router, with get_session/get_current_user overridden onto the
testcontainers Postgres.
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

from cvops_api.core.auth import get_current_user
from cvops_api.db.session import get_session
from cvops_api.db.models.auth import Org, User
from cvops_api.db.models.projects import Project
from cvops_api.db.models.workflows import Workflow
from cvops_api.routers import projects


@pytest_asyncio.fixture
async def factory(postgres_url: str):
    engine = create_async_engine(postgres_url, echo=False)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


def _client(factory, current_user: User) -> AsyncClient:
    app = FastAPI()
    # main.py mounts the projects router under /projects; mirror that here so
    # the route paths match production.
    app.include_router(projects.router, prefix="/projects")

    async def _get_session_dep():
        async with factory() as sess:
            yield sess

    app.dependency_overrides[get_session] = _get_session_dep
    app.dependency_overrides[get_current_user] = lambda: current_user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed(factory) -> tuple[User, Project, Workflow]:
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
        wf = Workflow(
            project_id=project.id,
            name=f"ingest-{suffix}",
            definition={"steps": [], "edges": []},
        )
        s.add(wf)
        await s.commit()
        await s.refresh(user)
        await s.refresh(project)
        await s.refresh(wf)
        return user, project, wf


async def test_set_default_ingest_workflow(factory) -> None:
    user, project, wf = await _seed(factory)

    async with _client(factory, user) as c:
        res = await c.patch(
            f"/projects/{project.id}",
            json={"default_ingest_workflow_id": str(wf.id)},
        )

    assert res.status_code == 200
    assert res.json()["default_ingest_workflow_id"] == str(wf.id)

    async with factory() as s:
        refreshed = await s.get(Project, project.id)
        assert refreshed.default_ingest_workflow_id == wf.id


async def test_explicit_null_clears_default_ingest_workflow(factory) -> None:
    user, project, wf = await _seed(factory)
    async with factory() as s:
        proj = await s.get(Project, project.id)
        proj.default_ingest_workflow_id = wf.id
        await s.commit()

    async with _client(factory, user) as c:
        res = await c.patch(
            f"/projects/{project.id}",
            json={"default_ingest_workflow_id": None},
        )

    assert res.status_code == 200
    assert res.json()["default_ingest_workflow_id"] is None

    async with factory() as s:
        refreshed = await s.get(Project, project.id)
        assert refreshed.default_ingest_workflow_id is None


async def test_omitted_field_preserves_default_ingest_workflow(factory) -> None:
    user, project, wf = await _seed(factory)
    async with factory() as s:
        proj = await s.get(Project, project.id)
        proj.default_ingest_workflow_id = wf.id
        await s.commit()

    # A PATCH that doesn't mention the field must leave it intact.
    async with _client(factory, user) as c:
        res = await c.patch(
            f"/projects/{project.id}",
            json={"name": "renamed"},
        )

    assert res.status_code == 200
    assert res.json()["default_ingest_workflow_id"] == str(wf.id)
    assert res.json()["name"] == "renamed"

    async with factory() as s:
        refreshed = await s.get(Project, project.id)
        assert refreshed.default_ingest_workflow_id == wf.id
