# ICD — Worker: CVAT

**Owner:** TBD
**Last updated:** 2026-06-14

---

## What it is

Owns all annotation work and dataset export. Runs auto-labeling (model inference), manages the human-in-the-loop gate via CVAT, pulls reviewed annotations back, exports the committed dataset to YOLO format, and chains to the next worker at each stage.

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
PostgreSQL   job pickup, labeling_jobs, annotation_revisions, blobs — direct asyncpg
MinIO        read images for auto-label, write export artifacts — direct S3/boto3 via StorageBackend
Redis        consume from cvat stream
CVAT         REST API — push tasks, upload images, pull completed annotations
API          POST /internal/runs/{id}/advance — signal executor to chain next steps
```

---

## Environment Variables

```
DATABASE_URL          postgresql+asyncpg://cvops:<password>@postgres:5432/cvops
MINIO_ENDPOINT        http://minio:9000
MINIO_ACCESS_KEY      <minio root user>
MINIO_SECRET_KEY      <minio root password>
REDIS_URL             redis://redis:6379/0
REDIS_STREAM          cvat
CVAT_URL              http://cvat:8080
CVAT_USERNAME         <cvat admin user>
CVAT_PASSWORD         <cvat admin password>
CVAT_WEBHOOK_SECRET   <shared secret for validating incoming webhooks>
WORKER_TOKEN          <long-lived JWT for POST /internal/*>
CVAT_POLL_INTERVAL    300    (seconds — fallback polling, default 5 min)
```

---

## Steps It Runs

| step_type | queue | What it does |
|---|---|---|
| `step.auto_label` | `cvat` | Model inference on data items, writes annotation_revisions with source='model' |
| `step.human_review` | `cvat` | Gate step — push to CVAT for human annotation, run → `waiting` |
| `step.export_yolo` | `cvat` | Materialise committed dataset to YOLO tar.gz, upload to MinIO |

---

## Auto-Label Flow (step.auto_label)

Triggered via auto-chain from the preprocessing worker after `step.extract_frames` completes.

```
1. Load data_item_ids from input_refs
2. For each data_item: fetch image blob from MinIO via presigned GET URL
3. Run inference (model config from step config, e.g. model_version_id or external endpoint)
4. Convert predictions → canonical annotation payload
5. INSERT annotation_revisions rows:
   { annotation_type: 'annotation.cv.detection',
     source: 'model',
     review_status: 'pending',
     data_item_id, payload }
6. UPDATE runs: { status: 'succeeded', output_refs: {annotation_revision_ids} }
7. INSERT events row
8. XACK Redis message
9. POST /internal/runs/{workflow_run_id}/advance
   { step_run_id, output_refs: {annotation_revision_ids} }
   → executor enqueues step.human_review to cvat stream
```

---

## Push Flow (step.human_review)

```
1. Load annotation_revision_ids from input_refs
2. Load data_items for those revisions
3. Call CVAT API:
   a. GET  /api/projects?name={cvops_project_name}  find or create CVAT project
   b. POST /api/tasks                               create task for this batch
   c. POST /api/tasks/{id}/data                     upload images
   d. POST /api/tasks/{id}/annotations              upload pre-labels (auto-label output)
4. INSERT labeling_jobs row:
   { status: 'pushed', cvat_task_id, cvat_job_ids,
     annotation_revision_ids_in, sample_count }
5. POST /api/webhooks on CVAT to register completion callback
6. Raise GateException({labeling_job_id})
   → executor sets run status = 'waiting'
   → dashboard shows "N jobs pending — Open in CVAT →"
```

---

## Pull Flow (on CVAT completion)

Triggered by webhook (primary) or polling fallback every `CVAT_POLL_INTERVAL` seconds.

The API receives `POST /internal/cvat/webhook`, validates `CVAT_WEBHOOK_SECRET`, and enqueues a sync message into the `cvat` Redis Stream. This worker picks it up.

```
1. Check all CVAT jobs in labeling_jobs.cvat_job_ids are completed
2. GET /api/tasks/{cvat_task_id}/annotations   download reviewed annotations
3. Convert CVAT geometry → canonical annotation payload (see Geometry Conversion)
4. INSERT annotation_revisions rows:
   { annotation_type: 'annotation.cv.detection',
     source: 'human',
     review_status: 'accepted',
     author_user_id: <mapped from CVAT user> }
5. UPDATE labeling_jobs:
   { status: 'completed', completed_at: now(),
     annotation_revision_ids_out: [...] }
6. UPDATE runs: { status: 'succeeded', output_refs: {annotation_revision_ids} }
7. INSERT events row
8. XACK Redis message
9. POST /internal/runs/{workflow_run_id}/advance
   { step_run_id, output_refs: {annotation_revision_ids} }
   → executor enqueues step.commit_dataset to preprocessing stream
```

Idempotent — if pull flow fires twice (webhook + poll race), `labeling_jobs.status == 'completed'` at step 1 short-circuits the second run.

---

## Export Flow (step.export_yolo)

Triggered via auto-chain from the preprocessing worker after `step.commit_dataset` completes.

```
1. Load commit_id from input_refs
2. SELECT commit_samples JOIN samples JOIN blobs WHERE commit_id = ...
3. For each sample: presigned GET URL → download image bytes from MinIO
4. Build YOLO directory layout:
   images/train/  images/val/  labels/train/  labels/val/
5. Write annotation_revisions as YOLO .txt label files
   (one file per image: class_id cx cy w h per line, normalised)
6. Tar the directory → ctx.storage.save_bytes(tar_bytes, "application/x-tar")
   → StorageBackend: sha256 hash, upload to MinIO, INSERT blobs row in PG
7. UPDATE runs: { status: 'succeeded', output_refs: {export_blob_hash} }
8. INSERT events row
9. XACK Redis message
10. POST /internal/runs/{workflow_run_id}/advance
    { step_run_id, output_refs: {export_blob_hash} }
    → executor enqueues step.train to training stream
```

---

## Auto-Chain Summary

```
preprocessing completes step.extract_frames
    → XADD cvat {step.auto_label}

cvat completes step.auto_label
    → XADD cvat {step.human_review}

cvat completes step.human_review (gate resolved via CVAT webhook)
    → XADD preprocessing {step.commit_dataset}

preprocessing completes step.commit_dataset
    → XADD cvat {step.export_yolo}

cvat completes step.export_yolo
    → XADD training {step.train}
```

All chaining goes through `POST /internal/runs/{id}/advance` → executor creates the child run row and does the XADD.

---

## Geometry Conversion

**Push — CVOps → CVAT:**
```
bbox [cx, cy, w, h] normalised →
  x1 = (cx - w/2) * W
  y1 = (cy - h/2) * H
  x2 = (cx + w/2) * W
  y2 = (cy + h/2) * H
  (W, H = data_item width, height from metadata)
```

**Pull — CVAT → CVOps:**
```
CVAT [x1, y1, x2, y2] absolute pixels →
  cx = (x1 + x2) / (2 * W)
  cy = (y1 + y2) / (2 * H)
  w  = (x2 - x1) / W
  h  = (y2 - y1) / H
```

---

## Reads From

| Source | What |
|---|---|
| PostgreSQL `runs` | Job config, input_refs |
| PostgreSQL `annotation_revisions` | Pre-labels to push to CVAT |
| PostgreSQL `data_items` | Image metadata (width, height) for geometry conversion |
| PostgreSQL `commits` + `commit_samples` | Sample membership for YOLO export |
| MinIO | Image bytes for auto-label inference and YOLO export |
| CVAT REST API | Completed annotation data |

---

## Writes To

| Destination | What |
|---|---|
| PostgreSQL `annotation_revisions` | Model-generated and human-reviewed revisions |
| PostgreSQL `labeling_jobs` | Push record, completion record |
| PostgreSQL `runs` | Status updates, output_refs |
| PostgreSQL `blobs` | Export tar.gz blob row |
| PostgreSQL `events` | Status transitions |
| MinIO | YOLO export tar.gz archive |
| CVAT REST API | Tasks, images, pre-labels |
| API `POST /internal/runs/{id}/advance` | Workflow advance signal |

---

## Does NOT

```
✗ extract frames from video
✗ create dataset commits
✗ launch Docker containers
✗ hold the Docker socket
✗ proxy bytes through the API (reads PG and MinIO directly)
```
