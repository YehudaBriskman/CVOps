"""
Tests for cvops_api.core.storage.MinIOBackend using moto to mock S3.

MinIOBackend wraps synchronous boto3 calls inside async methods.
Since asyncio_mode = "auto" in pyproject.toml, async test functions are
collected and executed automatically without explicit @pytest.mark.anyio
or asyncio.run() wrappers.

Each test activates `with mock_aws():` and patches MINIO_ENDPOINT to None
so that boto3 targets the default AWS S3 endpoint — the one moto intercepts.
A non-None endpoint_url (e.g. localhost:9000) routes around moto's interception.
"""
from __future__ import annotations

import hashlib

import pytest
from moto import mock_aws
from unittest.mock import patch

from cvops_api.config import settings
from cvops_api.core.storage import MinIOBackend, StorageBackend


def _mocked_backend() -> MinIOBackend:
    """Instantiate MinIOBackend with moto-compatible settings.

    MINIO_ENDPOINT must be None so boto3 uses the default AWS S3 endpoint
    that moto's mock_aws intercepts. Any custom endpoint_url (localhost:*) is
    not intercepted by moto and would route to a real server.
    """
    return MinIOBackend()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_save_bytes_returns_sha256_hash() -> None:
    """save_bytes should return a string prefixed with 'sha256:'."""
    with mock_aws():
        with patch.object(settings, "MINIO_ENDPOINT", None), \
             patch.object(settings, "MINIO_ACCESS_KEY", "testing"), \
             patch.object(settings, "MINIO_SECRET_KEY", "testing"), \
             patch.object(settings, "MINIO_BUCKET", "test-bucket"):
            backend = _mocked_backend()
            blob_hash = await backend.save_bytes(b"hello", "application/octet-stream")

    assert isinstance(blob_hash, str)
    assert blob_hash.startswith("sha256:")


async def test_save_bytes_idempotent() -> None:
    """Saving the same bytes twice must return the identical hash without error."""
    with mock_aws():
        with patch.object(settings, "MINIO_ENDPOINT", None), \
             patch.object(settings, "MINIO_ACCESS_KEY", "testing"), \
             patch.object(settings, "MINIO_SECRET_KEY", "testing"), \
             patch.object(settings, "MINIO_BUCKET", "test-bucket"):
            backend = _mocked_backend()
            data = b"idempotent content"
            hash1 = await backend.save_bytes(data, "application/octet-stream")
            hash2 = await backend.save_bytes(data, "application/octet-stream")

    assert hash1 == hash2


async def test_get_bytes_returns_uploaded_content() -> None:
    """get_bytes should return exactly the bytes that were previously saved."""
    with mock_aws():
        with patch.object(settings, "MINIO_ENDPOINT", None), \
             patch.object(settings, "MINIO_ACCESS_KEY", "testing"), \
             patch.object(settings, "MINIO_SECRET_KEY", "testing"), \
             patch.object(settings, "MINIO_BUCKET", "test-bucket"):
            backend = _mocked_backend()
            original = b"round-trip content"
            blob_hash = await backend.save_bytes(original, "application/octet-stream")
            retrieved = await backend.get_bytes(blob_hash)

    assert retrieved == original


def test_sha256_utility() -> None:
    """StorageBackend._sha256 should return 'sha256:' + the hex digest of the input."""
    data = b"test"
    expected = "sha256:" + hashlib.sha256(data).hexdigest()

    assert StorageBackend._sha256(data) == expected


def test_bucket_key_format() -> None:
    """_bucket_key should split the hex part into 'blobs/{first2}/{rest}' segments."""
    hex_part = "ab" * 32  # 64 hex chars — a valid SHA-256 digest
    blob_hash = "sha256:" + hex_part

    key = StorageBackend._bucket_key(blob_hash)

    assert key.startswith("blobs/")
    parts = key.split("/")
    # Expect exactly: ["blobs", "<first2>", "<remaining62>"]
    assert len(parts) == 3
    assert parts[1] == hex_part[:2]
    assert parts[2] == hex_part[2:]


async def test_get_presigned_get_returns_string() -> None:
    """get_presigned_get should return a non-empty string URL for an existing blob."""
    with mock_aws():
        with patch.object(settings, "MINIO_ENDPOINT", None), \
             patch.object(settings, "MINIO_ACCESS_KEY", "testing"), \
             patch.object(settings, "MINIO_SECRET_KEY", "testing"), \
             patch.object(settings, "MINIO_BUCKET", "test-bucket"):
            backend = _mocked_backend()
            blob_hash = await backend.save_bytes(b"presign me", "application/octet-stream")
            url = await backend.get_presigned_get(blob_hash)

    assert isinstance(url, str)
    assert len(url) > 0
