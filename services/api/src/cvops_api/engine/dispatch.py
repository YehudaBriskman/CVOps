"""Shared workflow-run creation.

Both the explicit run endpoint (`POST /workflows/{id}/runs`) and the backend
auto-trigger on upload (`POST /data-sources/{id}/confirm-upload`) create a
pending workflow run the same way. Keep that in one place so the row shape and
the commit-before-advance ordering can't drift between callers. After creating
the run, callers invoke `advance_workflow` (engine/coordinator.py) to enqueue
the first ready steps onto Redis Streams.
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

    Commits so the row is durable before the caller invokes `advance_workflow`,
    which creates the first child step runs and rings their Redis queues.
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
