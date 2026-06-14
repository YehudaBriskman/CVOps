from fastapi import APIRouter
from sqlalchemy import text
from cvops_api.db.session import async_session_factory

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness + DB connectivity check."""
    async with async_session_factory() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.post("/cvat/webhook")
async def cvat_webhook(payload: dict) -> dict[str, str]:  # type: ignore[type-arg]
    """
    Phase 2: receives CVAT job-completed events.
    Looks up labeling_job by cvat_task_id, pulls annotations,
    inserts annotation_revisions, calls resume_workflow().
    """
    return {"received": "ok"}
