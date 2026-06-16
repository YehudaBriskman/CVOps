"""Router test for listing an ontology's label classes.

GET /ontologies/{id}/classes returns the ontology's classes ordered by
sort_order, scoped to the caller's org. Mirrors test_runs.py: a minimal app
mounting only the ontologies router over the testcontainers Postgres.
"""

from __future__ import annotations

import uuid

import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from cvops_api.core.auth import get_current_user
from cvops_api.db.session import get_session
from cvops_api.db.models.auth import Org, User
from cvops_api.db.models.ontologies import LabelClass, Ontology
from cvops_api.db.models.projects import Project
from cvops_api.routers import ontologies


@pytest_asyncio.fixture
async def factory(postgres_url: str):
    engine = create_async_engine(postgres_url, echo=False)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


def _client(factory, current_user: User) -> AsyncClient:
    app = FastAPI()
    app.include_router(ontologies.router)

    async def _get_session_dep():
        async with factory() as sess:
            yield sess

    app.dependency_overrides[get_session] = _get_session_dep
    app.dependency_overrides[get_current_user] = lambda: current_user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed(factory):
    suffix = uuid.uuid4().hex[:8]
    async with factory() as s:
        org = Org(name=f"org-{suffix}")
        s.add(org)
        await s.flush()
        user = User(org_id=org.id, email=f"u-{suffix}@test.com")
        project = Project(org_id=org.id, name=f"proj-{suffix}")
        s.add_all([user, project])
        await s.flush()
        ont = Ontology(project_id=project.id, name="default")
        s.add(ont)
        await s.flush()
        # Insert out of order to prove the endpoint sorts by sort_order.
        s.add_all(
            [
                LabelClass(ontology_id=ont.id, class_key="car", display_name="Car", color="#0F0", sort_order=1),
                LabelClass(ontology_id=ont.id, class_key="plane", display_name="Plane", color="#F00", sort_order=0),
            ]
        )
        await s.commit()
        await s.refresh(user)
        return user, ont.id


async def test_list_classes_ordered_by_sort_order(factory) -> None:
    user, ont_id = await _seed(factory)
    async with _client(factory, user) as c:
        res = await c.get(f"/ontologies/{ont_id}/classes")
    assert res.status_code == 200
    body = res.json()
    assert [lc["class_key"] for lc in body] == ["plane", "car"]  # sort_order 0, 1


async def test_list_classes_missing_ontology_404(factory) -> None:
    user, _ = await _seed(factory)
    async with _client(factory, user) as c:
        res = await c.get(f"/ontologies/{uuid.uuid4()}/classes")
    assert res.status_code == 404


async def test_list_classes_cross_org_404(factory) -> None:
    _owner, ont_id = await _seed(factory)
    other, _ = await _seed(factory)
    async with _client(factory, other) as c:
        res = await c.get(f"/ontologies/{ont_id}/classes")
    assert res.status_code == 404
