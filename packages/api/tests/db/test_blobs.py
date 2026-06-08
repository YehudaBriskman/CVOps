import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from cvops_api.db.models.blobs import Blob, TypeSchema
from tests.db.conftest import make_blob

# ---------------------------------------------------------------------------
# Blob tests
# ---------------------------------------------------------------------------


async def test_blob_create(session: AsyncSession):
    hash_val = "sha256:" + "a" * 64
    blob = Blob(
        hash=hash_val,
        storage_backend="minio",
        storage_key="blobs/aa/test-object",
        size_bytes=2048,
        media_type="image/png",
    )
    session.add(blob)
    await session.flush()

    assert blob.hash == hash_val


async def test_blob_pk_is_hash_not_uuid(session: AsyncSession):
    blob = await make_blob(session)

    assert hasattr(blob, "hash")
    assert not hasattr(blob, "id")


async def test_blob_duplicate_hash_raises(session: AsyncSession):
    shared_hash = "sha256:" + "b" * 64

    blob_a = Blob(
        hash=shared_hash,
        storage_backend="minio",
        storage_key="blobs/aa/object-a",
        size_bytes=512,
        media_type="image/jpeg",
    )
    session.add(blob_a)
    await session.flush()

    blob_b = Blob(
        hash=shared_hash,
        storage_backend="minio",
        storage_key="blobs/aa/object-b",
        size_bytes=1024,
        media_type="image/jpeg",
    )
    session.add(blob_b)

    with pytest.raises(IntegrityError):
        await session.flush()

    await session.rollback()


async def test_blob_created_at_auto(session: AsyncSession):
    blob = Blob(
        hash="sha256:" + "c" * 64,
        storage_backend="s3",
        storage_key="blobs/cc/auto-ts",
        size_bytes=4096,
        media_type="video/mp4",
    )
    session.add(blob)
    await session.flush()

    result = await session.execute(select(Blob).where(Blob.hash == blob.hash))
    fetched = result.scalar_one()

    assert fetched.created_at is not None


async def test_blob_no_updated_at(session: AsyncSession):
    blob = await make_blob(session)

    assert not hasattr(blob, "updated_at")


async def test_blob_storage_fields(session: AsyncSession):
    blob = Blob(
        hash="sha256:" + "d" * 64,
        storage_backend="gcs",
        storage_key="blobs/dd/my-object-key",
        size_bytes=8192,
        media_type="application/octet-stream",
    )
    session.add(blob)
    await session.flush()

    assert blob.storage_backend == "gcs"
    assert blob.storage_key == "blobs/dd/my-object-key"
    assert blob.size_bytes == 8192
    assert blob.media_type == "application/octet-stream"


# ---------------------------------------------------------------------------
# TypeSchema tests
# ---------------------------------------------------------------------------


async def test_type_schema_create(session: AsyncSession):
    ts = TypeSchema(
        type_key="step.extract_frames",
        category="step",
        json_schema={"type": "object"},
    )
    session.add(ts)
    await session.flush()

    assert ts.type_key == "step.extract_frames"


async def test_type_schema_pk_is_type_key(session: AsyncSession):
    ts = TypeSchema(
        type_key="step.pk_check",
        category="step",
        json_schema={"type": "object"},
    )
    session.add(ts)
    await session.flush()

    assert hasattr(ts, "type_key")
    assert not hasattr(ts, "id")


async def test_type_schema_duplicate_key_raises(session: AsyncSession):
    shared_key = "step.duplicate_test"

    ts_a = TypeSchema(
        type_key=shared_key,
        category="step",
        json_schema={"type": "object"},
    )
    session.add(ts_a)
    await session.flush()

    ts_b = TypeSchema(
        type_key=shared_key,
        category="step",
        json_schema={"type": "object", "properties": {}},
    )
    session.add(ts_b)

    with pytest.raises(IntegrityError):
        await session.flush()

    await session.rollback()


async def test_type_schema_version_default(session: AsyncSession):
    ts = TypeSchema(
        type_key="step.version_default",
        category="step",
        json_schema={"type": "object"},
    )
    session.add(ts)
    await session.flush()

    result = await session.execute(
        select(TypeSchema).where(TypeSchema.type_key == ts.type_key)
    )
    fetched = result.scalar_one()

    assert fetched.schema_version == "1"


async def test_type_schema_ui_hints_nullable(session: AsyncSession):
    ts = TypeSchema(
        type_key="step.no_hints",
        category="step",
        json_schema={"type": "object"},
    )
    session.add(ts)
    await session.flush()

    assert ts.ui_hints is None


async def test_type_schema_json_schema_stored(session: AsyncSession):
    complex_schema = {
        "type": "object",
        "properties": {
            "fps": {"type": "integer", "minimum": 1, "maximum": 120},
            "output_dir": {"type": "string"},
        },
        "required": ["fps"],
    }

    ts = TypeSchema(
        type_key="step.complex_schema",
        category="step",
        json_schema=complex_schema,
    )
    session.add(ts)
    await session.flush()

    result = await session.execute(
        select(TypeSchema).where(TypeSchema.type_key == ts.type_key)
    )
    fetched = result.scalar_one()

    assert fetched.json_schema == complex_schema
