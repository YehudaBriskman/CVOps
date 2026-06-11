import asyncio

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

import cvops_api.db.models  # noqa: F401 — registers all 21 models with Base.metadata
from cvops_api.db.base import Base


@pytest.fixture(scope="session")
def postgres_url() -> str:  # type: ignore[return]
    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url()
        # testcontainers returns a psycopg2 URL; swap driver for asyncpg
        url = url.replace("+psycopg2", "+asyncpg").replace(
            "postgresql://", "postgresql+asyncpg://", 1
        )
        # strip any remaining psycopg2 fragment
        if "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        yield url


@pytest.fixture(scope="session", autouse=True)
def create_test_schema(postgres_url: str) -> None:
    """Create all tables once for the entire test session."""

    async def _setup() -> None:
        engine = create_async_engine(postgres_url, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(_setup())


@pytest.fixture
async def session(postgres_url: str) -> AsyncSession:  # type: ignore[return]
    """
    Per-test async DB session.
    Tests use unique UUID-based values so rows from different tests never collide.
    Call await session.flush() to make inserts visible within the test.
    Call await session.commit() when the test needs to verify post-commit state.
    """
    engine = create_async_engine(postgres_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as sess:
        yield sess
    await engine.dispose()
