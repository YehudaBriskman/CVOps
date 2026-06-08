"""
Tests for the /internal/health endpoint.

The health endpoint executes SELECT 1 against the database. To avoid
importing cvops_steps (which is not installed in the test environment)
the lifespan context is bypassed by building a lightweight test app that
mounts only the internal router against the test database.

asyncio_mode = "auto" in pyproject.toml means async test functions and
async fixtures are collected and driven by pytest-asyncio automatically.
"""

from __future__ import annotations

import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch

from cvops_api.routers import internal


# ---------------------------------------------------------------------------
# Minimal test app — avoids cvops_steps import in main.py lifespan
# ---------------------------------------------------------------------------


def _build_test_app() -> FastAPI:
    """
    Create a minimal FastAPI instance that registers only the internal router.
    This bypasses the lifespan in cvops_api.main which tries to import cvops_steps.
    """
    test_app = FastAPI()
    test_app.include_router(internal.router, prefix="/internal")
    return test_app


_test_app = _build_test_app()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client(postgres_url: str) -> AsyncClient:
    """
    AsyncClient pointed at the lightweight test app.

    The internal router's health endpoint calls async_session_factory from
    cvops_api.db.session. We patch that factory to use a session bound to
    the test database so the SELECT 1 hits a real but ephemeral Postgres
    instance rather than the default settings URL.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from contextlib import asynccontextmanager

    test_engine = create_async_engine(postgres_url, echo=False)
    test_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

    @asynccontextmanager
    async def _override_session_factory():  # type: ignore[return]
        async with test_factory() as sess:
            yield sess

    with patch("cvops_api.routers.internal.async_session_factory", test_factory):
        async with AsyncClient(
            transport=ASGITransport(app=_test_app),
            base_url="http://test",
        ) as c:
            yield c

    await test_engine.dispose()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_health_returns_200(client: AsyncClient) -> None:
    """GET /internal/health must respond with HTTP 200."""
    response = await client.get("/internal/health")

    assert response.status_code == 200


async def test_health_response_has_status_ok(client: AsyncClient) -> None:
    """GET /internal/health must return the JSON body {"status": "ok"}."""
    response = await client.get("/internal/health")

    assert response.json() == {"status": "ok"}
