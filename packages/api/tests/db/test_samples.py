import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from cvops_api.db.models.samples import DataSource, Sample
from tests.db.conftest import make_blob, make_data_source, make_project, make_sample


# ---------------------------------------------------------------------------
# DataSource tests
# ---------------------------------------------------------------------------


async def test_data_source_create(session: AsyncSession):
    project = await make_project(session)
    ds = DataSource(project_id=project.id, type="video")
    session.add(ds)
    await session.flush()

    assert ds.project_id == project.id
    assert ds.type == "video"


async def test_data_source_status_default(session: AsyncSession):
    project = await make_project(session)
    ds = DataSource(project_id=project.id, type="image_folder")
    session.add(ds)
    await session.flush()
    await session.refresh(ds)

    assert ds.status == "pending"


async def test_data_source_project_fk(session: AsyncSession):
    ds = DataSource(project_id=uuid.uuid4(), type="video")
    session.add(ds)
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


async def test_data_source_blob_hash_nullable(session: AsyncSession):
    project = await make_project(session)
    ds = DataSource(project_id=project.id, type="external_uri", external_uri="https://example.com/data")
    session.add(ds)
    await session.flush()

    assert ds.blob_hash is None


async def test_data_source_metadata_stored(session: AsyncSession):
    project = await make_project(session)
    ds = DataSource(project_id=project.id, type="video", metadata_={"fps": 30})
    session.add(ds)
    await session.flush()
    await session.refresh(ds)

    assert ds.metadata_["fps"] == 30


# ---------------------------------------------------------------------------
# Sample tests
# ---------------------------------------------------------------------------


async def test_sample_create(session: AsyncSession):
    project = await make_project(session)
    blob = await make_blob(session)
    ds = await make_data_source(session, project_id=project.id)
    sample = Sample(
        project_id=project.id,
        blob_hash=blob.hash,
        source_id=ds.id,
        width=1920,
        height=1080,
    )
    session.add(sample)
    await session.flush()

    assert sample.id is not None
    assert sample.project_id == project.id
    assert sample.blob_hash == blob.hash
    assert sample.source_id == ds.id
    assert sample.width == 1920
    assert sample.height == 1080


async def test_sample_unique_project_blob(session: AsyncSession):
    project = await make_project(session)
    blob = await make_blob(session)
    ds = await make_data_source(session, project_id=project.id)

    sample_a = Sample(
        project_id=project.id,
        blob_hash=blob.hash,
        source_id=ds.id,
        width=640,
        height=480,
    )
    session.add(sample_a)
    await session.flush()

    sample_b = Sample(
        project_id=project.id,
        blob_hash=blob.hash,
        source_id=ds.id,
        width=640,
        height=480,
    )
    session.add(sample_b)
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


async def test_sample_different_projects_same_blob(session: AsyncSession):
    blob = await make_blob(session)

    project_a = await make_project(session)
    ds_a = await make_data_source(session, project_id=project_a.id)
    sample_a = Sample(
        project_id=project_a.id,
        blob_hash=blob.hash,
        source_id=ds_a.id,
        width=1280,
        height=720,
    )
    session.add(sample_a)
    await session.flush()

    project_b = await make_project(session)
    ds_b = await make_data_source(session, project_id=project_b.id)
    sample_b = Sample(
        project_id=project_b.id,
        blob_hash=blob.hash,
        source_id=ds_b.id,
        width=1280,
        height=720,
    )
    session.add(sample_b)
    await session.flush()

    assert sample_a.id != sample_b.id
    assert sample_a.blob_hash == sample_b.blob_hash


async def test_sample_frame_index_nullable(session: AsyncSession):
    sample = await make_sample(session)

    assert sample.frame_index is None


async def test_sample_frame_index_set(session: AsyncSession):
    sample = await make_sample(session, frame_index=42)
    await session.refresh(sample)

    assert sample.frame_index == 42


async def test_sample_thumbnail_hash_nullable(session: AsyncSession):
    sample = await make_sample(session)

    assert sample.thumbnail_hash is None


async def test_sample_source_fk(session: AsyncSession):
    project = await make_project(session)
    blob = await make_blob(session)
    sample = Sample(
        project_id=project.id,
        blob_hash=blob.hash,
        source_id=uuid.uuid4(),
        width=800,
        height=600,
    )
    session.add(sample)
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


async def test_sample_blob_fk(session: AsyncSession):
    project = await make_project(session)
    ds = await make_data_source(session, project_id=project.id)
    sample = Sample(
        project_id=project.id,
        blob_hash=f"sha256:{'b' * 63}",
        source_id=ds.id,
        width=800,
        height=600,
    )
    session.add(sample)
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()
