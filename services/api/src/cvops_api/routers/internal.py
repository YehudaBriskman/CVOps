import hashlib
import hmac
import os

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text

from cvops_api.core.redis_client import get_redis
from cvops_api.db.session import async_session_factory

router = APIRouter()

# Redis stream the CVAT worker consumes. Must match HumanReviewStep.queue and
# the worker's REDIS_STREAM.
CVAT_STREAM = "cvat"


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness + DB connectivity check."""
    async with async_session_factory() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ok"}


def _valid_signature(secret: str, body: bytes, header: str | None) -> bool:
    """Constant-time check of CVAT's ``X-Signature-256: sha256=<hex>`` header."""
    if not header:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)


@router.post("/cvat/webhook")
async def cvat_webhook(request: Request) -> dict[str, str]:
    """Receive CVAT job/task update events and bridge them onto the cvat stream.

    The API does no CVAT I/O: it validates the HMAC signature and, on a job
    completion event, enqueues a thin ``cvat_sync`` doorbell keyed by
    ``cvat_task_id``. The worker reloads the labeling_job, pulls the reviewed
    annotations, writes revisions, and resumes the gated run. The worker
    short-circuits on an already-completed job, so duplicate webhooks are safe.
    """
    secret = os.environ.get("CVAT_WEBHOOK_SECRET")
    if not secret:
        # Feature not configured — refuse rather than accept unauthenticated calls.
        raise HTTPException(status_code=503, detail="CVAT webhook not configured")

    body = await request.body()
    if not _valid_signature(secret, body, request.headers.get("X-Signature-256")):
        raise HTTPException(status_code=401, detail="bad signature")

    payload = await request.json()

    # Only forward job-completion events; CVAT fires the webhook on many updates.
    # Task-level events are forwarded too (rare) so a manual task finish still
    # reconciles. The worker decides whether the whole job is actually done and
    # dedups via labeling_jobs.status.
    job = payload.get("job") or {}
    task = payload.get("task") or {}
    cvat_task_id = job.get("task_id") or task.get("id")
    job_completed = job.get("state") == "completed"
    if cvat_task_id is None or not (job_completed or task):
        return {"received": "ignored"}

    await get_redis().xadd(
        CVAT_STREAM,
        {"kind": "cvat_sync", "cvat_task_id": str(cvat_task_id)},
    )
    return {"received": "queued"}
