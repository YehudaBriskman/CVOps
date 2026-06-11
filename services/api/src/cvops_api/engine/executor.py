"""
Workflow executor — runs steps in topological order.
Called as a BackgroundTask; creates its own DB session.
"""

from __future__ import annotations

import uuid
from collections import deque
from datetime import datetime, UTC
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cvops_api.db.session import async_session_factory
from cvops_api.db.models.runs import Run
from cvops_api.db.models.workflows import Workflow
from cvops_api.core.registry import registry
from cvops_api.core.storage import get_storage
from cvops_api.core.audit import emit_event
from cvops_api.engine.step import StepContext, GateException
from cvops_api.engine.ref_resolver import resolve_refs, ResolutionError


async def execute_workflow(run_id: uuid.UUID, actor_id: uuid.UUID) -> None:
    """Entry point for BackgroundTasks. Creates its own DB session."""
    async with async_session_factory() as session:
        try:
            await _run(session, run_id=run_id, actor_id=actor_id)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            # Last-resort: try to mark the run failed
            async with async_session_factory() as s2:
                r = await s2.execute(select(Run).where(Run.id == run_id))
                run = r.scalar_one_or_none()
                if run:
                    run.status = "failed"
                    run.error = f"Executor crash: {exc}"
                    run.finished_at = datetime.now(UTC)
                    await s2.commit()


async def _run(session: AsyncSession, *, run_id: uuid.UUID, actor_id: uuid.UUID) -> None:
    # 1. Load workflow run + definition
    r = await session.execute(select(Run).where(Run.id == run_id))
    parent = r.scalar_one_or_none()
    if parent is None:
        return

    wf_result = await session.execute(select(Workflow).where(Workflow.id == parent.workflow_id))
    workflow = wf_result.scalar_one_or_none()
    if workflow is None:
        await _fail(session, parent, actor_id, "Workflow definition not found")
        return

    definition = workflow.definition or {}
    steps_list = definition.get("steps", [])
    edges = definition.get("edges", [])
    steps_by_id = {s["id"]: s for s in steps_list}

    # 2. Topological sort
    ordered = _topo_sort(list(steps_by_id.keys()), edges)
    if ordered is None:
        await _fail(session, parent, actor_id, "Workflow has a cycle")
        return

    # 3. Seed step_outputs from already-succeeded child runs (resume support)
    step_outputs: dict[str, dict[str, Any]] = {}
    existing = await session.execute(select(Run).where(Run.parent_run_id == run_id))
    for prev in existing.scalars().all():
        if prev.status == "succeeded" and prev.step_id:
            step_outputs[prev.step_id] = prev.output_refs or {}

    run_params: dict[str, Any] = (parent.input_refs or {}).get("params", {})

    # 4. Execute each step
    for step_id in ordered:
        step_def = steps_by_id[step_id]
        type_key: str = step_def["type"]
        config: dict[str, Any] = step_def.get("config", {})

        # Find or create child Run
        cr = await session.execute(
            select(Run).where(Run.parent_run_id == run_id, Run.step_id == step_id)
        )
        child_or_none: Run | None = cr.scalar_one_or_none()

        if child_or_none is None:
            child_or_none = Run(
                project_id=parent.project_id,
                kind="step",
                parent_run_id=run_id,
                workflow_id=parent.workflow_id,
                step_id=step_id,
                step_type=type_key,
                status="pending",
                input_refs={},
                output_refs={},
                config=config,
            )
            session.add(child_or_none)
            await session.flush()

        child: Run = child_or_none

        if child.status == "succeeded":
            step_outputs[step_id] = child.output_refs or {}
            continue
        if child.status == "waiting":
            return  # gate not yet resolved
        if child.status == "failed":
            return  # stop propagating

        # Validate config
        try:
            registry.validate_config(type_key, config)
        except Exception as exc:
            await _fail_child(session, child, parent, actor_id, f"Config invalid: {exc}")
            return

        # Resolve inputs
        try:
            inputs_template = step_def.get("inputs", {})
            resolved = resolve_refs(inputs_template, step_outputs, run_params)
        except ResolutionError as exc:
            await _fail_child(session, child, parent, actor_id, f"Input resolution: {exc}")
            return

        # Get step impl
        try:
            reg = registry.resolve(type_key)
        except KeyError:
            await _fail_child(session, child, parent, actor_id, f"Unknown step type: {type_key!r}")
            return

        step_impl = reg.impl
        idem_key = step_impl.idempotency_key(config, resolved)

        # Idempotency: check for a prior succeeded run with same key
        idem_result = await session.execute(
            select(Run).where(
                Run.step_type == type_key,
                Run.status == "succeeded",
                Run.config["_idem_key"].astext == idem_key,
            )
        )
        prior = idem_result.scalar_one_or_none()
        if prior is not None:
            child.output_refs = prior.output_refs
            child.status = "succeeded"
            child.finished_at = datetime.now(UTC)
            await session.flush()
            step_outputs[step_id] = child.output_refs or {}
            continue

        # Store idem key and mark running
        child.config = {**config, "_idem_key": idem_key}
        child.status = "running"
        child.started_at = datetime.now(UTC)
        await session.flush()
        await emit_event(
            session,
            actor_id=actor_id,
            actor_type="system",
            entity_type="run",
            entity_id=child.id,
            action="run.started",
        )

        # Build context
        ctx = StepContext(
            session=session,
            storage=get_storage(),
            project_id=str(parent.project_id),
            run_id=str(child.id),
            actor_id=str(actor_id),
            emit_event=lambda **kw: emit_event(session, **kw),
        )

        # Execute
        try:
            output = await step_impl.run(ctx, config, resolved)
        except GateException as gate:
            child.status = "waiting"
            child.output_refs = {"gate_data": gate.gate_data}
            child.finished_at = datetime.now(UTC)
            await session.flush()
            await emit_event(
                session,
                actor_id=actor_id,
                actor_type="system",
                entity_type="run",
                entity_id=child.id,
                action="run.waiting",
            )
            return  # Workflow paused at gate
        except Exception as exc:
            await _fail_child(session, child, parent, actor_id, str(exc))
            return

        child.output_refs = output
        child.status = "succeeded"
        child.finished_at = datetime.now(UTC)
        await session.flush()
        await emit_event(
            session,
            actor_id=actor_id,
            actor_type="system",
            entity_type="run",
            entity_id=child.id,
            action="run.succeeded",
        )
        step_outputs[step_id] = output

    # All steps done
    parent.status = "succeeded"
    parent.finished_at = datetime.now(UTC)
    await session.flush()
    await emit_event(
        session,
        actor_id=actor_id,
        actor_type="system",
        entity_type="run",
        entity_id=run_id,
        action="run.succeeded",
    )


def _topo_sort(step_ids: list[str], edges: list[dict[str, str]]) -> list[str] | None:
    """Kahn's algorithm. Returns None if a cycle is detected."""
    in_degree: dict[str, int] = {s: 0 for s in step_ids}
    adj: dict[str, list[str]] = {s: [] for s in step_ids}
    for e in edges:
        src, dst = e["from"], e["to"]
        adj.setdefault(src, []).append(dst)
        in_degree[dst] = in_degree.get(dst, 0) + 1

    queue: deque[str] = deque(s for s in step_ids if in_degree[s] == 0)
    result: list[str] = []
    while queue:
        node = queue.popleft()
        result.append(node)
        for nb in adj.get(node, []):
            in_degree[nb] -= 1
            if in_degree[nb] == 0:
                queue.append(nb)

    return result if len(result) == len(step_ids) else None


async def _fail(session: AsyncSession, run: Run, actor_id: uuid.UUID, error: str) -> None:
    run.status = "failed"
    run.error = error
    run.finished_at = datetime.now(UTC)
    await session.flush()
    await emit_event(
        session,
        actor_id=actor_id,
        actor_type="system",
        entity_type="run",
        entity_id=run.id,
        action="run.failed",
        payload={"error": error},
    )


async def _fail_child(
    session: AsyncSession,
    child: Run,
    parent: Run,
    actor_id: uuid.UUID,
    error: str,
) -> None:
    child.status = "failed"
    child.error = error
    child.finished_at = datetime.now(UTC)
    await _fail(session, parent, actor_id, f"Step '{child.step_id}' failed: {error}")
