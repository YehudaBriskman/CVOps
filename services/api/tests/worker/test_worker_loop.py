"""Redis-Streams consumer tests for ``cvops_worker.worker``.

The worker has no test infra of its own, but ``cvops_worker`` is importable in
the API venv (it depends on ``cvops-api``), so these tests live under the API
suite and reuse its ``session`` (testcontainers Postgres) and ``fake_redis``
(fakeredis.aioredis) fixtures.

We never run the infinite ``_consume_loop`` here. Instead we exercise the small
internal pieces for a single message/iteration:

  * ``_ensure_group``            — group-create idempotency (BUSYGROUP).
  * ``_claim_and_run``           — the FOR UPDATE SKIP LOCKED + status='pending'
                                   claim guard that calls ``process_step``.
  * the ack-always contract      — re-implemented inline the way ``_handle``
                                   does it (the real ``_handle`` is a closure
                                   inside the loop and cannot be imported).
  * ``_orphan_recovery_loop``    — one recovery pass, driven via the coordinator
                                   helpers the loop body calls.

``_claim_and_run`` opens its own session via ``async_session_factory`` rather
than reusing the test ``session`` fixture, so the seeded rows must be committed
before it runs (it cannot see uncommitted state from another session).
"""

from __future__ import annotations

import uuid
from typing import Any
from datetime import datetime, timedelta, UTC
from unittest.mock import patch

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from cvops_api.db.models.auth import Org
from cvops_api.db.models.projects import Project
from cvops_api.db.models.runs import Run
from cvops_api.db.models.workflows import Workflow
from cvops_api.engine import coordinator

from cvops_worker import worker


# ── fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
async def worker_db(postgres_url: str):  # type: ignore[no-untyped-def]
    """Point ``_claim_and_run``'s ``async_session_factory`` at the test DB.

    The worker opens its own session via the module-level ``async_session_factory``
    (imported by name into ``worker``), which is bound to the *default* settings
    engine — not the testcontainers Postgres. Patch it to a maker on the test URL
    so ``_claim_and_run`` and the orphan-recovery sessions read committed rows
    seeded by the ``session`` fixture. Yields the maker for tests that want a
    fresh session of their own.
    """
    engine = create_async_engine(postgres_url, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    with patch.object(worker, "async_session_factory", factory):
        yield factory
    await engine.dispose()


# ── helpers ──────────────────────────────────────────────────────────────────


async def _seed_parent_and_child(
    session, step_type: str, *, child_status: str = "pending"
) -> tuple[Run, Run]:
    """Seed an org/project/workflow + a pending parent and one step child.

    Committed (not just flushed) so ``_claim_and_run``'s separate session can
    see the rows. Mirrors the seed helper in ``test_process_step.py``.
    """
    suffix = uuid.uuid4().hex[:8]
    org = Org(name=f"org-{suffix}")
    session.add(org)
    await session.flush()
    project = Project(org_id=org.id, name=f"proj-{suffix}")
    session.add(project)
    await session.flush()
    definition = {
        "steps": [{"id": "s1", "type": step_type, "config": {}, "inputs": {}}],
        "edges": [],
    }
    wf = Workflow(project_id=project.id, name=f"wf-{suffix}", definition=definition)
    session.add(wf)
    await session.flush()
    parent = Run(
        project_id=project.id,
        workflow_id=wf.id,
        kind="workflow",
        status="pending",
        input_refs={"params": {}},
        output_refs={},
        config={},
    )
    session.add(parent)
    await session.flush()
    child = Run(
        project_id=project.id,
        kind="step",
        parent_run_id=parent.id,
        workflow_id=wf.id,
        step_id="s1",
        step_type=step_type,
        status=child_status,
        input_refs={},
        output_refs={},
        config={"_idem_key": "k-" + suffix},
    )
    session.add(child)
    await session.commit()
    return parent, child


async def _handle_once(fake_redis, msg_id: str, fields: dict[str, str]) -> None:
    """Re-implementation of the loop's ``_handle`` closure for one message.

    Identical contract: run the job, then ALWAYS ack — even if the run raises,
    the message is acked (no automatic requeue; failures live in PG).
    """
    try:
        await worker._claim_and_run(fields["job_id"])
    finally:
        await fake_redis.xack(worker.STREAM, worker.GROUP, msg_id)


async def _pending_entries(fake_redis) -> int:
    """Count not-yet-acked entries in the group's pending-entries list (PEL)."""
    info = await fake_redis.xpending(worker.STREAM, worker.GROUP)
    # redis-py returns a dict like {"pending": N, ...} for the summary form.
    return int(info["pending"]) if isinstance(info, dict) else int(info[0])


# ── _ensure_group idempotency ────────────────────────────────────────────────


async def test_ensure_group_creates_then_is_idempotent(fake_redis) -> None:
    # First call creates the group + stream (mkstream=True).
    await worker._ensure_group()
    groups = await fake_redis.xinfo_groups(worker.STREAM)
    assert any(g["name"] == worker.GROUP for g in groups)

    # Second call hits BUSYGROUP and must be swallowed (no raise).
    await worker._ensure_group()
    groups = await fake_redis.xinfo_groups(worker.STREAM)
    assert sum(1 for g in groups if g["name"] == worker.GROUP) == 1


async def test_ensure_group_reraises_non_busygroup(fake_redis) -> None:
    async def _boom(*_a: Any, **_k: Any) -> None:
        raise RuntimeError("ECONNREFUSED")

    with patch.object(fake_redis, "xgroup_create", _boom):
        with pytest.raises(RuntimeError, match="ECONNREFUSED"):
            await worker._ensure_group()


# ── end-to-end claim + ack ───────────────────────────────────────────────────


async def test_claim_runs_step_and_acks(session, fake_redis, echo_step, worker_db) -> None:
    """Seed a pending run, XADD a doorbell, drive one handle iteration:
    the run advances to succeeded and the message is XACK'd."""
    parent, child = await _seed_parent_and_child(session, "test.echo")

    await worker._ensure_group()
    await coordinator.enqueue_step(child.id, "test.echo", worker.STREAM)

    # Read the one message back out of the group, as the loop's XREADGROUP would.
    resp = await fake_redis.xreadgroup(
        worker.GROUP, worker.CONSUMER, streams={worker.STREAM: ">"}, count=10
    )
    (_stream, messages) = resp[0]
    assert len(messages) == 1
    msg_id, fields = messages[0]
    assert fields["job_id"] == str(child.id)

    with patch.object(coordinator, "get_storage", lambda: None):
        await _handle_once(fake_redis, msg_id, fields)

    # Run advanced through the coordinator.
    await session.refresh(child)
    assert child.status == "succeeded"
    await session.refresh(parent)
    assert parent.status == "succeeded"

    # Message acked → empty pending-entries list.
    assert await _pending_entries(fake_redis) == 0


async def test_handle_acks_even_when_claim_raises(
    session, fake_redis, echo_step, worker_db
) -> None:
    """If ``_claim_and_run`` raises, the message is STILL acked — the worker
    never auto-requeues; failures are recorded in PG, not Redis."""
    _parent, child = await _seed_parent_and_child(session, "test.echo")

    await worker._ensure_group()
    await coordinator.enqueue_step(child.id, "test.echo", worker.STREAM)
    resp = await fake_redis.xreadgroup(
        worker.GROUP, worker.CONSUMER, streams={worker.STREAM: ">"}, count=10
    )
    msg_id, fields = resp[0][1][0]

    async def _explode(_job_id: str) -> None:
        raise RuntimeError("claim blew up")

    with patch.object(worker, "_claim_and_run", _explode):
        with pytest.raises(RuntimeError, match="claim blew up"):
            await _handle_once(fake_redis, msg_id, fields)

    # Despite the exception, the message was acked in the finally block.
    assert await _pending_entries(fake_redis) == 0


# ── claim guard (idempotent against re-enqueues) ─────────────────────────────


async def test_claim_skips_non_pending_run(session, fake_redis, echo_step, worker_db) -> None:
    """A run already in a non-pending state is NOT re-processed — the
    status='pending' guard makes re-delivery/re-enqueue a no-op."""
    _parent, child = await _seed_parent_and_child(session, "test.echo", child_status="succeeded")
    # Give it an output to prove _claim_and_run leaves it untouched.
    await session.execute(
        update(Run).where(Run.id == child.id).values(output_refs={"sentinel": True})
    )
    await session.commit()

    with patch.object(coordinator, "get_storage", lambda: None):
        await worker._claim_and_run(str(child.id))

    await session.refresh(child)
    assert child.status == "succeeded"
    assert child.output_refs == {"sentinel": True}  # process_step never ran


async def test_claim_unknown_run_is_noop(session, fake_redis, worker_db) -> None:
    """A job_id with no matching row claims nothing and does not raise."""
    with patch.object(coordinator, "get_storage", lambda: None):
        await worker._claim_and_run(str(uuid.uuid4()))  # should simply return


# ── orphan recovery (one pass) ───────────────────────────────────────────────


async def test_orphan_recovery_reenqueues_stale_pending(
    session, fake_redis, echo_step, worker_db
) -> None:
    """A stale pending run for one of this worker's step types gets re-enqueued
    onto the stream by a single recovery pass."""
    _parent, child = await _seed_parent_and_child(session, "test.echo")
    # Backdate past ORPHAN_MIN_AGE_SECONDS so it is considered orphaned.
    await session.execute(
        update(Run)
        .where(Run.id == child.id)
        .values(created_at=datetime.now(UTC) - timedelta(seconds=120))
    )
    await session.commit()

    # Drive one recovery pass directly (not the timed loop). EchoStep has no
    # explicit queue, so queue_for(...) == DEFAULT_QUEUE == worker.STREAM, which
    # puts "test.echo" in this worker's _my_step_types().
    my_types = worker._my_step_types()
    assert "test.echo" in my_types

    async with worker_db() as recovery_session:
        orphans = await coordinator.find_orphan_step_runs(
            recovery_session, my_types, worker.ORPHAN_MIN_AGE_SECONDS
        )
    ids = {rid for rid, _ in orphans}
    assert child.id in ids

    for run_id, step_type in orphans:
        await coordinator.enqueue_step(run_id, step_type, worker.STREAM)

    # The doorbell for our run now sits on the stream.
    entries = await fake_redis.xrange(worker.STREAM)
    job_ids = {fields["job_id"] for _id, fields in entries}
    assert str(child.id) in job_ids


async def test_orphan_recovery_ignores_recent_and_running(
    session, fake_redis, echo_step, worker_db
) -> None:
    """Recent pending and already-running rows are not re-enqueued."""
    _p1, recent = await _seed_parent_and_child(session, "test.echo")
    _p2, running = await _seed_parent_and_child(session, "test.echo", child_status="running")

    my_types = worker._my_step_types()
    async with worker_db() as recovery_session:
        orphans = await coordinator.find_orphan_step_runs(
            recovery_session, my_types, worker.ORPHAN_MIN_AGE_SECONDS
        )
    ids = {rid for rid, _ in orphans}
    assert recent.id not in ids  # too young
    assert running.id not in ids  # not pending
