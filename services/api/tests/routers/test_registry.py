"""Router tests for the step-type registry router.

The registry is the in-memory `cvops_api.core.registry.registry` singleton; the
`echo_step` fixture registers a `test.echo` step into it for the test's
lifetime, which is what these endpoints surface.

main.py mounts this router with prefix="/registry" and the router declares
/types, so mount it the same way here.
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
from cvops_api.routers import registry as registry_router


@pytest_asyncio.fixture
async def factory(postgres_url: str):
    engine = create_async_engine(postgres_url, echo=False)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


def _client(factory, current_user: User) -> AsyncClient:
    app = FastAPI()
    app.include_router(registry_router.router, prefix="/registry")

    async def _get_session_dep():
        async with factory() as sess:
            yield sess

    app.dependency_overrides[get_session] = _get_session_dep
    app.dependency_overrides[get_current_user] = lambda: current_user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed_user(factory) -> User:
    suffix = uuid.uuid4().hex[:8]
    async with factory() as s:
        org = Org(name=f"org-{suffix}")
        s.add(org)
        await s.flush()
        user = User(org_id=org.id, email=f"u-{suffix}@test.com")
        s.add(user)
        await s.commit()
        await s.refresh(user)
        return user


# ---------------------------------------------------------------------------
# list types
# ---------------------------------------------------------------------------


async def test_list_types_includes_registered_step(factory, echo_step) -> None:
    user = await _seed_user(factory)
    async with _client(factory, user) as c:
        res = await c.get("/registry/types")

    assert res.status_code == 200, res.text
    entry = next((t for t in res.json() if t["type_key"] == "test.echo"), None)
    assert entry is not None
    assert entry["category"] == "step"  # getattr default in registry.register
    assert entry["json_schema"] == {"type": "object"}
    assert entry["ui_hints"] == {}


async def test_list_types_category_filter(factory, echo_step) -> None:
    user = await _seed_user(factory)
    async with _client(factory, user) as c:
        match = await c.get("/registry/types", params={"category": "step"})
        miss = await c.get("/registry/types", params={"category": "no-such-cat"})

    assert match.status_code == 200, match.text
    assert any(t["type_key"] == "test.echo" for t in match.json())

    assert miss.status_code == 200, miss.text
    assert all(t["type_key"] != "test.echo" for t in miss.json())


# ---------------------------------------------------------------------------
# get single type
# ---------------------------------------------------------------------------


async def test_get_type(factory, echo_step) -> None:
    user = await _seed_user(factory)
    async with _client(factory, user) as c:
        res = await c.get("/registry/types/test.echo")

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["type_key"] == "test.echo"
    assert body["category"] == "step"
    assert body["json_schema"] == {"type": "object"}


async def test_get_unknown_type_404(factory) -> None:
    user = await _seed_user(factory)
    async with _client(factory, user) as c:
        res = await c.get("/registry/types/does.not.exist")
    assert res.status_code == 404, res.text
