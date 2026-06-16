"""
JobRunner — picks up a single job from the runs table and executes it.

Enforces the full job lifecycle:
  pending → running → succeeded | failed | waiting (gate)

On success, calls POST /internal/runs/{workflow_run_id}/advance so the API
executor can chain the next step in the DAG.
"""

from __future__ import annotations

import logging
from datetime import datetime, UTC
from typing import Any

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from cvops_api.core.audit import emit_event
from cvops_api.core.registry import registry
from cvops_api.core.storage import get_storage
from cvops_api.db.models.runs import Run
from cvops_api.engine.step import GateException, StepContext

from cvops_worker_common.config import worker_settings
from cvops_worker_common.session import async_session_factory

logger = logging.getLogger(__name__)

# Worker-executed steps have no interactive user. events.actor_id is a UUID
# column, so use the system sentinel (matches worker_cvat.sync.SYSTEM_ACTOR_ID)
# rather than a non-UUID label like "service:worker".
SYSTEM_ACTOR_ID = "00000000-0000-0000-0000-000000000000"


async def run_job(job_id: str, step_type: str) -> None:
    """Entry point called by ConsumerLoop for each message. Opens its own session."""
    async with async_session_factory() as session:
        run = await _acquire(session, job_id)
        if run is None:
            return  # taken by another worker replica

        try:
            output = await _execute(session, run, step_type)
            await _succeed(session, run, output)
            await session.commit()
            await _advance(run)
        except GateException as gate:
            await _wait(session, run, gate.gate_data)
            await session.commit()
        except Exception as exc:
            await _fail(session, run, str(exc))
            await session.commit()
            logger.exception("Job %s failed: %s", job_id, exc)


async def _acquire(session: AsyncSession, job_id: str) -> Run | None:
    """Lock the run row. Returns None if already taken (SKIP LOCKED)."""
    result = await session.execute(
        select(Run)
        .where(Run.id == job_id)  # type: ignore[arg-type]
        .with_for_update(skip_locked=True)
    )
    run = result.scalar_one_or_none()
    if run is None:
        return None

    if run.status != "pending":
        return None

    run.status = "running"
    run.started_at = datetime.now(UTC)
    await session.flush()
    await emit_event(
        session,
        actor_id=None,
        actor_type="service",
        entity_type="run",
        entity_id=run.id,
        action="run.started",
    )
    return run


async def _execute(
    session: AsyncSession, run: Run, step_type: str
) -> dict[str, Any]:
    try:
        reg = registry.resolve(step_type)
    except KeyError as exc:
        raise RuntimeError(f"Unknown step type: {step_type!r}") from exc

    step_impl = reg.impl
    config: dict[str, Any] = run.config or {}
    inputs: dict[str, Any] = run.input_refs or {}

    ctx = StepContext(
        session=session,
        storage=get_storage(),
        project_id=str(run.project_id),
        run_id=str(run.id),
        actor_id=SYSTEM_ACTOR_ID,
        emit_event=lambda **kw: emit_event(session, **kw),
    )

    return await step_impl.run(ctx, config, inputs)


async def _succeed(
    session: AsyncSession, run: Run, output: dict[str, Any]
) -> None:
    run.status = "succeeded"
    run.output_refs = output
    run.finished_at = datetime.now(UTC)
    await session.flush()
    await emit_event(
        session,
        actor_id=None,
        actor_type="service",
        entity_type="run",
        entity_id=run.id,
        action="run.succeeded",
    )


async def _wait(
    session: AsyncSession, run: Run, gate_data: dict[str, Any]
) -> None:
    run.status = "waiting"
    run.output_refs = {"gate_data": gate_data}
    run.finished_at = datetime.now(UTC)
    await session.flush()
    await emit_event(
        session,
        actor_id=None,
        actor_type="service",
        entity_type="run",
        entity_id=run.id,
        action="run.waiting",
    )


async def _fail(session: AsyncSession, run: Run, error: str) -> None:
    run.status = "failed"
    run.error = error
    run.finished_at = datetime.now(UTC)
    await session.flush()
    await emit_event(
        session,
        actor_id=None,
        actor_type="service",
        entity_type="run",
        entity_id=run.id,
        action="run.failed",
        payload={"error": error},
    )


async def _advance(run: Run) -> None:
    """Signal the API executor to resolve and enqueue the next DAG step."""
    if not run.parent_run_id:
        return
    url = (
        f"{worker_settings.API_BASE_URL}/internal/runs"
        f"/{run.parent_run_id}/advance"
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                json={"step_run_id": str(run.id), "output_refs": run.output_refs},
                headers={"Authorization": f"Bearer {worker_settings.WORKER_TOKEN}"},
            )
            if resp.status_code == 404:
                logger.debug("Advance endpoint not yet implemented — skipping chain")
            elif resp.status_code >= 400:
                logger.warning(
                    "Advance call failed: %s %s", resp.status_code, resp.text
                )
    except httpx.RequestError as exc:
        logger.warning("Advance call error (will not retry): %s", exc)
