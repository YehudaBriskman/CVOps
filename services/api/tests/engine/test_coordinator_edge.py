"""Coordinator edge cases — cycle rejection, failure cascade, gate parking,
and idempotency reuse — that the happy-path suite in test_coordinator.py
doesn't cover.

Uses the same testcontainers Postgres (`session`) + fakeredis (`fake_redis`)
fixtures. Local trivial steps (FailingStep, GateStep) are registered/popped
the same way conftest's `echo_step` fixture handles EchoStep.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy import select

from cvops_api.core.registry import registry
from cvops_api.db.models.auth import Org
from cvops_api.db.models.projects import Project
from cvops_api.db.models.runs import Run
from cvops_api.db.models.workflows import Workflow
from cvops_api.engine import coordinator
from cvops_api.engine.coordinator import advance_workflow, process_step
from cvops_api.engine.step import GateException, Step, StepContext

STREAM = "preprocessing"


@pytest.fixture(autouse=True)
def _no_storage():
    """process_step builds a StepContext via get_storage(); the real S3Backend
    reaches out to Garage at construction. Our trivial steps never touch
    storage, so stub it out (mirrors tests/worker/test_process_step.py)."""
    with patch.object(coordinator, "get_storage", lambda: None):
        yield


# ── Local trivial steps ─────────────────────────────────────────────────────


class FailingStep(Step):
    """Always raises a plain (non-gate) exception."""

    type_key = "test.fail"
    config_schema: dict[str, Any] = {"type": "object"}

    async def run(
        self, ctx: StepContext, config: dict[str, Any], inputs: dict[str, Any]
    ) -> dict[str, Any]:
        raise RuntimeError("boom")


class GateStep(Step):
    """Always parks the run by raising GateException with some gate_data."""

    type_key = "test.gate"
    config_schema: dict[str, Any] = {"type": "object"}
    is_gate = True

    async def run(
        self, ctx: StepContext, config: dict[str, Any], inputs: dict[str, Any]
    ) -> dict[str, Any]:
        raise GateException({"reason": "needs human", "inputs": inputs})


@pytest.fixture
def failing_step():  # type: ignore[no-untyped-def]
    step = FailingStep()
    registry.register(step)
    yield step
    registry._store.pop(step.type_key, None)


@pytest.fixture
def gate_step():  # type: ignore[no-untyped-def]
    step = GateStep()
    registry.register(step)
    yield step
    registry._store.pop(step.type_key, None)


# ── Seed helper ─────────────────────────────────────────────────────────────


async def _seed_parent(session, definition: dict) -> tuple[Run, str]:
    suffix = uuid.uuid4().hex[:8]
    org = Org(name=f"org-{suffix}")
    session.add(org)
    await session.flush()
    project = Project(org_id=org.id, name=f"proj-{suffix}")
    session.add(project)
    await session.flush()
    wf = Workflow(project_id=project.id, name=f"wf-{suffix}", definition=definition)
    session.add(wf)
    await session.flush()
    source_id = str(uuid.uuid4())
    parent = Run(
        project_id=project.id,
        workflow_id=wf.id,
        kind="workflow",
        status="pending",
        input_refs={"params": {"source_id": source_id}},
        output_refs={},
        config={},
    )
    session.add(parent)
    await session.commit()
    return parent, source_id


# ── Cycle detection ─────────────────────────────────────────────────────────


async def test_cycle_in_dag_fails_parent_and_enqueues_nothing(
    session, fake_redis, echo_step
) -> None:
    """A 2-node cycle (a→b, b→a) is rejected by _topo_sort; advance fails the
    parent with 'Workflow has a cycle' and creates no child runs."""
    definition = {
        "steps": [
            {"id": "a", "type": "test.echo", "config": {}},
            {"id": "b", "type": "test.echo", "config": {}},
        ],
        "edges": [
            {"from": "a", "to": "b"},
            {"from": "b", "to": "a"},
        ],
    }
    parent, _ = await _seed_parent(session, definition)
    actor = uuid.uuid4()

    await advance_workflow(session, parent.id, actor)

    await session.refresh(parent)
    assert parent.status == "failed"
    assert parent.error == "Workflow has a cycle"

    children = (
        (await session.execute(select(Run).where(Run.parent_run_id == parent.id))).scalars().all()
    )
    assert children == []
    assert await fake_redis.xlen(STREAM) == 0


async def test_self_loop_is_a_cycle(session, fake_redis, echo_step) -> None:
    """A single node with a self-edge (a→a) is also a cycle."""
    definition = {
        "steps": [{"id": "a", "type": "test.echo", "config": {}}],
        "edges": [{"from": "a", "to": "a"}],
    }
    parent, _ = await _seed_parent(session, definition)

    await advance_workflow(session, parent.id, uuid.uuid4())

    await session.refresh(parent)
    assert parent.status == "failed"
    assert parent.error == "Workflow has a cycle"


# ── Failure cascade ─────────────────────────────────────────────────────────


async def test_failing_step_fails_child_and_parent(session, fake_redis, failing_step) -> None:
    """A step raising a non-gate exception in process_step marks the child
    'failed' and cascades to the parent run."""
    definition = {
        "steps": [{"id": "s1", "type": "test.fail", "config": {}, "inputs": {}}],
        "edges": [],
    }
    parent, _ = await _seed_parent(session, definition)
    actor = uuid.uuid4()

    await advance_workflow(session, parent.id, actor)
    child = (
        (await session.execute(select(Run).where(Run.parent_run_id == parent.id))).scalars().one()
    )
    assert child.status == "pending"

    await process_step(session, child.id, actor)

    await session.refresh(child)
    await session.refresh(parent)
    assert child.status == "failed"
    assert child.error == "boom"
    assert child.finished_at is not None
    assert parent.status == "failed"
    assert "Step 's1' failed: boom" == parent.error


async def test_failed_step_short_circuits_subsequent_advance(
    session, fake_redis, failing_step, echo_step
) -> None:
    """Once a child has failed, a fresh advance keeps the parent failed and
    does not create the downstream step (a→b, a fails)."""
    definition = {
        "steps": [
            {"id": "a", "type": "test.fail", "config": {}, "inputs": {}},
            {"id": "b", "type": "test.echo", "config": {}, "inputs": {}},
        ],
        "edges": [{"from": "a", "to": "b"}],
    }
    parent, _ = await _seed_parent(session, definition)
    actor = uuid.uuid4()

    await advance_workflow(session, parent.id, actor)
    child_a = (
        (await session.execute(select(Run).where(Run.parent_run_id == parent.id))).scalars().one()
    )
    await process_step(session, child_a.id, actor)

    # process_step calls advance again after failing; b must never be created.
    children = (
        (await session.execute(select(Run).where(Run.parent_run_id == parent.id))).scalars().all()
    )
    step_ids = {c.step_id for c in children}
    assert step_ids == {"a"}
    await session.refresh(parent)
    assert parent.status == "failed"


# ── Gate parking + resume ───────────────────────────────────────────────────


async def test_gate_step_parks_run_as_waiting(session, fake_redis, gate_step) -> None:
    """GateException parks the child as 'waiting' with gate_data stashed in
    output_refs; the parent stays pending and no advance happens."""
    definition = {
        "steps": [{"id": "g", "type": "test.gate", "config": {}, "inputs": {}}],
        "edges": [],
    }
    parent, source_id = await _seed_parent(session, definition)
    actor = uuid.uuid4()

    await advance_workflow(session, parent.id, actor)
    child = (
        (await session.execute(select(Run).where(Run.parent_run_id == parent.id))).scalars().one()
    )

    await process_step(session, child.id, actor)

    await session.refresh(child)
    await session.refresh(parent)
    assert child.status == "waiting"
    # The step has an empty `inputs` template, so the coordinator forwards the
    # run params as the frozen inputs (the "unwired step" path), which the gate
    # echoes back in its gate_data.
    assert child.output_refs == {
        "gate_data": {"reason": "needs human", "inputs": {"source_id": source_id}}
    }
    assert child.finished_at is not None
    # Parent not finalized; gate resume is external.
    assert parent.status == "pending"


async def test_advance_on_waiting_run_is_a_noop(session, fake_redis, gate_step, echo_step) -> None:
    """While a child is 'waiting', a fresh advance must not create downstream
    steps (the 'any waiting' short-circuit in advance_workflow)."""
    definition = {
        "steps": [
            {"id": "g", "type": "test.gate", "config": {}, "inputs": {}},
            {"id": "after", "type": "test.echo", "config": {}, "inputs": {}},
        ],
        "edges": [{"from": "g", "to": "after"}],
    }
    parent, _ = await _seed_parent(session, definition)
    actor = uuid.uuid4()

    await advance_workflow(session, parent.id, actor)
    gate_child = (
        (await session.execute(select(Run).where(Run.parent_run_id == parent.id))).scalars().one()
    )
    await process_step(session, gate_child.id, actor)

    # Simulate the gate-resolve endpoint advancing while still waiting:
    await advance_workflow(session, parent.id, actor)
    children = (
        (await session.execute(select(Run).where(Run.parent_run_id == parent.id))).scalars().all()
    )
    assert {c.step_id for c in children} == {"g"}


async def test_gate_resume_creates_downstream_step(
    session, fake_redis, gate_step, echo_step
) -> None:
    """After the gate child is moved to 'succeeded' (mimicking the gate-resolve
    endpoint), advance enqueues the downstream step."""
    definition = {
        "steps": [
            {"id": "g", "type": "test.gate", "config": {}, "inputs": {}},
            {"id": "after", "type": "test.echo", "config": {}, "inputs": {}},
        ],
        "edges": [{"from": "g", "to": "after"}],
    }
    parent, _ = await _seed_parent(session, definition)
    actor = uuid.uuid4()

    await advance_workflow(session, parent.id, actor)
    gate_child = (
        (await session.execute(select(Run).where(Run.parent_run_id == parent.id))).scalars().one()
    )
    await process_step(session, gate_child.id, actor)

    # Resolve the gate: the endpoint marks it succeeded then advances.
    await session.refresh(gate_child)
    gate_child.status = "succeeded"
    gate_child.output_refs = {"approved": True}
    await session.commit()

    await advance_workflow(session, parent.id, actor)

    children = (
        (await session.execute(select(Run).where(Run.parent_run_id == parent.id))).scalars().all()
    )
    by_step = {c.step_id: c for c in children}
    assert set(by_step) == {"g", "after"}
    assert by_step["after"].status == "pending"
    # Two doorbells total: g (first advance) then after (gate resume). The
    # most recent entry is the downstream step.
    assert await fake_redis.xlen(STREAM) == 2
    entries = await fake_redis.xrange(STREAM)
    assert entries[-1][1]["job_id"] == str(by_step["after"].id)


# ── Idempotency reuse across a two-step chain ───────────────────────────────


async def test_idempotency_reuse_skips_enqueue_in_chain(session, fake_redis, echo_step) -> None:
    """A two-step chain where the FIRST step has a matching prior succeeded run:
    s1 is born succeeded (no enqueue), then s2 becomes ready and IS enqueued.
    Asserts the reuse via the stream containing only s2's doorbell."""
    definition = {
        "steps": [
            {
                "id": "s1",
                "type": "test.echo",
                "config": {},
                "inputs": {"src": "$run.params.source_id"},
            },
            {"id": "s2", "type": "test.echo", "config": {}, "inputs": {}},
        ],
        "edges": [{"from": "s1", "to": "s2"}],
    }
    parent, source_id = await _seed_parent(session, definition)
    actor = uuid.uuid4()

    # Prior succeeded run whose idem key matches s1's (echo, config {},
    # resolved inputs {"src": source_id}).
    idem_key = echo_step.idempotency_key({}, {"src": source_id})
    prior = Run(
        project_id=parent.project_id,
        kind="step",
        step_type="test.echo",
        status="succeeded",
        input_refs={"src": source_id},
        output_refs={"echoed": "reused"},
        config={"_idem_key": idem_key},
    )
    session.add(prior)
    await session.commit()

    await advance_workflow(session, parent.id, actor)

    children = (
        (await session.execute(select(Run).where(Run.parent_run_id == parent.id))).scalars().all()
    )
    by_step = {c.step_id: c for c in children}
    # s1 reused: succeeded, copied outputs, NOT enqueued.
    assert by_step["s1"].status == "succeeded"
    assert by_step["s1"].output_refs == {"echoed": "reused"}
    # s2 newly created pending and enqueued.
    assert by_step["s2"].status == "pending"

    assert await fake_redis.xlen(STREAM) == 1
    entries = await fake_redis.xrange(STREAM)
    assert entries[0][1]["job_id"] == str(by_step["s2"].id)
    assert entries[0][1]["step_type"] == "test.echo"
