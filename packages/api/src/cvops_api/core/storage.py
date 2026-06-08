"""
StorageBackend — interface + MinIO implementation (P1/P4/P9).
All step implementations call exactly these methods; never touch boto3 directly.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod

import boto3
from botocore.config import Config

from cvops_api.config import settings


class StorageBackend(ABC):
    @abstractmethod
    async def save_bytes(self, data: bytes, media_type: str) -> str:
        """Hash, dedup-check, upload. Returns 'sha256:<hex>'."""

    @abstractmethod
    async def get_presigned_get(self, blob_hash: str, ttl_seconds: int = 900) -> str:
        """Short-lived URL for client to download a blob directly (P9)."""

    @abstractmethod
    async def get_presigned_put(self, blob_hash: str, ttl_seconds: int = 3600) -> str:
        """Short-lived URL for client to upload a blob directly (P9)."""

    @abstractmethod
    async def get_bytes(self, blob_hash: str) -> bytes:
        """For workers that need to read bytes locally."""

    @abstractmethod
    async def delete_blob(self, blob_hash: str) -> None:
        """Used only by the audited GC sweep."""

    @staticmethod
    def _sha256(data: bytes) -> str:
        return "sha256:" + hashlib.sha256(data).hexdigest()

    @staticmethod
    def _bucket_key(blob_hash: str) -> str:
        """blobs/{first2}/{rest} — avoids hot-spotting in MinIO at scale."""
        hex_part = blob_hash.removeprefix("sha256:")
        return f"blobs/{hex_part[:2]}/{hex_part[2:]}"


class MinIOBackend(StorageBackend):
    def __init__(self) -> None:
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.MINIO_ENDPOINT,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
            config=Config(signature_version="s3v4"),
        )
        self._bucket = settings.MINIO_BUCKET
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except Exception:
            self._client.create_bucket(Bucket=self._bucket)

    def _exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:
            return False

    async def save_bytes(self, data: bytes, media_type: str) -> str:
        blob_hash = self._sha256(data)
        key = self._bucket_key(blob_hash)
        if not self._exists(key):
            self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=media_type)
        return blob_hash

    async def get_presigned_get(self, blob_hash: str, ttl_seconds: int = 900) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": self._bucket_key(blob_hash)},
            ExpiresIn=ttl_seconds,
        )

    async def get_presigned_put(self, blob_hash: str, ttl_seconds: int = 3600) -> str:
        return self._client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self._bucket, "Key": self._bucket_key(blob_hash)},
            ExpiresIn=ttl_seconds,
        )

    async def get_bytes(self, blob_hash: str) -> bytes:
        resp = self._client.get_object(Bucket=self._bucket, Key=self._bucket_key(blob_hash))
        return resp["Body"].read()  # type: ignore[no-any-return]

    async def delete_blob(self, blob_hash: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=self._bucket_key(blob_hash))


_storage: StorageBackend | None = None


def get_storage() -> StorageBackend:
    """FastAPI dependency / module-level singleton."""
    global _storage
    if _storage is None:
        _storage = MinIOBackend()
    return _storage
