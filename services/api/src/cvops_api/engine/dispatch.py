"""Shared workflow-run creation.

Both the explicit run endpoint (`POST /workflows/{id}/runs`) and the backend
auto-trigger on upload (`POST /data-sources/{id}/confirm-upload`) create a
pending workflow run the same way. Keep that in one place so the row shape and
the commit-before-background-task ordering can't drift between callers.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from cvops_api.db.models.runs import Run
from cvops_api.db.models.workflows import Workflow


async def create_workflow_run(
    session: AsyncSession,
    workflow: Workflow,
    params: dict[str, Any],
    actor_id: uuid.UUID,
) -> Run:
    """Insert a pending workflow run and commit it.

    Commits so the row is visible to the executor's own session before the
    caller schedules `execute_workflow` as a background task. The caller owns
    scheduling (BackgroundTasks is only available on the request).
    """
    run = Run(
        project_id=workflow.project_id,
        workflow_id=workflow.id,
        kind="workflow",
        status="pending",
        attempt=1,
        input_refs={"params": params},
        output_refs={},
        config={},
    )
    session.add(run)
    await session.flush()
    await session.commit()
    return run
