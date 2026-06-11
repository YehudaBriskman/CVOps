# ICD — Worker: Preprocessing

**Owner:** Nati / Yahav
**Last updated:** 2026-06-11

---

## What it is

Executes all data transformation steps: frame extraction, auto-labeling, dataset commit, and export. Runs any registered step with `queue = "preprocessing"`. Has no knowledge of CVAT, Docker containers, or any specific data domain — it just resolves a `step_type` from the registry and calls `step.run()`.

---

## Dependencies

```
PostgreSQL   job pickup and result write-back — direct asyncpg connection, not through the API
MinIO        read source blobs, write output blobs — direct S3/boto3 calls, not through the API
Redis        consume from preprocessing stream, orphan recovery
```

**Important:** this worker connects to both PostgreSQL and MinIO directly — it does not go through the API for either. The API is never in the data path for workers. The `StorageBackend` abstraction (`ctx.storage`) wraps the MinIO boto3 calls so the same worker code works against MinIO, Garage, or AWS S3 with a config change only.

---

## Environment Variables

```
DATABASE_URL        postgresql+asyncpg://cvops:<password>@postgres:5432/cvops
MINIO_ENDPOINT      http://minio:9000
MINIO_ACCESS_KEY    <minio root user>
MINIO_SECRET_KEY    <minio root password>
REDIS_URL           redis://redis:6379/0
REDIS_STREAM        preprocessing
WORKER_TOKEN        <long-lived JWT>
WORKER_CONCURRENCY  4    (optional — parallel job slots, default 4)
```

---

## Steps It Runs

| step_type | What it does |
|---|---|
| `step.extract_frames` | FFmpeg frame extraction, dedup, thumbnail generation |
| `step.auto_label` | Model inference on data items, writes annotation_revisions |
| `step.commit_dataset` | Creates immutable commit + CAS branch advance |
| `step.export_yolo` | Materialises commit to YOLO tar.gz archive |

---

## How Blobs Are Written

Every byte the worker produces (frames, thumbnails, exports) follows this exact pattern:

```
1. worker calls ctx.storage.save_bytes(raw_bytes, media_type)
   └──► StorageBackend computes sha256 hash of bytes
   └──► uploads to MinIO at path blobs/{hash[7:9]}/{hash[9:]}  (direct S3 PUT)
   └──► inserts blobs row in PG: {hash, storage_key, size_bytes, media_type}
   └──► returns blob_hash = "sha256:<hex>"

2. worker inserts data_items row in PG:
   {blob_hash: "sha256:...", source_id, item_type, metadata}

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

6. On failure:
   UPDATE runs SET status = 'failed', error = <message>, finished_at = now()
   INSERT events row
   XACK message (do not requeue — retry is user-triggered from dashboard)
```

---

## Orphan Recovery

On startup and every 60 seconds, query for jobs that are pending in PG but not in Redis (handles Redis restart / message loss):

```sql
SELECT id FROM runs
WHERE status = 'pending'
  AND step_type IN (
    'step.extract_frames', 'step.auto_label',
    'step.commit_dataset', 'step.export_yolo'
  )
  AND created_at < now() - interval '30 seconds'
```

Re-enqueue any found rows into the `preprocessing` Redis Stream.

---

## Scaling

```yaml
worker-preprocessing:
  deploy:
    replicas: 2   # increase for more parallelism
                  # SELECT FOR UPDATE SKIP LOCKED handles concurrency safely
```

---

## Reads From

| Source | What |
|---|---|
| PostgreSQL `runs` | Job config, input_refs |
| PostgreSQL `data_items` | Item metadata for auto_label and commit steps |
| PostgreSQL `annotation_revisions` | Existing revisions for commit step |
| MinIO | Source blobs (video files, uploaded images, RF captures) |

---

## Writes To

| Destination | What |
|---|---|
| PostgreSQL `runs` | Status updates, output_refs, finished_at |
| PostgreSQL `data_items` | New rows on ingest |
| PostgreSQL `blobs` | New content-addressed blob rows |
| PostgreSQL `annotation_revisions` | Model-generated annotations |
| PostgreSQL `commits` + `commit_samples` | Immutable dataset snapshots |
| PostgreSQL `events` | One row per status transition |
| MinIO | Frame JPEGs, thumbnail PNGs, export tar.gz archives |

---

## Does NOT

```
✗ talk to CVAT
✗ launch Docker containers
✗ hold the Docker socket
✗ call the API over HTTP (writes directly to PG and MinIO)
✗ know what domain the data is in (CV, RF, audio — domain-agnostic)
```
