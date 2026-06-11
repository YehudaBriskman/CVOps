# ICD — Worker: Labeling

**Owner:** TBD
**Last updated:** 2026-06-11

---

## What it is

Manages the human-in-the-loop gate. Pushes annotation tasks to CVAT, receives completion signals (via API webhook or polling fallback), pulls reviewed annotations back, writes new annotation revisions to PostgreSQL, and resumes the paused workflow run.

---

## Dependencies

```
PostgreSQL   job pickup, labeling_jobs table, annotation_revisions write-back
Redis        consume from labeling stream
CVAT         REST API — push tasks, upload images, pull completed annotations
API          POST /runs/{id}/gates/{step_id}/resolve — to resume paused workflow
```

---

## Environment Variables

```
DATABASE_URL          postgresql+asyncpg://cvops:<password>@postgres:5432/cvops
REDIS_URL             redis://redis:6379/0
REDIS_STREAM          labeling
CVAT_URL              http://cvat:8080
CVAT_USERNAME         <cvat admin user>
CVAT_PASSWORD         <cvat admin password>
CVAT_WEBHOOK_SECRET   <shared secret for validating incoming webhooks>
WORKER_TOKEN          <long-lived JWT>
CVAT_POLL_INTERVAL    300    (seconds — fallback polling interval, default 5 min)
```

---

## Steps It Runs

| step_type | What it does |
|---|---|
| `step.human_review` | CVAT push (gate step — raises GateException, run goes to `waiting`) |

---

## Push Flow (when step.human_review fires)

```
1. Load annotation_revision_ids from input_refs
2. Load data_items for those revisions
3. Call CVAT API:
   a. GET  /api/projects?name={cvops_project_name}  find or create CVAT project
   b. POST /api/tasks                               create task for this batch
   c. POST /api/tasks/{id}/data                     upload images
   d. POST /api/tasks/{id}/annotations              upload pre-labels
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

The API receives `POST /internal/cvat/webhook` and forwards the signal into the `labeling` Redis Stream. This worker picks it up.

```
1. Check all CVAT jobs in labeling_jobs.cvat_job_ids are completed
2. GET /api/tasks/{cvat_task_id}/annotations   download reviewed annotations
3. Convert CVAT geometry → canonical annotation payload per annotation_type
4. INSERT annotation_revisions rows:
   { annotation_type: 'annotation.cv.detection',
     source: 'human',
     review_status: 'accepted',
     author_user_id: <mapped from CVAT user> }
5. UPDATE labeling_jobs:
   { status: 'completed', completed_at: now(),
     annotation_revision_ids_out: [...] }
6. POST /api/runs/{workflow_run_id}/gates/{step_id}/resolve
   → API resumes the workflow from the next step
```

Idempotent — if pull flow is triggered twice (webhook + poll race), checking `labeling_jobs.status == 'completed'` at step 1 short-circuits the second call.

---

## Geometry Conversion

**Push — CVOps → CVAT:**
```
bbox [cx, cy, w, h] normalized →
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
| PostgreSQL `annotation_revisions` | Pre-label data to push to CVAT |
| PostgreSQL `data_items` | Image metadata (width, height) for geometry conversion |
| CVAT REST API | Completed annotation data |

---

## Writes To

| Destination | What |
|---|---|
| PostgreSQL `labeling_jobs` | Push record, completion record |
| PostgreSQL `annotation_revisions` | Human-reviewed annotation revisions |
| PostgreSQL `runs` | Status updates |
| PostgreSQL `events` | Status transitions |
| CVAT REST API | Tasks, images, pre-labels |
| API `POST /runs/{id}/gates/{step_id}/resolve` | Workflow resume signal |

---

## Does NOT

```
✗ touch MinIO directly (images go to CVAT via CVAT's storage, not re-uploaded to MinIO)
✗ launch Docker containers
✗ hold the Docker socket
✗ run preprocessing steps
✗ know what YOLO is or any export format
```
