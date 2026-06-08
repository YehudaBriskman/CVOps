from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, UTC

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cvops_api.core.auth import get_current_user
from cvops_api.db.session import get_session
from cvops_api.db.models.auth import User
from cvops_api.db.models.projects import Project
from cvops_api.db.models.workflows import Workflow
from cvops_api.db.models.runs import Run, Event
from cvops_api.engine.executor import execute_workflow
from cvops_api.schemas.runs import RunCreate, RunOut, RunDetail, EventOut, GateResolve

router = APIRouter()


async def _check_project(
    project_id: uuid.UUID,
    current_user: User,
    session: AsyncSession,
) -> Project:
    r = await session.execute(
        select(Project).where(
            Project.id == project_id,
            Project.org_id == current_user.org_id,
            Project.deleted_at == None,  # noqa: E711
        )
    )
    proj = r.scalar_one_or_none()
    if proj is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj


@router.post("/workflows/{workflow_id}/runs", response_model=RunOut, status_code=201)
async def create_run(
    workflow_id: uuid.UUID,
    body: RunCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RunOut:
    r = await session.execute(select(Workflow).where(Workflow.id == workflow_id))
    wf = r.scalar_one_or_none()
    if wf is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    await _check_project(wf.project_id, current_user, session)

    run = Run(
        project_id=wf.project_id,
        workflow_id=wf.id,
        kind="workflow",
        status="pending",
        attempt=1,
        input_refs={"params": body.params},
        output_refs={},
        config={},
    )
    session.add(run)
    await session.flush()

    # Commit before background task so the row is visible to the executor session
    await session.commit()

    background_tasks.add_task(execute_workflow, run.id, current_user.id)
    return RunOut.model_validate(run)


@router.get("/runs/{id}", response_model=RunDetail)
async def get_run(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RunDetail:
    r = await session.execute(select(Run).where(Run.id == id))
    run = r.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    await _check_project(run.project_id, current_user, session)

    r_steps = await session.execute(
        select(Run).where(Run.parent_run_id == run.id)
    )
    steps = list(r_steps.scalars().all())

    return RunDetail(
        run=RunOut.model_validate(run),
        steps=[RunOut.model_validate(s) for s in steps],
    )


@router.get("/runs/{id}/events", response_model=list[EventOut])
async def list_run_events(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[EventOut]:
    r = await session.execute(select(Run).where(Run.id == id))
    run = r.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    await _check_project(run.project_id, current_user, session)

    # Collect child run ids
    r_children = await session.execute(
        select(Run.id).where(Run.parent_run_id == run.id)
    )
    child_ids = [row for row in r_children.scalars().all()]
    entity_ids = [run.id, *child_ids]

    r_events = await session.execute(
        select(Event)
        .where(
            Event.entity_type == "run",
            Event.entity_id.in_(entity_ids),
        )
        .order_by(Event.created_at)
    )
    return [EventOut.model_validate(ev) for ev in r_events.scalars().all()]


@router.get("/runs/{id}/events/stream")
async def stream_run_events(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    r = await session.execute(select(Run).where(Run.id == id))
    run = r.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    proj = await session.get(Project, run.project_id)
    if proj is None or proj.org_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Run not found")

    async def generate():
        from cvops_api.db.session import async_session_factory

        seen_ids: set[uuid.UUID] = set()
        terminal = {"succeeded", "failed", "cancelled"}

        async with async_session_factory() as s:
            while True:
                result = await s.execute(
                    select(Event)
                    .where(
                        Event.entity_type == "run",
                        Event.entity_id == id,
                    )
                    .order_by(Event.created_at)
                )
                for ev in result.scalars().all():
                    if ev.id not in seen_ids:
                        seen_ids.add(ev.id)
                        data = EventOut.model_validate(ev).model_dump_json()
                        yield f"data: {data}\n\n"

                run_result = await s.execute(select(Run).where(Run.id == id))
                current_run = run_result.scalar_one_or_none()
                if current_run and current_run.status in terminal:
                    yield "event: done\ndata: {}\n\n"
                    return

                await asyncio.sleep(1)

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/runs/{id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_run(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    r = await session.execute(select(Run).where(Run.id == id))
    run = r.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    await _check_project(run.project_id, current_user, session)

    if run.status in {"pending", "running"}:
        run.status = "cancelled"
        run.finished_at = datetime.now(UTC)
        await session.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/runs/{id}/retry", response_model=RunOut, status_code=status.HTTP_201_CREATED)
async def retry_run(
    id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RunOut:
    r = await session.execute(select(Run).where(Run.id == id))
    run = r.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    await _check_project(run.project_id, current_user, session)

    new_run = Run(
        project_id=run.project_id,
        workflow_id=run.workflow_id,
        kind=run.kind,
        status="pending",
        attempt=run.attempt + 1,
        input_refs=run.input_refs,
        output_refs={},
        config=run.config,
    )
    session.add(new_run)
    await session.flush()
    await session.commit()

    background_tasks.add_task(execute_workflow, new_run.id, current_user.id)
    return RunOut.model_validate(new_run)


@router.post("/runs/{id}/gates/{step_id}/resolve")
async def resolve_gate(
    id: uuid.UUID,
    step_id: str,
    body: GateResolve,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    r = await session.execute(select(Run).where(Run.id == id))
    run = r.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    await _check_project(run.project_id, current_user, session)

    r_child = await session.execute(
        select(Run).where(
            Run.parent_run_id == run.id,
            Run.step_id == step_id,
            Run.status == "waiting",
        )
    )
    child = r_child.scalar_one_or_none()
    if child is None:
        raise HTTPException(status_code=404, detail="Waiting gate step not found")

    child.output_refs = {"resolution": body.resolution}
    child.status = "succeeded"
    child.finished_at = datetime.now(UTC)
    await session.commit()

    background_tasks.add_task(execute_workflow, run.id, current_user.id)
    return {"status": "resumed"}
