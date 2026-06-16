"""Tests for ``cvops_worker_common.runner.run_job`` — the per-job lifecycle.

``run_job`` opens its own session via the module-level ``async_session_factory``
(patched to the test DB by ``worker_db``), claims the run with the
status='pending' + FOR UPDATE SKIP LOCKED guard, executes the step out of the
registry, and finalizes the run:

  pending → running → succeeded | failed | waiting (gate)

On success with a parent it POSTs ``/internal/runs/{parent}/advance`` over HTTP;
we either give the child no parent (skips the call) or patch ``_advance`` so no
network is touched. ``get_storage`` is patched out because EchoStep never uses
storage and the real backend reaches for Garage at construction time.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import patch

from sqlalchemy import select

from cvops_api.core.registry import registry
from cvops_api.db.models.runs import Event, Run
from cvops_api.engine.step import GateException, Step

from cvops_worker_common import runner

from .conftest import seed_parent_and_child


class _GateStep(Step):
    type_key = "test.gate"
    config_schema: dict[str, Any] = {"type": "object"}

    async def run(self, ctx, config, inputs):  # type: ignore[no-untyped-def]
        raise GateException({"reason": "needs review"})


class _FailStep(Step):
    type_key = "test.fail"
    config_schema: dict[str, Any] = {"type": "object"}

    async def run(self, ctx, config, inputs):  # type: ignore[no-untyped-def]
        raise RuntimeError("boom")


# ── success → advance ─────────────────────────────────────────────────────────


async def test_run_job_success_marks_succeeded(session, fake_redis, echo_step, worker_db) -> None:
    _parent, child = await seed_parent_and_child(session, "test.echo", with_parent=False)

    with patch.object(runner, "get_storage", lambda: None):
        await runner.run_job(str(child.id), "test.echo")

    await session.refresh(child)
    assert child.status == "succeeded"
    assert child.output_refs == {"echoed": {}}
    assert child.started_at is not None and child.finished_at is not None

    # started + succeeded events recorded for the child.
    actions = (
        (await session.execute(select(Event.action).where(Event.entity_id == child.id)))
        .scalars()
        .all()
    )
    assert "run.started" in actions
    assert "run.succeeded" in actions


async def test_run_job_success_with_parent_calls_advance(
    session, fake_redis, echo_step, worker_db
) -> None:
    """When the child has a parent, the success path fires ``_advance`` (the
    HTTP chain trigger). We patch ``_advance`` to assert it is invoked with the
    finalized run rather than touching the network."""
    _parent, child = await seed_parent_and_child(session, "test.echo", with_parent=True)

    calls: list[uuid.UUID] = []

    async def _spy_advance(run: Run) -> None:
        calls.append(run.id)

    with (
        patch.object(runner, "get_storage", lambda: None),
        patch.object(runner, "_advance", _spy_advance),
    ):
        await runner.run_job(str(child.id), "test.echo")

    await session.refresh(child)
    assert child.status == "succeeded"
    assert calls == [child.id]


# ── gate → waiting ────────────────────────────────────────────────────────────


async def test_run_job_gate_parks_waiting(session, fake_redis, worker_db) -> None:
    registry.register(_GateStep())
    try:
        _parent, child = await seed_parent_and_child(session, "test.gate", with_parent=False)
        with patch.object(runner, "get_storage", lambda: None):
            await runner.run_job(str(child.id), "test.gate")

        await session.refresh(child)
        assert child.status == "waiting"
        assert child.output_refs == {"gate_data": {"reason": "needs review"}}
    finally:
        registry._store.pop("test.gate", None)


# ── exception → failed ────────────────────────────────────────────────────────


async def test_run_job_failure_marks_failed(session, fake_redis, worker_db) -> None:
    registry.register(_FailStep())
    try:
        _parent, child = await seed_parent_and_child(session, "test.fail", with_parent=False)
        with patch.object(runner, "get_storage", lambda: None):
            await runner.run_job(str(child.id), "test.fail")

        await session.refresh(child)
        assert child.status == "failed"
        assert "boom" in (child.error or "")
        assert child.finished_at is not None
    finally:
        registry._store.pop("test.fail", None)


async def test_run_job_unknown_step_type_fails(session, fake_redis, echo_step, worker_db) -> None:
    """An unregistered step type fails the run (RuntimeError in ``_execute``)
    rather than escaping — failures are recorded in PG, never re-raised."""
    _parent, child = await seed_parent_and_child(session, "test.echo", with_parent=False)

    with patch.object(runner, "get_storage", lambda: None):
        await runner.run_job(str(child.id), "test.no_such_step")

    await session.refresh(child)
    assert child.status == "failed"
    assert "test.no_such_step" in (child.error or "")


# ── claim guard ───────────────────────────────────────────────────────────────


async def test_run_job_skips_non_pending(session, fake_redis, echo_step, worker_db) -> None:
    """``_acquire`` only claims a pending row; a running/terminal run is left
    untouched, so redelivery of an in-flight job is a no-op."""
    _parent, child = await seed_parent_and_child(
        session, "test.echo", child_status="running", with_parent=False
    )

    with patch.object(runner, "get_storage", lambda: None):
        await runner.run_job(str(child.id), "test.echo")

    await session.refresh(child)
    assert child.status == "running"  # untouched
