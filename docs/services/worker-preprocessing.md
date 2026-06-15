# ICD — Worker: Preprocessing

**Owner:** Nati / Yahav
**Last updated:** 2026-06-14

---

## What it is

Executes data ingestion and dataset commit steps: frame extraction and dataset commit. Runs any registered step with `queue = "preprocessing"`. Has no knowledge of CVAT, model inference, Docker containers, or any specific data domain — it just resolves a `step_type` from the registry and calls `step.run()`.

---

## Base Package

Built on `packages/worker-common` — the shared worker library that provides:

```
ConsumerLoop       XREADGROUP loop, XACK, orphan recovery, graceful shutdown
SessionFactory     async SQLAlchemy session factory (direct asyncpg, not through the API)
StorageBackend     MinIO/S3 abstraction (same interface as the API's get_storage())
WorkerRegistry     resolves step_type → Step instance (same registry as the API)
```

Every worker imports `worker-common` and specialises it with its own step implementations and stream name. No worker re-implements the consumer loop or DB session setup.

---

## Dependencies

```
PostgreSQL   job pickup and result write-back — direct asyncpg connection, not through the API
MinIO        read source blobs, write output blobs — direct S3/boto3 via StorageBackend
Redis        consume from preprocessing stream, orphan recovery
```

Workers do not go through the API for data access. The API is never in the data path for workers.

---

## Environment Variables

```
DATABASE_URL        postgresql+asyncpg://cvops:<password>@postgres:5432/cvops
MINIO_ENDPOINT      http://minio:9000
MINIO_ACCESS_KEY    <minio root user>
MINIO_SECRET_KEY    <minio root password>
REDIS_URL           redis://redis:6379/0
REDIS_STREAM        preprocessing
WORKER_TOKEN        <long-lived JWT for POST /internal/*>
WORKER_CONCURRENCY  4    (optional — parallel job slots, default 4)
```

---

## Steps It Runs

| step_type | queue | What it does |
|---|---|---|
| `step.extract_frames` | `preprocessing` | FFmpeg frame extraction, dedup, thumbnail generation |
| `step.commit_dataset` | `preprocessing` | Creates immutable commit + CAS branch advance |

All annotation work (`step.auto_label`, `step.human_review`, `step.export_yolo`) runs on the CVAT worker.

---

## How Blobs Are Written

Every byte the worker produces (frames, thumbnails) follows this exact pattern:

```
1. worker calls ctx.storage.save_bytes(raw_bytes, media_type)
   └──► StorageBackend computes sha256 hash of bytes
   └──► uploads to MinIO at path blobs/{hash[0:2]}/{hash[2:]}  (direct S3 PUT)
   └──► inserts blobs row in PG: {hash, storage_key, size_bytes, media_type}
   └──► returns blob_hash = "sha256:<hex>"

2. worker inserts samples row in PG:
   {blob_hash: "sha256:...", source_id, metadata}

MinIO holds the bytes. PG holds the reference (hash → storage key).
They are linked by the content hash.
```

---

## Job Pickup Flow

```
1. XREADGROUP on Redis Stream "preprocessing"
   → receives {job_id, step_type, queue}

2. SELECT * FROM runs WHERE id = job_id FOR UPDATE SKIP LOCKED
   → fetches full config + input_refs from PG

3. UPDATE runs SET status = 'running', started_at = now()

4. step = registry.resolve(step_type)
   await step.run(ctx, config, inputs)

5. On success:
   UPDATE runs SET status = 'succeeded', output_refs = {...}, finished_at = now()
   INSERT events row
   XACK message on Redis Stream
   POST /internal/runs/{workflow_run_id}/advance
     { step_run_id, output_refs }
     → executor resolves next DAG step and enqueues to appropriate stream

6. On failure:
   UPDATE runs SET status = 'failed', error = <message>, finished_at = now()
   INSERT events row
   XACK message (do not requeue — retry is user-triggered from dashboard)
```

---

## Auto-Chain

```
preprocessing completes step.extract_frames
    → POST /internal/runs/{id}/advance
    → executor enqueues step.auto_label to cvat stream

preprocessing completes step.commit_dataset
    → POST /internal/runs/{id}/advance
    → executor enqueues step.export_yolo to cvat stream
```

---

## Orphan Recovery

On startup and every 60 seconds, query for jobs that are pending in PG but not in Redis (handles Redis restart / message loss):

```sql
SELECT id FROM runs
WHERE status = 'pending'
  AND step_type IN ('step.extract_frames', 'step.commit_dataset')
  AND created_at < now() - interval '30 seconds'
```

Re-enqueue any found rows into the `preprocessing` Redis Stream.

---

## Scaling

```yaml
worker-preprocessing:
  deploy:
    replicas: 2   # SELECT FOR UPDATE SKIP LOCKED handles concurrency safely
```

---

## Reads From

| Source | What |
|---|---|
| PostgreSQL `runs` | Job config, input_refs |
| PostgreSQL `samples` | Sample metadata for commit step |
| PostgreSQL `annotation_revisions` | Revision IDs for commit step |
| MinIO | Source blobs (video files, uploaded images) |

---

## Writes To

| Destination | What |
|---|---|
| PostgreSQL `runs` | Status updates, output_refs, finished_at |
| PostgreSQL `samples` | New rows on ingest |
| PostgreSQL `blobs` | New content-addressed blob rows |
| PostgreSQL `commits` + `commit_samples` | Immutable dataset snapshots |
| PostgreSQL `events` | One row per status transition |
| MinIO | Frame JPEGs, thumbnail PNGs |
| API `POST /internal/runs/{id}/advance` | Workflow advance signal |

---

## Does NOT

```
✗ run model inference or auto-labeling
✗ talk to CVAT
✗ export datasets
✗ launch Docker containers
✗ hold the Docker socket
✗ proxy bytes through the API (writes directly to PG and MinIO)
✗ know what domain the data is in (CV, RF, audio — domain-agnostic)
```
