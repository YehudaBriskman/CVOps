# ICD — Data Layer

**Owner:** Yehuda
**Last updated:** 2026-06-11

---

## What it is

The data layer is not a microservice. It is two stores with a shared abstraction library:

```
PostgreSQL          facts — metadata, pointers, job state, audit log
MinIO / Garage / S3 bytes — images, frames, exports, model weights
```

Both are accessed **directly** by the API and workers. There is no separate "data service" sitting in front of them. The abstraction is a shared Python library (`packages/api`), not a network service.

---

## Why No Separate Data Service

A common microservices pattern is to add a dedicated service that owns the DB and exposes a REST API for it. Other services call it instead of talking to PG directly.

This pattern is **not used in CVOps**, and here is why:

```
Without data service:
  worker → PG (direct asyncpg)     one network hop, microseconds

With data service:
  worker → HTTP → data service → PG   two hops, milliseconds each

When frame extraction inserts 500 frames per video,
that difference is 500 × (milliseconds vs microseconds).
At scale this matters significantly.
```

More importantly: the abstraction you get from a data service is already provided by the SQLAlchemy model layer, which is a shared Python library — same benefit, no network overhead.

---

## The Two Stores

### PostgreSQL — Facts

Holds all metadata, state, and references. Never holds bytes.

```
Every piece of structured data lives here:
  projects, orgs, users
  data_items (references to blobs, not bytes)
  annotation_revisions (payload JSONB, not image data)
  commits, commit_samples, refs
  runs, events
  model_versions (reference to weights blob, not the weights)
  workflows, labeling_jobs, training_containers
  blobs (hash → storage_key index)
  type_schemas (registry)
```

Who connects:
```
API             reads + writes all tables
worker-preprocessing  reads runs, data_items, annotation_revisions
                      writes data_items, blobs, annotation_revisions,
                             commits, commit_samples, runs, events
worker-labeling       reads runs, annotation_revisions, data_items
                      writes annotation_revisions, labeling_jobs, runs, events
worker-training       reads runs, training_containers
                      writes model_versions, blobs, runs, events
```

Connection: `asyncpg` (async PostgreSQL driver) via SQLAlchemy 2.x async.

### MinIO / Garage / S3 — Bytes

Holds all binary content, content-addressed by SHA-256. Never holds metadata.

```
Every byte lives here:
  frame images         blobs/{hash[7:9]}/{hash[9:]}
  thumbnails           same path scheme
  export tar.gz        same path scheme
  model weights        same path scheme
  training logs        same path scheme
```

Who connects:
```
API                   presigned URL generation only (no byte reads/writes)
worker-preprocessing  read source blobs, write frames + thumbnails + exports
worker-training       read export dataset, write model weights + logs
Browser               direct upload/download via presigned URLs (no service in path)
```

Connection: `boto3` with `endpoint_url = MINIO_ENDPOINT`. Swapping MinIO for Garage or S3 is one config line — zero code changes.

---

## The StorageBackend Abstraction

Location: `packages/api/src/cvops_api/core/storage.py`

This is the data layer abstraction for bytes. All workers use it via `ctx.storage` — they never import boto3 directly.

```python
class StorageBackend:
    async def save_bytes(self, data: bytes, media_type: str) -> str:
        """
        Upload bytes to object storage.
        Returns blob_hash = "sha256:<hex>".
        Also inserts a blobs row in PG.
        Idempotent — identical bytes uploaded twice produce one blobs row.
        """

    async def get_bytes(self, blob_hash: str) -> bytes:
        """Download bytes by hash."""

    async def get_presigned_get(self, blob_hash: str, ttl_seconds: int) -> str:
        """Return a short-lived signed URL for direct browser download."""

    async def get_presigned_put(self, object_key: str, ttl_seconds: int) -> str:
        """Return a short-lived signed URL for direct browser upload."""

    async def delete_blob(self, blob_hash: str) -> None:
        """Hard-delete a blob (GC only — never called in normal flow)."""
```

`MinIOBackend` implements this against MinIO/Garage/S3. To swap storage providers: change `MINIO_ENDPOINT` and credentials. Nothing else changes.

---

## The Blobs Table — The Link Between Stores

Every byte written to object storage gets a corresponding row in PostgreSQL:

```sql
blobs
  hash            TEXT PRIMARY KEY   -- "sha256:<64-hex>"  ← the link
  storage_backend TEXT               -- "minio" | "s3" | "gcs"
  storage_key     TEXT               -- "blobs/ab/cdef..."  ← where in MinIO
  size_bytes      BIGINT
  media_type      TEXT
  created_at      TIMESTAMPTZ
```

This table is the index. Given a `blob_hash`, you can find the bytes. Given a `data_item`, you find its `blob_hash`, then find the bytes. The API uses this to generate presigned URLs without ever fetching the bytes itself.

---

## The SQLAlchemy Models — The PG Abstraction

Location: `packages/api/src/cvops_api/db/models/`

These are the data layer abstraction for PostgreSQL. Workers import them from `packages/api` (shared library).

```
blobs.py           Blob model
auth.py            Org, User, Membership, RefreshToken
projects.py        Project, DataSource
data_items.py      DataItem  (renamed from Sample — domain-agnostic)
ontologies.py      Ontology, LabelClass
annotations.py     AnnotationRevision
versioning.py      Dataset, Commit, CommitSample, Ref, ProjectDatasetLink
workflows.py       Workflow
runs.py            Run
models.py          ModelVersion, TrainingContainer
labeling.py        LabelingJob
```

Workers never write raw SQL (except the `FOR UPDATE SKIP LOCKED` job pickup query). Everything else goes through SQLAlchemy models. This is the ORM layer acting as the repository pattern.

---

## Security

Workers have direct DB credentials. Scope is enforced at the PostgreSQL role level:

```
cvops_api_role       full read/write — used by API
cvops_worker_role    read runs, write runs + domain tables
                     cannot read: users, refresh_tokens, orgs settings
                     cannot delete: commits, annotation_revisions (append-only enforced by PG trigger)
```

This means a compromised worker cannot read user passwords or delete versioned history even if it tries.
