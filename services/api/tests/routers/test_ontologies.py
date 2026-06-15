"""Router tests for the ontologies router.

Covers list (empty / multiple / soft-delete filtering), create, get (404 +
cross-org 404), and the label-class lifecycle: create (incl. 409 on duplicate
class_key/sort_order), update, and delete (a hard delete in this handler).

Same pattern as test_projects/test_data_sources: a minimal FastAPI app mounting
only the ontologies router with get_session/get_current_user overridden onto the
testcontainers Postgres. The router defines full inline paths, so it is mounted
with NO prefix (mirrors main.py's bare /api/v1 mount).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

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


async def _seed(factory) -> tuple[User, Project]:
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


# ── list ────────────────────────────────────────────────────────────────────


async def test_list_empty(factory) -> None:
    user, project = await _seed(factory)
    async with _client(factory, user) as c:
        res = await c.get(f"/projects/{project.id}/ontologies")
    assert res.status_code == 200, res.text
    assert res.json() == []


async def test_list_multiple_excludes_soft_deleted(factory) -> None:
    user, project = await _seed(factory)
    async with factory() as s:
        live = Ontology(project_id=project.id, name="live")
        deleted = Ontology(project_id=project.id, name="gone", deleted_at=datetime.now(UTC))
        s.add_all([live, deleted])
        await s.commit()
        live_id = live.id

    async with _client(factory, user) as c:
        res = await c.get(f"/projects/{project.id}/ontologies")

    assert res.status_code == 200, res.text
    body = res.json()
    assert [o["id"] for o in body] == [str(live_id)]
    assert body[0]["version"] == 1


async def test_list_project_not_found(factory) -> None:
    user, _project = await _seed(factory)
    async with _client(factory, user) as c:
        res = await c.get(f"/projects/{uuid.uuid4()}/ontologies")
    assert res.status_code == 404, res.text


async def test_list_cross_org_404(factory) -> None:
    _owner, project = await _seed(factory)
    other, _p2 = await _seed(factory)
    async with _client(factory, other) as c:
        res = await c.get(f"/projects/{project.id}/ontologies")
    assert res.status_code == 404, res.text


# ── create ──────────────────────────────────────────────────────────────────


async def test_create_ontology(factory) -> None:
    user, project = await _seed(factory)
    async with _client(factory, user) as c:
        res = await c.post(f"/projects/{project.id}/ontologies", json={"name": "objects"})
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["name"] == "objects"
    assert body["project_id"] == str(project.id)
    assert body["version"] == 1


async def test_create_cross_org_404(factory) -> None:
    _owner, project = await _seed(factory)
    other, _p2 = await _seed(factory)
    async with _client(factory, other) as c:
        res = await c.post(f"/projects/{project.id}/ontologies", json={"name": "objects"})
    assert res.status_code == 404, res.text


# ── get ─────────────────────────────────────────────────────────────────────


async def test_get_ontology(factory) -> None:
    user, project = await _seed(factory)
    async with factory() as s:
        ont = Ontology(project_id=project.id, name="objects")
        s.add(ont)
        await s.commit()
        ont_id = ont.id

    async with _client(factory, user) as c:
        res = await c.get(f"/ontologies/{ont_id}")
    assert res.status_code == 200, res.text
    assert res.json()["id"] == str(ont_id)


async def test_get_ontology_404(factory) -> None:
    user, _project = await _seed(factory)
    async with _client(factory, user) as c:
        res = await c.get(f"/ontologies/{uuid.uuid4()}")
    assert res.status_code == 404, res.text


async def test_get_ontology_cross_org_404(factory) -> None:
    _owner, project = await _seed(factory)
    other, _p2 = await _seed(factory)
    async with factory() as s:
        ont = Ontology(project_id=project.id, name="objects")
        s.add(ont)
        await s.commit()
        ont_id = ont.id

    async with _client(factory, other) as c:
        res = await c.get(f"/ontologies/{ont_id}")
    assert res.status_code == 404, res.text


# ── label classes ───────────────────────────────────────────────────────────


async def _make_ontology(factory, project: Project) -> uuid.UUID:
    async with factory() as s:
        ont = Ontology(project_id=project.id, name=f"ont-{uuid.uuid4().hex[:6]}")
        s.add(ont)
        await s.commit()
        return ont.id


async def test_create_label_class(factory) -> None:
    user, project = await _seed(factory)
    ont_id = await _make_ontology(factory, project)
    async with _client(factory, user) as c:
        res = await c.post(
            f"/ontologies/{ont_id}/classes",
            json={
                "class_key": "person",
                "display_name": "Person",
                "color": "#00FF00",
                "sort_order": 0,
            },
        )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["class_key"] == "person"
    assert body["display_name"] == "Person"
    assert body["color"] == "#00FF00"
    assert body["ontology_id"] == str(ont_id)


async def test_create_label_class_ontology_404(factory) -> None:
    user, _project = await _seed(factory)
    async with _client(factory, user) as c:
        res = await c.post(
            f"/ontologies/{uuid.uuid4()}/classes",
            json={"class_key": "person", "display_name": "Person", "sort_order": 0},
        )
    assert res.status_code == 404, res.text


async def test_create_label_class_duplicate_key_409(factory) -> None:
    user, project = await _seed(factory)
    ont_id = await _make_ontology(factory, project)
    async with _client(factory, user) as c:
        first = await c.post(
            f"/ontologies/{ont_id}/classes",
            json={"class_key": "dog", "display_name": "Dog", "sort_order": 0},
        )
        assert first.status_code == 201, first.text
        dup = await c.post(
            f"/ontologies/{ont_id}/classes",
            json={"class_key": "dog", "display_name": "Dog 2", "sort_order": 1},
        )
    assert dup.status_code == 409, dup.text


async def test_create_label_class_duplicate_sort_order_409(factory) -> None:
    user, project = await _seed(factory)
    ont_id = await _make_ontology(factory, project)
    async with _client(factory, user) as c:
        first = await c.post(
            f"/ontologies/{ont_id}/classes",
            json={"class_key": "cat", "display_name": "Cat", "sort_order": 5},
        )
        assert first.status_code == 201, first.text
        dup = await c.post(
            f"/ontologies/{ont_id}/classes",
            json={"class_key": "bird", "display_name": "Bird", "sort_order": 5},
        )
    assert dup.status_code == 409, dup.text


async def test_update_label_class(factory) -> None:
    user, project = await _seed(factory)
    ont_id = await _make_ontology(factory, project)
    async with factory() as s:
        lc = LabelClass(
            ontology_id=ont_id,
            class_key="person",
            display_name="Person",
            color="#FF0000",
            sort_order=0,
        )
        s.add(lc)
        await s.commit()
        lc_id = lc.id

    async with _client(factory, user) as c:
        res = await c.patch(
            f"/ontologies/{ont_id}/classes/{lc_id}",
            json={"display_name": "Human", "color": "#0000FF"},
        )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["display_name"] == "Human"
    assert body["color"] == "#0000FF"
    assert body["sort_order"] == 0  # untouched


async def test_update_label_class_404_wrong_ontology(factory) -> None:
    user, project = await _seed(factory)
    ont_id = await _make_ontology(factory, project)
    other_ont_id = await _make_ontology(factory, project)
    async with factory() as s:
        lc = LabelClass(
            ontology_id=other_ont_id,
            class_key="person",
            display_name="Person",
            color="#FF0000",
            sort_order=0,
        )
        s.add(lc)
        await s.commit()
        lc_id = lc.id

    # Class exists but belongs to a different ontology → 404.
    async with _client(factory, user) as c:
        res = await c.patch(
            f"/ontologies/{ont_id}/classes/{lc_id}",
            json={"display_name": "Human"},
        )
    assert res.status_code == 404, res.text


async def test_delete_label_class(factory) -> None:
    user, project = await _seed(factory)
    ont_id = await _make_ontology(factory, project)
    async with factory() as s:
        lc = LabelClass(
            ontology_id=ont_id,
            class_key="person",
            display_name="Person",
            color="#FF0000",
            sort_order=0,
        )
        s.add(lc)
        await s.commit()
        lc_id = lc.id

    async with _client(factory, user) as c:
        res = await c.delete(f"/ontologies/{ont_id}/classes/{lc_id}")
    assert res.status_code == 204, res.text

    # Gone from the DB (this handler hard-deletes the row).
    async with factory() as s:
        assert await s.get(LabelClass, lc_id) is None


async def test_delete_label_class_404(factory) -> None:
    user, project = await _seed(factory)
    ont_id = await _make_ontology(factory, project)
    async with _client(factory, user) as c:
        res = await c.delete(f"/ontologies/{ont_id}/classes/{uuid.uuid4()}")
    assert res.status_code == 404, res.text


async def test_create_label_class_cross_org_404(factory) -> None:
    _owner, project = await _seed(factory)
    other, _p2 = await _seed(factory)
    ont_id = await _make_ontology(factory, project)
    async with _client(factory, other) as c:
        res = await c.post(
            f"/ontologies/{ont_id}/classes",
            json={"class_key": "person", "display_name": "Person", "sort_order": 0},
        )
    assert res.status_code == 404, res.text
