"""Fixtures for worker-preprocessing.

These tests deliberately avoid a real Postgres: the worker module's
DB-touching helpers (``_claim_and_run`` via ``process_step``) are exercised by
the API integration suite. Here we cover the parts that are pure logic or only
need the Redis doorbell — step-type filtering, consumer-group setup, message
dispatch, and ack semantics — using ``fakeredis`` as a real in-memory Streams
backend and a stub registry/coordinator where a DB would otherwise be required.
"""

from __future__ import annotations

import asyncio

import fakeredis.aioredis
import pytest

import cvops_api.core.redis_client as redis_client


@pytest.fixture
async def fake_redis(monkeypatch):
    """A real-ish Redis (fakeredis) wired into cvops_api's get_redis singleton.

    ``decode_responses=True`` mirrors the production client so xreadgroup yields
    str field dicts exactly as the worker expects.

    fakeredis returns instantly from a *blocking* xreadgroup on an empty stream
    (its ``block`` is a no-op), so the worker's ``while`` loop would busy-spin and
    starve the event loop — handler tasks and the test driver never get scheduled.
    Real Redis actually parks for ``block`` ms. We restore cooperative scheduling
    by yielding (and briefly sleeping) whenever a blocking read comes back empty,
    which models real behaviour without touching worker code.
    """
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    _real_xreadgroup = r.xreadgroup

    async def _yielding_xreadgroup(*args, **kwargs):
        resp = await _real_xreadgroup(*args, **kwargs)
        if not resp and kwargs.get("block"):
            # Park like real Redis would, letting other tasks run.
            await asyncio.sleep(0.01)
        return resp

    monkeypatch.setattr(r, "xreadgroup", _yielding_xreadgroup)
    monkeypatch.setattr(redis_client, "_redis", r)
    yield r
    await r.aclose()


class FakeStep:
    """Minimal stand-in for a registered Step impl — only ``queue`` matters
    for ``queue_for`` / ``_my_step_types`` routing."""

    def __init__(self, type_key: str, queue: str = "") -> None:
        self.type_key = type_key
        self.queue = queue


class FakeReg:
    def __init__(self, type_key: str, queue: str = "") -> None:
        self.type_key = type_key
        self.impl = FakeStep(type_key, queue)


@pytest.fixture
def stub_registry(monkeypatch):
    """Replace registry.all() with a controllable set of registrations."""
    import cvops_worker.worker as worker

    regs: list[FakeReg] = []

    def _set(*registrations: FakeReg) -> None:
        regs.clear()
        regs.extend(registrations)

    fake = type("R", (), {"all": staticmethod(lambda: list(regs))})()
    monkeypatch.setattr(worker, "registry", fake)
    return _set
