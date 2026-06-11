import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from cvops_api.db.models.labeling import LabelingJob
from tests.db.conftest import make_project, make_run


async def test_labeling_job_create(session: AsyncSession):
    project = await make_project(session)
    run = await make_run(session, project_id=project.id)
    job = LabelingJob(
        project_id=project.id,
        run_id=run.id,
        step_id="step-label-1",
        cvat_task_id=42,
        sample_count=100,
    )
    session.add(job)
    await session.flush()

    assert job.id is not None
    assert job.project_id == project.id
    assert job.run_id == run.id
    assert job.cvat_task_id == 42
    assert job.sample_count == 100


async def test_labeling_job_status_default(session: AsyncSession):
    project = await make_project(session)
    run = await make_run(session, project_id=project.id)
    job = LabelingJob(
        project_id=project.id,
        run_id=run.id,
        step_id="step-label-2",
        cvat_task_id=99,
        sample_count=50,
    )
    session.add(job)
    await session.flush()
    await session.refresh(job)

    assert job.status == "pushed"


async def test_labeling_job_cvat_job_ids_default(session: AsyncSession):
    project = await make_project(session)
    run = await make_run(session, project_id=project.id)
    job = LabelingJob(
        project_id=project.id,
        run_id=run.id,
        step_id="step-label-3",
        cvat_task_id=7,
        sample_count=10,
    )
    session.add(job)
    await session.flush()
    await session.refresh(job)

    assert job.cvat_job_ids == []


async def test_labeling_job_completed_at_nullable(session: AsyncSession):
    project = await make_project(session)
    run = await make_run(session, project_id=project.id)
    job = LabelingJob(
        project_id=project.id,
        run_id=run.id,
        step_id="step-label-4",
        cvat_task_id=13,
        sample_count=25,
    )
    session.add(job)
    await session.flush()

    assert job.completed_at is None


async def test_labeling_job_run_fk(session: AsyncSession):
    project = await make_project(session)
    fake_run_id = uuid.uuid4()
    job = LabelingJob(
        project_id=project.id,
        run_id=fake_run_id,
        step_id="step-label-fk",
        cvat_task_id=55,
        sample_count=5,
    )
    session.add(job)

    with pytest.raises(IntegrityError):
        await session.flush()

    await session.rollback()


async def test_labeling_job_revision_ids_jsonb(session: AsyncSession):
    project = await make_project(session)
    run = await make_run(session, project_id=project.id)
    revision_ids = ["rev-id-1", "rev-id-2", "rev-id-3"]
    job = LabelingJob(
        project_id=project.id,
        run_id=run.id,
        step_id="step-label-5",
        cvat_task_id=88,
        sample_count=200,
        annotation_revision_ids_in=revision_ids,
    )
    session.add(job)
    await session.flush()
    await session.refresh(job)

    assert isinstance(job.annotation_revision_ids_in, list)
    assert len(job.annotation_revision_ids_in) == 3
    assert job.annotation_revision_ids_in[0] == "rev-id-1"
    assert job.annotation_revision_ids_in[2] == "rev-id-3"
