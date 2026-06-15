"""Error- and edge-path coverage for the CVAT pull flow (handle_cvat_sync).

The happy path lives in test_sync.py. Here we pin the branches that short-circuit
or skip rather than write a revision:

  * missing labeling_job for the task id  → warn + return, no advance
  * empty gate sample_ids                  → error + return, no advance
  * a reviewed frame index past the sample list → that frame is ignored
  * a sample with no prior revision        → skipped (no ontology to inherit),
    the job still completes with zero out-revisions and the gate still resumes
  * a gate run with no parent              → completes but does not chain

All are DB-backed (testcontainers) and mock advance_workflow to assert chaining.
Each seed uses a unique cvat_task_id (the handler selects by task id with
``.first()``), so tests can't cross-wire. Requires Docker.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text

import worker_cvat.sync as sync
from tests.conftest import HUMAN_REVIEWED, seed_review


@pytest.fixture
def _patched(session_factory, monkeypatch):
    """Point the handler's session factory at the test DB and stub advance."""
    advance = AsyncMock()
    monkeypatch.setattr(sync, "async_session_factory", session_factory)
    monkeypatch.setattr(sync, "advance_workflow", advance)
    return advance


async def _count_revisions(session_factory, sample_id: str) -> int:
    async with session_factory() as s:
        return (
            await s.execute(
                text(
                    "SELECT count(*) FROM annotation_revisions "
                    "WHERE sample_id = CAST(:s AS uuid)"
                ),
                {"s": sample_id},
            )
        ).scalar()


async def _job_status(session_factory, labeling_job_id: str) -> str:
    async with session_factory() as s:
        return (
            await s.execute(
                text("SELECT status FROM labeling_jobs WHERE id = CAST(:id AS uuid)"),
                {"id": labeling_job_id},
            )
        ).scalar()


async def test_missing_labeling_job_is_noop(session_factory, fake_pull, _patched):
    # No job seeded for this task id → handler warns and returns.
    await sync.handle_cvat_sync({"cvat_task_id": "999999"})
    _patched.assert_not_awaited()


async def test_empty_sample_ids_is_noop(session_factory, fake_pull, _patched):
    # gate_data has no sample_ids → handler logs error and returns before pull.
    ids = await seed_review(session_factory, sample_ids_override=[])
    await sync.handle_cvat_sync({"cvat_task_id": str(ids["cvat_task_id"])})
    _patched.assert_not_awaited()
    # No human revision written; the seeded model revision is untouched.
    assert await _count_revisions(session_factory, ids["sample_id"]) == 1
    assert await _job_status(session_factory, ids["labeling_job_id"]) == "pushed"


async def test_frame_index_past_samples_is_ignored(
    session_factory, _patched, fake_pull_factory
):
    """A reviewed frame index beyond the pushed sample list is skipped, not crashed."""
    ids = await seed_review(session_factory)
    # Frame 0 maps to our one sample; frame 5 has no corresponding sample_id.
    with fake_pull_factory({0: HUMAN_REVIEWED, 5: HUMAN_REVIEWED}):
        await sync.handle_cvat_sync({"cvat_task_id": str(ids["cvat_task_id"])})

    # Exactly one human revision (for frame 0); frame 5 ignored.
    async with session_factory() as s:
        n = (
            await s.execute(
                text(
                    "SELECT count(*) FROM annotation_revisions "
                    "WHERE sample_id = CAST(:s AS uuid) "
                    "AND provenance->>'source' = 'human'"
                ),
                {"s": ids["sample_id"]},
            )
        ).scalar()
    assert n == 1
    assert await _job_status(session_factory, ids["labeling_job_id"]) == "completed"
    _patched.assert_awaited_once()


async def test_sample_without_prior_revision_is_skipped(
    session_factory, _patched, fake_pull
):
    """No prior revision → no ontology to inherit → sample skipped, but the job
    still completes (zero out-revisions) and the gate resumes."""
    ids = await seed_review(session_factory, with_prior_revision=False)

    await sync.handle_cvat_sync({"cvat_task_id": str(ids["cvat_task_id"])})

    # No revision was written for the sample (it had none to inherit from).
    assert await _count_revisions(session_factory, ids["sample_id"]) == 0

    async with session_factory() as s:
        lj = (
            await s.execute(
                text(
                    "SELECT status, annotation_revision_ids_out FROM labeling_jobs "
                    "WHERE id = CAST(:id AS uuid)"
                ),
                {"id": ids["labeling_job_id"]},
            )
        ).first()
        assert lj[0] == "completed"
        assert lj[1] == []  # nothing inherited, so nothing emitted

        child = (
            await s.execute(
                text("SELECT status FROM runs WHERE id = CAST(:id AS uuid)"),
                {"id": ids["child_id"]},
            )
        ).first()
        assert child[0] == "succeeded"

    # The gate still resumes downstream even with zero revisions.
    _patched.assert_awaited_once()


async def test_no_parent_skips_advance(session_factory, fake_pull, monkeypatch):
    """A gate run with no parent_run_id completes the job but does not chain."""
    ids = await seed_review(session_factory)
    async with session_factory() as s:
        await s.execute(
            text("UPDATE runs SET parent_run_id = NULL WHERE id = CAST(:id AS uuid)"),
            {"id": ids["child_id"]},
        )
        await s.commit()

    advance = AsyncMock()
    monkeypatch.setattr(sync, "async_session_factory", session_factory)
    monkeypatch.setattr(sync, "advance_workflow", advance)

    await sync.handle_cvat_sync({"cvat_task_id": str(ids["cvat_task_id"])})

    # Job completed + gate resumed, but with no parent there's nothing to advance.
    advance.assert_not_awaited()
    assert await _job_status(session_factory, ids["labeling_job_id"]) == "completed"
