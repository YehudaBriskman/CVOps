"""Router tests for direct image upload → samples (no workflow).

Covers the presign + confirm endpoints: presign returns a per-file URL;
confirm creates one sample per image under a single shared 'Uploads'
(image_folder) source with group metadata; re-confirming the same hashes is
idempotent; and the data-sources list hides legacy per-image sources.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from cvops_api.core.auth import get_current_user
from cvops_api.db.session import get_session
from cvops_api.db.models.auth import Org, User
from cvops_api.db.models.projects import Project
from cvops_api.db.models.samples import DataSource
from cvops_api.routers import data_sources, samples


class _FakeStorage:
    async def get_presigned_put(
        self, blob_hash: str, ttl_seconds: int = 3600, endpoint: str | None = None
    ) -> str:
        return f"https://signed.example/put/{blob_hash}"


@pytest_asyncio.fixture
async def factory(postgres_url: str):
    engine = create_async_engine(postgres_url, echo=False)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
def patched_storage():
    with patch.object(data_sources, "get_storage", lambda: _FakeStorage()):
        yield


def _client(factory, current_user: User) -> AsyncClient:
    app = FastAPI()
    app.include_router(data_sources.router)
    app.include_router(samples.router)

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


def _hash() -> str:
    return "sha256:" + uuid.uuid4().hex.ljust(64, "0")


async def test_presign_returns_per_file_urls(factory) -> None:
    user, project = await _seed(factory)
    async with _client(factory, user) as c:
        res = await c.post(
            f"/projects/{project.id}/image-uploads/presign",
            json={
                "items": [{"filename": "a.jpg", "content_type": "image/jpeg", "sha256": _hash()}]
            },
        )
        assert res.status_code == 200
        items = res.json()["items"]
        assert len(items) == 1
        assert items[0]["put_url"].startswith("https://signed.example/put/")


async def test_confirm_creates_samples_under_one_uploads_source(factory) -> None:
    user, project = await _seed(factory)
    h1, h2 = _hash(), _hash()
    async with _client(factory, user) as c:
        res = await c.post(
            f"/projects/{project.id}/image-uploads/confirm",
            json={
                "group": "my-folder",
                "items": [
                    {"blob_hash": h1, "width": 640, "height": 480},
                    {"blob_hash": h2, "width": 800, "height": 600},
                ],
            },
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["created"] == 2
        source_id = body["source_id"]

        # Both samples exist under the one Uploads source, with group metadata.
        listing = await c.get(f"/projects/{project.id}/samples?source_id={source_id}")
        items = listing.json()["items"]
        assert len(items) == 2
        assert all(it["metadata"]["group"] == "my-folder" for it in items)
        assert all(it["review_status"] == "unreviewed" for it in items)

        # Re-confirm same hashes → idempotent (still 2 samples, same source).
        res2 = await c.post(
            f"/projects/{project.id}/image-uploads/confirm",
            json={"items": [{"blob_hash": h1, "width": 640, "height": 480}]},
        )
        assert res2.status_code == 201
        assert res2.json()["source_id"] == source_id
        again = await c.get(f"/projects/{project.id}/samples?source_id={source_id}")
        assert len(again.json()["items"]) == 2


async def test_list_excludes_legacy_image_sources(factory) -> None:
    user, project = await _seed(factory)
    async with factory() as s:
        s.add(DataSource(project_id=project.id, type="video", status="ingested"))
        s.add(DataSource(project_id=project.id, type="image", status="uploaded"))
        await s.commit()

    async with _client(factory, user) as c:
        # Create the Uploads folder via a confirm.
        await c.post(
            f"/projects/{project.id}/image-uploads/confirm",
            json={"items": [{"blob_hash": _hash(), "width": 100, "height": 100}]},
        )
        res = await c.get(f"/projects/{project.id}/data-sources")
        types = sorted(ds["type"] for ds in res.json())
        assert "image" not in types
        assert "video" in types
        assert "image_folder" in types
