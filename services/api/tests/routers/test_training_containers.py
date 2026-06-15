"""Router tests for the training-containers CRUD + /validate endpoints.

A training container is a per-project, reusable training environment (a Docker
`image` + an `icd_config` Interface Contract Document). The router exposes full
CRUD plus a `/validate` endpoint that checks a candidate icd_config instance
against the container's stored icd_config (used as a JSON Schema).

Same minimal-app pattern as test_datasets_train / test_projects: mount only the
training_containers router, override session/current_user onto the
testcontainers Postgres. Org/project scoping is asserted via a cross-org 404.
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
from cvops_api.db.models.models import TrainingContainer
from cvops_api.routers import training_containers


@pytest_asyncio.fixture
async def factory(postgres_url: str):
    engine = create_async_engine(postgres_url, echo=False)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


def _client(factory, current_user: User) -> AsyncClient:
    app = FastAPI()
    # main.py mounts this router with just the /api/v1 prefix; the routes define
    # their own full paths. Mount bare here so paths match.
    app.include_router(training_containers.router)

    async def _get_session_dep():
        async with factory() as sess:
            yield sess

    app.dependency_overrides[get_session] = _get_session_dep
    app.dependency_overrides[get_current_user] = lambda: current_user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed_user_project(factory) -> tuple[User, Project]:
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


async def test_crud_happy_path(factory) -> None:
    user, project = await _seed_user_project(factory)

    async with _client(factory, user) as c:
        # create
        res = await c.post(
            f"/projects/{project.id}/training-containers",
            json={
                "name": "yolo-trainer",
                "description": "ultralytics yolo",
                "image": "ghcr.io/example/trainer:latest",
                "icd_config": {"inputs": {"epochs": {"env": "EPOCHS"}}},
            },
        )
        assert res.status_code == 201, res.text
        tc = res.json()
        tc_id = tc["id"]
        assert tc["name"] == "yolo-trainer"
        assert tc["project_id"] == str(project.id)
        assert tc["image"] == "ghcr.io/example/trainer:latest"

        # get
        res = await c.get(f"/training-containers/{tc_id}")
        assert res.status_code == 200
        assert res.json()["id"] == tc_id

        # list
        res = await c.get(f"/projects/{project.id}/training-containers")
        assert res.status_code == 200
        assert [t["id"] for t in res.json()] == [tc_id]

        # patch
        res = await c.patch(
            f"/training-containers/{tc_id}",
            json={"description": "updated", "image": "ghcr.io/example/trainer:v2"},
        )
        assert res.status_code == 200
        assert res.json()["description"] == "updated"
        assert res.json()["image"] == "ghcr.io/example/trainer:v2"

        # delete (soft) — then it's gone from get + list
        res = await c.delete(f"/training-containers/{tc_id}")
        assert res.status_code == 204
        assert (await c.get(f"/training-containers/{tc_id}")).status_code == 404
        res = await c.get(f"/projects/{project.id}/training-containers")
        assert res.status_code == 200
        assert res.json() == []


async def test_cross_org_get_404(factory) -> None:
    """A container under another org's project is invisible."""
    _owner, project = await _seed_user_project(factory)
    other_user, _other_project = await _seed_user_project(factory)

    async with factory() as s:
        tc = TrainingContainer(
            project_id=project.id,
            name="owned",
            image="ghcr.io/example/trainer:latest",
            icd_config={},
        )
        s.add(tc)
        await s.commit()
        await s.refresh(tc)

    async with _client(factory, other_user) as c:
        assert (await c.get(f"/training-containers/{tc.id}")).status_code == 404
        # And the list under the foreign project 404s (project scoping).
        res = await c.get(f"/projects/{project.id}/training-containers")
        assert res.status_code == 404


async def test_create_under_foreign_project_404(factory) -> None:
    _owner, project = await _seed_user_project(factory)
    other_user, _other_project = await _seed_user_project(factory)

    async with _client(factory, other_user) as c:
        res = await c.post(
            f"/projects/{project.id}/training-containers",
            json={"name": "x", "image": "img", "icd_config": {}},
        )
        assert res.status_code == 404


async def test_validate_valid_and_invalid(factory) -> None:
    user, project = await _seed_user_project(factory)

    async with _client(factory, user) as c:
        res = await c.post(
            f"/projects/{project.id}/training-containers",
            json={
                "name": "schema-tc",
                "image": "img",
                "icd_config": {
                    "type": "object",
                    "properties": {"epochs": {"type": "integer"}},
                    "required": ["epochs"],
                },
            },
        )
        assert res.status_code == 201, res.text
        tc_id = res.json()["id"]

        # valid instance
        res = await c.post(
            f"/training-containers/{tc_id}/validate",
            json={"icd_config": {"epochs": 5}},
        )
        assert res.status_code == 200
        assert res.json() == {"valid": True, "errors": []}

        # invalid instance (wrong type)
        res = await c.post(
            f"/training-containers/{tc_id}/validate",
            json={"icd_config": {"epochs": "not-an-int"}},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["valid"] is False
        assert body["errors"]
