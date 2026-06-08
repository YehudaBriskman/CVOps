"""Async Redis client — initialized at startup, used for token blacklist."""

from __future__ import annotations

from redis.asyncio import Redis
from redis.asyncio import from_url

from cvops_api.config import settings

_redis: Redis | None = None  # type: ignore[type-arg]


async def init_redis() -> None:
    global _redis
    _redis = from_url(settings.REDIS_URL, decode_responses=True)


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


def get_redis() -> Redis:  # type: ignore[type-arg]
    if _redis is None:
        raise RuntimeError("Redis client not initialized — call init_redis() at startup")
    return _redis
