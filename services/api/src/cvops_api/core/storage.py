"""
StorageBackend — interface + S3-compatible implementation.

The concrete `S3Backend` targets any S3-compatible object store. CVOps ships
with Garage (https://garagehq.deuxfleurs.fr/) as the default; the same backend
works against AWS S3, MinIO, etc. by switching `S3_ENDPOINT` and `S3_REGION`.

All step implementations and routers call exactly these methods; never touch
boto3 directly.
"""

from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from cvops_api.config import settings

log = logging.getLogger(__name__)


class StorageBackend(ABC):
    @abstractmethod
    async def save_bytes(self, data: bytes, media_type: str) -> str:
        """Hash, dedup-check, upload. Returns 'sha256:<hex>'."""

    @abstractmethod
    async def get_presigned_get(self, blob_hash: str, ttl_seconds: int = 900) -> str:
        """Short-lived URL for client to download a blob directly."""

    @abstractmethod
    async def get_presigned_put(self, blob_hash: str, ttl_seconds: int = 3600) -> str:
        """Short-lived URL for client to upload a hash-keyed blob directly."""

    @abstractmethod
    async def get_presigned_put_for_upload(
        self, upload_id: str, ttl_seconds: int = 3600
    ) -> str:
        """Short-lived URL for client to upload to a transient `uploads/{id}` key.

        Used by the data-sources upload flow, where the SHA-256 of the payload
        is unknown until the client finishes uploading.
        """

    @abstractmethod
    async def promote_upload(
        self, upload_id: str, blob_hash: str
    ) -> tuple[int, str, str]:
        """Move a finished `uploads/{id}` object to its content-addressed
        `blobs/{hash}` location via a server-side copy (bytes never transit the
        API). Idempotent: skips the copy if the blob key already exists.

        Returns `(size_bytes, media_type, storage_key)` for the caller to record
        in the `blobs` table. The SHA-256 is taken on trust here and verified
        lazily by the step that first reads the bytes (e.g. extract_frames).
        """

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
        """blobs/{first2}/{rest} — avoids hot-spotting at scale."""
        hex_part = blob_hash.removeprefix("sha256:")
        return f"blobs/{hex_part[:2]}/{hex_part[2:]}"


class S3Backend(StorageBackend):
    def __init__(self) -> None:
        cfg = Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        )
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT,
            region_name=settings.S3_REGION,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            config=cfg,
        )
        # Presigned URLs must be signed against a browser-reachable host. When
        # S3_PUBLIC_ENDPOINT differs from the internal endpoint, use a dedicated
        # client for signing; otherwise reuse the internal one.
        public_endpoint = settings.S3_PUBLIC_ENDPOINT or settings.S3_ENDPOINT
        if public_endpoint == settings.S3_ENDPOINT:
            self._presign_client = self._client
        else:
            self._presign_client = boto3.client(
                "s3",
                endpoint_url=public_endpoint,
                region_name=settings.S3_REGION,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY,
                config=cfg,
            )
        self._bucket = settings.S3_BUCKET
        self._verify_bucket()
        self._ensure_cors()

    def _ensure_cors(self) -> None:
        """Allow browsers to PUT/GET directly against presigned URLs.

        Permissive (origin '*') because dev runs from varied origins (localhost,
        dev-VM hostnames, Vite). Best-effort: a backend that rejects the CORS API
        shouldn't take down the API — uploads just won't work cross-origin.
        """
        try:
            self._client.put_bucket_cors(
                Bucket=self._bucket,
                CORSConfiguration={
                    "CORSRules": [
                        {
                            "AllowedOrigins": ["*"],
                            "AllowedMethods": ["GET", "PUT", "HEAD"],
                            "AllowedHeaders": ["*"],
                            "ExposeHeaders": ["ETag"],
                            "MaxAgeSeconds": 3600,
                        }
                    ]
                },
            )
        except ClientError as exc:
            log.warning("Could not set bucket CORS on %r: %s", self._bucket, exc)

    def _verify_bucket(self) -> None:
        """Garage does not auto-create buckets. Fail fast at startup if missing."""
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError as exc:
            raise RuntimeError(
                f"S3 bucket {self._bucket!r} is not reachable at "
                f"{settings.S3_ENDPOINT!r}. Create it with "
                f"`garage bucket create {self._bucket}` and grant the access "
                f"key read+write before starting the API."
            ) from exc

    def _exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError:
            return False

    async def save_bytes(self, data: bytes, media_type: str) -> str:
        blob_hash = self._sha256(data)
        key = self._bucket_key(blob_hash)
        if not self._exists(key):
            self._client.put_object(
                Bucket=self._bucket, Key=key, Body=data, ContentType=media_type
            )
        return blob_hash

    async def get_presigned_get(self, blob_hash: str, ttl_seconds: int = 900) -> str:
        return str(
            self._presign_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": self._bucket_key(blob_hash)},
                ExpiresIn=ttl_seconds,
            )
        )

    async def get_presigned_put(self, blob_hash: str, ttl_seconds: int = 3600) -> str:
        return str(
            self._presign_client.generate_presigned_url(
                "put_object",
                Params={"Bucket": self._bucket, "Key": self._bucket_key(blob_hash)},
                ExpiresIn=ttl_seconds,
            )
        )

    async def get_presigned_put_for_upload(
        self, upload_id: str, ttl_seconds: int = 3600
    ) -> str:
        return str(
            self._presign_client.generate_presigned_url(
                "put_object",
                Params={"Bucket": self._bucket, "Key": f"uploads/{upload_id}"},
                ExpiresIn=ttl_seconds,
            )
        )

    async def promote_upload(
        self, upload_id: str, blob_hash: str
    ) -> tuple[int, str, str]:
        src_key = f"uploads/{upload_id}"
        dst_key = self._bucket_key(blob_hash)
        head = self._client.head_object(Bucket=self._bucket, Key=src_key)
        size_bytes = int(head["ContentLength"])
        media_type = head.get("ContentType") or "application/octet-stream"
        if not self._exists(dst_key):
            self._client.copy_object(
                Bucket=self._bucket,
                Key=dst_key,
                CopySource={"Bucket": self._bucket, "Key": src_key},
                ContentType=media_type,
                MetadataDirective="REPLACE",
            )
        return size_bytes, media_type, dst_key

    async def get_bytes(self, blob_hash: str) -> bytes:
        resp = self._client.get_object(
            Bucket=self._bucket, Key=self._bucket_key(blob_hash)
        )
        return resp["Body"].read()  # type: ignore[no-any-return]

    async def delete_blob(self, blob_hash: str) -> None:
        self._client.delete_object(
            Bucket=self._bucket, Key=self._bucket_key(blob_hash)
        )


_storage: StorageBackend | None = None


def get_storage() -> StorageBackend:
    """FastAPI dependency / module-level singleton."""
    global _storage
    if _storage is None:
        _storage = S3Backend()
    return _storage
