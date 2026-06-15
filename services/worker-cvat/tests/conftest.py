"""Test fixtures for worker-cvat — testcontainers Postgres, mirroring the API
suite's conftest. Schema is created with Base.metadata.create_all (no Alembic),
so worker-cvat must be installed alongside cvops-api (its dependency).

Requires Docker.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from cvops_api.db.base import Base
import cvops_api.db.models  # noqa: F401 — populate Base.metadata with all tables


@pytest.fixture(scope="session")
def postgres_url() -> str:
    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url()
        url = url.replace("+psycopg2", "+asyncpg").replace(
            "postgresql://", "postgresql+asyncpg://", 1
        )
        yield url


@pytest.fixture(scope="session", autouse=True)
def create_test_schema(postgres_url: str) -> None:
    async def _setup() -> None:
        engine = create_async_engine(postgres_url, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(_setup())


@pytest.fixture
async def session_factory(postgres_url: str):
    engine = create_async_engine(postgres_url, echo=False)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()
