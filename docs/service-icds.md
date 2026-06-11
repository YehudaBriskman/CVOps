# CVOps — Service ICDs

**Status:** Locked. Every service boundary, environment contract, and communication channel is defined here.
**Last updated:** 2026-06-11

Each section covers one service: what it is, what it needs to start, what it reads, what it writes, and — critically — what it does NOT do. The "does not" list is as important as the rest. It defines the hard boundary between services.

---

## Table of Contents

1. [Shared Concepts](#1-shared-concepts)
2. [API](#2-api)
3. [Worker — Preprocessing](#3-worker--preprocessing)
4. [Worker — Labeling](#4-worker--labeling)
5. [Worker — Training](#5-worker--training)
6. [Frontend](#6-frontend)
7. [Step Contract (shared library)](#7-step-contract-shared-library)
8. [Redis Stream Contract](#8-redis-stream-contract)
9. [Communication Map](#9-communication-map)

---

## 1. Shared Concepts

### 1.1 Job Lifecycle

Every unit of async work is a row in the `runs` table:

```
pending   → worker picks it up   → running
running   → step completes       → succeeded
running   → step raises gate     → waiting   (human review gate)
waiting   → gate resolved        → running   (resumes from next step)
running   → step raises error    → failed
failed    → user retries         → running   (attempt + 1)
```

The `runs` table is the single source of truth for job state. Redis Streams carry only a wake-up signal — they never hold job state.

### 1.2 Worker Token

Workers authenticate to the API using a long-lived JWT (`WORKER_TOKEN` env var). The API validates this token on `/internal/*` endpoints. Workers never use user credentials.

### 1.3 Presigned URL Pattern

No service proxies bytes. The API issues presigned URLs. Clients and workers fetch/upload bytes directly from MinIO.

```
wants bytes → asks API for presigned URL → API returns URL → goes directly to MinIO
```

---

## 2. API

### What it is
The orchestration layer. Handles all HTTP from the browser, manages auth, owns all CRUD, runs the workflow executor (Phase 1: in-process, Phase 2: dispatches to workers), and issues presigned URLs for MinIO access.

### Dependencies (must be healthy before API starts)
```
PostgreSQL   — all reads and writes
MinIO        — presigned URL generation only (no byte proxying)
Redis        — locks, cache, SSE pub/sub, job enqueue (Phase 2)
```

### Environment Variables
```
DATABASE_URL        postgresql+asyncpg://cvops:<password>@postgres:5432/cvops
MINIO_ENDPOINT      http://minio:9000
MINIO_ACCESS_KEY    <minio root user>
MINIO_SECRET_KEY    <minio root password>
MINIO_BUCKET        cvops-blobs
REDIS_URL           redis://redis:6379/0
JWT_SECRET          <min 32 chars, random>
WORKER_TOKEN        <long-lived JWT for worker auth>
```

### Reads From
| Source | What |
|---|---|
| PostgreSQL | All tables — auth, projects, data_items, commits, runs, events, etc. |
| Redis | Distributed locks (branch CAS), short-lived cache (presigned URL metadata) |

### Writes To
| Destination | What |
|---|---|
| PostgreSQL | All domain tables. Every mutation emits an `events` row. |
| Redis Streams | `preprocessing`, `labeling`, `training` — thin wake-up messages when a run is created (Phase 2) |
| Redis pub/sub | `runs:{run_id}` channel — publishes event payloads for SSE stream delivery |

### Exposes
```
REST API        /api/*          — all endpoints (see Section 12 of MASTER_PLAN)
SSE stream      /api/runs/{id}/events/stream
Webhook         /internal/cvat/webhook
Health          /internal/health
```

### Does NOT
```
✗ proxy image bytes or model weights — issues presigned URLs instead
✗ execute long-running step logic in the request thread
✗ hold the Docker socket
✗ talk to CVAT directly
✗ know what a "frame" or "RF capture" is — domain-agnostic at this layer
```

---

## 3. Worker — Preprocessing

### What it is
Executes all data transformation steps: frame extraction, auto-labeling, dataset commit, and export. Runs registered steps whose `queue = "preprocessing"`. Knows nothing about CVAT or Docker containers.

### Dependencies
```
PostgreSQL   — job pickup and result write-back
MinIO        — read source blobs, write output blobs (frames, thumbnails, exports)
Redis        — consume from preprocessing stream, orphan recovery
```

### Environment Variables
```
DATABASE_URL        postgresql+asyncpg://cvops:<password>@postgres:5432/cvops
MINIO_ENDPOINT      http://minio:9000
MINIO_ACCESS_KEY    <minio root user>
MINIO_SECRET_KEY    <minio root password>
REDIS_URL           redis://redis:6379/0
REDIS_STREAM        preprocessing
WORKER_TOKEN        <long-lived JWT>
WORKER_CONCURRENCY  4   (optional, default 4 — number of parallel jobs)
```

### Steps It Runs
```
step.extract_frames    — FFmpeg, dedup, thumbnail generation
step.auto_label        — model inference, annotation_revisions insert
step.commit_dataset    — immutable commit + CAS branch advance
step.export_yolo       — materialise commit to YOLO tar.gz
```

### Job Pickup Flow
```
1. XREADGROUP on Redis Stream "preprocessing"
   → receives {job_id, step_type, queue}

2. SELECT runs WHERE id = job_id FOR UPDATE SKIP LOCKED
   → fetches full config + input_refs

3. UPDATE runs SET status = 'running', started_at = now()

4. registry.resolve(step_type).run(ctx, config, inputs)

5. On success:
   UPDATE runs SET status = 'succeeded', output_refs = {...}, finished_at = now()
   XACK Redis Stream message

6. On failure:
   UPDATE runs SET status = 'failed', error = <message>, finished_at = now()
   XACK Redis Stream message (do not requeue — retry is user-driven)

7. Emit events row for every status transition
```

### Orphan Recovery
On startup and every 60 seconds:
```sql
SELECT id FROM runs
WHERE status = 'pending'
  AND step_type IN ('step.extract_frames', 'step.auto_label',
                    'step.commit_dataset', 'step.export_yolo')
  AND created_at < now() - interval '30 seconds'
```
Re-enqueue any found rows into the `preprocessing` Redis Stream.

### Reads From
| Source | What |
|---|---|
| PostgreSQL `runs` | Job config, input_refs |
| PostgreSQL `data_items` | Sample metadata for auto_label and commit steps |
| PostgreSQL `annotation_revisions` | Existing revisions for commit step |
| MinIO | Source blobs (video files, uploaded images) |

### Writes To
| Destination | What |
|---|---|
| PostgreSQL `runs` | Status updates, output_refs |
| PostgreSQL `data_items` | New rows on ingest |
| PostgreSQL `blobs` | New content-addressed blob rows |
| PostgreSQL `annotation_revisions` | Model-generated annotations |
| PostgreSQL `commits` + `commit_samples` | Immutable dataset snapshots |
| PostgreSQL `events` | One row per status transition |
| MinIO | Frame JPEGs, thumbnail PNGs, export tar.gz archives |

### Does NOT
```
✗ talk to CVAT
✗ launch Docker containers
✗ hold the Docker socket
✗ call the API over HTTP (writes directly to PG and MinIO)
```

---

## 4. Worker — Labeling

### What it is
Manages the human-in-the-loop gate. Pushes annotation tasks to CVAT, receives completion signals (webhook from API or polling), pulls reviewed annotations back, writes new annotation revisions, and resumes the paused workflow run.

### Dependencies
```
PostgreSQL   — job pickup, labeling_jobs table, annotation_revisions write-back
Redis        — consume from labeling stream
CVAT         — REST API (push tasks, upload images, pull annotations)
```

### Environment Variables
```
DATABASE_URL        postgresql+asyncpg://cvops:<password>@postgres:5432/cvops
REDIS_URL           redis://redis:6379/0
REDIS_STREAM        labeling
CVAT_URL            http://cvat:8080
CVAT_USERNAME       <cvat admin user>
CVAT_PASSWORD       <cvat admin password>
CVAT_WEBHOOK_SECRET <shared secret for webhook validation>
WORKER_TOKEN        <long-lived JWT>
CVAT_POLL_INTERVAL  300   (seconds, default 5 min — fallback polling interval)
```

### Steps It Runs
```
step.human_review    — CVAT push (gate: raises GateException → run → waiting)
```

### Push Flow (when step.human_review fires)
```
1. Load annotation_revision_ids from input_refs
2. Load data_items rows for those revisions
3. Call CVAT API:
   a. GET /api/projects?name={cvops_project_name}  — find or create CVAT project
   b. POST /api/tasks                               — create task for this batch
   c. POST /api/tasks/{id}/data                     — upload images
   d. POST /api/tasks/{id}/annotations              — upload pre-labels
4. INSERT labeling_jobs row:
   {status: 'pushed', cvat_task_id, cvat_job_ids, annotation_revision_ids_in}
5. POST /api/webhooks on CVAT — register completion webhook
6. Raise GateException({labeling_job_id})
   → executor sets run status = 'waiting'
```

### Pull Flow (on CVAT completion)

Triggered by webhook (primary) or polling fallback:
```
1. Verify all CVAT jobs in labeling_jobs.cvat_job_ids are completed
2. GET /api/tasks/{cvat_task_id}/annotations  — download reviewed annotations
3. Convert CVAT geometry → canonical annotation payload
4. INSERT annotation_revisions rows:
   {source: 'human', review_status: 'accepted', author_user_id: <mapped>}
5. UPDATE labeling_jobs:
   {status: 'completed', annotation_revision_ids_out: [...]}
6. POST /api/runs/{workflow_run_id}/gates/{step_id}/resolve
   — API resumes the workflow
```

Webhook is delivered to `POST /internal/cvat/webhook` on the API, which forwards the signal to this worker via the `labeling` Redis Stream.

### Reads From
| Source | What |
|---|---|
| PostgreSQL `runs` | Job config, input_refs |
| PostgreSQL `annotation_revisions` | Pre-label data to push to CVAT |
| PostgreSQL `data_items` | Image metadata for CVAT upload |
| CVAT REST API | Completed annotation data |

### Writes To
| Destination | What |
|---|---|
| PostgreSQL `labeling_jobs` | Push record, completion record |
| PostgreSQL `annotation_revisions` | Human-reviewed revisions |
| PostgreSQL `runs` | Status updates |
| PostgreSQL `events` | Status transitions |
| CVAT REST API | Tasks, images, pre-labels |
| API (`POST /runs/{id}/gates/{step_id}/resolve`) | Resume signal |

### Does NOT
```
✗ touch MinIO directly (images go to CVAT, not MinIO, during this step)
✗ launch Docker containers
✗ run preprocessing steps
✗ know what YOLO is
```

---

## 5. Worker — Training

### What it is
Launches user-supplied Docker training containers, monitors them, reads results, and writes model_version records. The only service with Docker socket access.

### Dependencies
```
PostgreSQL   — job pickup, training_containers ICD config, model_versions write
MinIO        — download export dataset, upload model weights
Redis        — consume from training stream
Docker       — socket to launch user containers
```

### Environment Variables
```
DATABASE_URL        postgresql+asyncpg://cvops:<password>@postgres:5432/cvops
MINIO_ENDPOINT      http://minio:9000
MINIO_ACCESS_KEY    <minio root user>
MINIO_SECRET_KEY    <minio root password>
REDIS_URL           redis://redis:6379/0
REDIS_STREAM        training
WORKER_TOKEN        <long-lived JWT>
DOCKER_TIMEOUT      7200   (seconds, default 2h — max container run time)
```

### Steps It Runs
```
step.train       — ICD-driven Docker container dispatch
step.evaluate    — model evaluation against a commit (Phase 3)
```

### Training Flow
```
1. Load runs row → config: {training_container_id, hyperparams}
2. Load training_containers row → icd_config
3. Download export tar.gz from MinIO → extract to {tmpdir}/dataset/
4. Create {tmpdir}/output/
5. Build env dict from icd_config.inputs + hyperparams
6. Build volume mounts:
     {tmpdir}/dataset → icd_config.volume_mount  (read-only)
     {tmpdir}/output  → /output                  (read-write)
7. docker run:
     image:       training_containers.image
     environment: env dict
     volumes:     above
     detach:      True (Phase 2 — stream logs)
     remove:      True
8. Poll container until exit (every 5s)
   Stream logs to runs.logs_blob_hash (upload to MinIO as they arrive)
9. On exit code 0:
   a. Read {tmpdir}/output/{metrics_file_path} → parse JSON metrics
   b. Read mlflow_run_id from metrics JSON if present
   c. Tar weights directory → upload to MinIO → weights_blob_hash
   d. INSERT model_versions:
        {blob_hash: weights_blob_hash,
         trained_on_commit_id: <from workflow run context>,
         training_container_id,
         hyperparams, metrics,
         mlflow_run_id: metrics.get('mlflow_run_id'),
         seed: hyperparams.get('seed')}
   e. UPDATE runs: {status: 'succeeded', output_refs: {model_version_id}}
10. On non-zero exit:
    UPDATE runs: {status: 'failed', error: last 500 chars of logs}
```

### MLflow Reference

If the user's training container reports to MLflow, it should write the run ID into `metrics.json`:
```json
{
  "mAP50": 0.87,
  "loss": 0.043,
  "mlflow_run_id": "abc123def456"
}
```
This worker reads it and stores it on `model_versions.mlflow_run_id`. No other MLflow coupling exists in CVOps — the dashboard shows a "View in MLflow →" link using this ID.

### Reads From
| Source | What |
|---|---|
| PostgreSQL `runs` | Job config, input_refs |
| PostgreSQL `training_containers` | ICD config (env var mapping, volume mount, output paths) |
| MinIO | Export dataset tar.gz |

### Writes To
| Destination | What |
|---|---|
| PostgreSQL `model_versions` | Trained model record |
| PostgreSQL `runs` | Status, output_refs, logs_blob_hash |
| PostgreSQL `blobs` | Weights blob, logs blob |
| PostgreSQL `events` | Status transitions |
| MinIO | Model weights tar.gz, streaming training logs |
| Docker daemon | Container launch and monitoring |

### Does NOT
```
✗ talk to CVAT
✗ process or transform data items
✗ implement any training logic (that lives in the user's container)
✗ know what model architecture is being trained
```

---

## 6. Frontend

### What it is
React SPA served by Nginx. Interacts with two backends: the API (all business logic) and MinIO (file bytes via presigned URLs). Never talks to workers, PostgreSQL, or Redis directly.

### Dependencies at runtime
```
API     — REST + SSE
MinIO   — presigned URLs for file upload and download
```

### Environment Variables (build-time, injected via Vite)
```
VITE_API_BASE_URL    /api   (Nginx proxies — no CORS issues)
```

### Communicates With

**API — REST:**
```
All business logic: auth, projects, workflows, runs, datasets,
models, training containers, registry, samples browser.
Base URL: /api (proxied by Nginx to api:8000)
Auth: Bearer <access_token> on every request
Refresh: automatic via axios interceptor on 401
```

**API — SSE:**
```
GET /api/runs/{id}/events/stream
Opens a persistent connection.
API pushes event JSON on every run status transition.
Frontend updates run view in real time without polling.
Closes when run reaches terminal state.
```

**MinIO — presigned URLs:**
```
UPLOAD:
  1. POST /api/projects/{id}/data-sources  → API returns presigned PUT URL
  2. Frontend PUTs file bytes directly to MinIO URL
  3. POST /api/data-sources/{id}/confirm-upload  → API verifies + inserts blob

DOWNLOAD (images, thumbnails, weights):
  1. GET /api/samples/{id}/thumbnail-url   → API returns presigned GET URL
  2. Frontend fetches bytes directly from MinIO URL
  Presigned URLs are short-lived (15 min read, 1 hr for weights)
```

### Does NOT
```
✗ talk to PostgreSQL
✗ talk to Redis
✗ talk to workers
✗ talk to CVAT directly (API handles all CVAT interaction)
✗ store auth tokens anywhere other than localStorage
```

---

## 7. Step Contract (shared library)

`packages/steps` is a Python library imported by all three workers. It is not a running service. It defines every step implementation and registers them in the registry.

### Step Base Class

```python
# packages/api/src/cvops_api/engine/step.py

@dataclass
class StepContext:
    session:    AsyncSession      # DB session
    storage:    StorageBackend    # MinIO/S3 abstraction
    project_id: str               # UUID
    run_id:     str               # UUID of this step's runs row
    actor_id:   str               # UUID of triggering user
    audit:      Callable          # bound emit_event coroutine

class GateException(Exception):
    """Raised by gate steps to pause the workflow run."""
    def __init__(self, gate_data: dict):
        self.gate_data = gate_data   # stored in runs.output_refs

class Step:
    type_key:     str   = ""     # e.g. "step.extract_frames"
    queue:        str   = ""     # "preprocessing" | "labeling" | "training"
    config_schema: dict = {}     # JSON Schema — validated before run starts
    is_gate:      bool  = False  # True → raises GateException to pause workflow

    async def run(
        self,
        ctx:     StepContext,
        config:  dict,           # validated against config_schema
        inputs:  dict,           # resolved artifact refs
    ) -> dict:                   # output artifact refs
        raise NotImplementedError

    def idempotency_key(self, config: dict, inputs: dict) -> str:
        # SHA-256 of (type_key + config + inputs)
        # executor skips execution if a succeeded run with same key exists
        ...
```

### Step Input/Output Contract

| Step | Inputs | Outputs |
|---|---|---|
| `step.extract_frames` | `{source_id: uuid}` | `{data_item_ids: [uuid, ...]}` |
| `step.auto_label` | `{data_item_ids: [uuid, ...]}` | `{annotation_revision_ids: [uuid, ...]}` |
| `step.human_review` | `{annotation_revision_ids: [uuid, ...]}` | `{annotation_revision_ids: [uuid, ...]}` |
| `step.commit_dataset` | `{data_item_ids: [uuid, ...], annotation_revision_ids: [uuid, ...]}` | `{commit_id: uuid, ref_id: uuid}` |
| `step.export_yolo` | `{commit_id: uuid}` | `{export_blob_hash: "sha256:..."}` |
| `step.train` | `{export_blob_hash: "sha256:..."}` | `{model_version_id: uuid}` |

### Registration

```python
# packages/steps/src/cvops_steps/__init__.py

from cvops_api.core.registry import registry
from .extract_frames import ExtractFramesStep
from .auto_label     import AutoLabelStep
from .human_review   import HumanReviewStep
from .commit_dataset import CommitDatasetStep
from .export_yolo    import ExportYoloStep
from .train          import TrainStep

def register_all():
    for step in [
        ExtractFramesStep(),
        AutoLabelStep(),
        HumanReviewStep(),
        CommitDatasetStep(),
        ExportYoloStep(),
        TrainStep(),
    ]:
        registry.register(step)
        # also upserts type_schemas row in PG at API startup
```

---

## 8. Redis Stream Contract

### Stream Names
```
preprocessing    consumed by worker-preprocessing
labeling         consumed by worker-labeling
training         consumed by worker-training
```

### Message Format (all streams, same shape)
```json
{
  "job_id":    "<uuid — the runs row id>",
  "step_type": "<registered type_key e.g. step.extract_frames>",
  "queue":     "<stream name>"
}
```

**That is the entire message.** Workers fetch all other information (config, inputs, project_id) from the `runs` row in PostgreSQL using `job_id`.

### Producer (API)

Phase 1 — no Redis write. Executor runs in-process via `BackgroundTasks`.

Phase 2 — API enqueues after creating the `runs` row:
```python
await redis.xadd(
    step.queue,                            # stream name
    {"job_id": run_id,
     "step_type": step.type_key,
     "queue": step.queue}
)
```

### Consumer (Workers)

Each worker uses a consumer group named after its service:
```python
# on startup — create consumer group if not exists
await redis.xgroup_create(stream_name, group_name="worker-preprocessing",
                           id="$", mkstream=True)

# main loop
messages = await redis.xreadgroup(
    groupname="worker-preprocessing",
    consumername=f"worker-{hostname}",
    streams={stream_name: ">"},   # ">" = new messages only
    count=1,
    block=5000                    # block 5s if empty
)

# after job completes:
await redis.xack(stream_name, "worker-preprocessing", message_id)
```

### Orphan Recovery Channel

Separate from the stream. Workers periodically query PG for orphaned pending jobs and re-enqueue them. This is the durability fallback in case Redis loses a message.

---

## 9. Communication Map

```
                      BROWSER
                         │
           ┌─────────────┼──────────────┐
           │ REST/SSE    │              │ presigned URLs
           ▼             │              ▼
         NGINX           │            MinIO
           │             │         (bytes only)
     /api/ │   / │       │              ▲
           ▼   ▼         │              │
         API  Frontend   │    ┌─────────┤
           │             │    │         │
           │ write runs  │    │  write  │
           │ + XADD      │    │  blobs  │
           ▼             │    │         │
         Redis           │    │         │
         Streams         │    │         │
           │             │    │         │
     ┌─────┼─────┐       │    │         │
     ▼     ▼     ▼       │    │         │
  worker worker worker   │    │         │
  prep  label train      │    │         │
     │     │     │       │    │         │
     │     │     └───────┼────┘         │
     │     │             │ write model  │
     │     │             │ weights      │
     └─────┴─────────────┘              │
           │ write data_items,          │
           │ annotation_revisions,      │
           │ commits, runs, events      │
           ▼                            │
       PostgreSQL ─────────────────────►│
       (facts, job state)      presigned URL lookups

  worker-label ──► CVAT (push tasks, pull annotations)
  worker-train ──► Docker daemon (launch training containers)
```

### Who talks to what — summary table

| From | To | How | What |
|---|---|---|---|
| Browser | API | HTTP REST | auth, CRUD, workflow runs |
| Browser | API | SSE | live run events |
| Browser | MinIO | HTTP (presigned) | upload/download bytes |
| API | PostgreSQL | SQLAlchemy async | all reads and writes |
| API | Redis | ioredis | locks, cache, XADD to streams |
| API | MinIO | boto3 | presigned URL generation only |
| worker-preprocessing | PostgreSQL | asyncpg | job pickup + result write |
| worker-preprocessing | MinIO | boto3 | read source blobs, write outputs |
| worker-preprocessing | Redis | ioredis | XREADGROUP, XACK |
| worker-labeling | PostgreSQL | asyncpg | job pickup + revision write |
| worker-labeling | Redis | ioredis | XREADGROUP, XACK |
| worker-labeling | CVAT | httpx REST | push tasks, pull annotations |
| worker-labeling | API | httpx REST | `POST /runs/{id}/gates/{step}/resolve` |
| worker-training | PostgreSQL | asyncpg | job pickup + model_version write |
| worker-training | MinIO | boto3 | read dataset, write weights |
| worker-training | Redis | ioredis | XREADGROUP, XACK |
| worker-training | Docker daemon | docker-py | container launch + monitor |
