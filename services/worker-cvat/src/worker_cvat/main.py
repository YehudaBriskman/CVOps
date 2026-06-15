"""worker-cvat entrypoint.

Consumes the ``cvat`` Redis stream. Two message kinds arrive:
  * run doorbells ``{job_id, step_type}`` — normal step execution (step.human_review
    runs the push flow and parks the run at the gate), handled by run_job.
  * ``{kind: "cvat_sync", cvat_task_id}`` — the webhook bridge signalling a CVAT
    task is done; routed to the pull handler which resumes the gate.
"""

from __future__ import annotations

import asyncio
import logging

from cvops_api.core.redis_client import close_redis, init_redis
from cvops_worker_common import ConsumerLoop

from worker_cvat.sync import handle_cvat_sync

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

STREAM = "cvat"


def main() -> None:
    try:
        from cvops_steps import register_all

        register_all()
    except ImportError:
        logger.warning("cvops_steps not importable — registry is empty")

    loop = ConsumerLoop(
        stream=STREAM,
        step_types=["step.human_review"],
        sync_handler=handle_cvat_sync,
    )

    async def run() -> None:
        # The pull handler resumes gates via advance_workflow, which enqueues
        # downstream steps through the cvops_api redis singleton — so it must be
        # initialised (ConsumerLoop maintains its own connection separately).
        await init_redis()
        try:
            await loop.run_forever()
        finally:
            await close_redis()

    asyncio.run(run())


if __name__ == "__main__":
    main()
