# ICD — API Service

**Owner:** Yehuda
**Last updated:** 2026-06-11

---

## What it is

The orchestration layer. Handles all HTTP from the browser, manages auth, owns all CRUD, runs the workflow executor (Phase 1: in-process via `BackgroundTasks`; Phase 2: dispatches jobs to workers via Redis Streams), and issues presigned URLs for MinIO access.

---

## Dependencies (must be healthy before API starts)

```
PostgreSQL   all reads and writes
MinIO        presigned URL generation only — API never touches bytes
Redis        locks, cache, SSE pub/sub, job enqueue (Phase 2)
```

---

## Environment Variables

```
DATABASE_URL        postgresql+asyncpg://cvops:<password>@postgres:5432/cvops
MINIO_ENDPOINT      http://minio:9000
MINIO_ACCESS_KEY    <minio root user>
MINIO_SECRET_KEY    <minio root password>
MINIO_BUCKET        cvops-blobs
REDIS_URL           redis://redis:6379/0
JWT_SECRET          <min 32 chars, random>
WORKER_TOKEN        <long-lived JWT issued to workers>
```

---

## Reads From

| Source | What |
|---|---|
| PostgreSQL | All tables — auth, projects, data_items, commits, runs, events, etc. |
| Redis | Distributed locks (branch CAS protection), short-lived presigned URL cache |

---

## Writes To

| Destination | What |
|---|---|
| PostgreSQL | All domain tables. Every mutation emits an `events` row. |
| Redis Streams | `preprocessing`, `labeling`, `training` — thin `{job_id, step_type, queue}` messages when a run is created (Phase 2 only) |
| Redis pub/sub | `runs:{run_id}` channel — event payloads for SSE delivery to browser |

---

## Exposes

```
REST API     /api/*                              all endpoints (see MASTER_PLAN §12)
SSE stream   /api/runs/{id}/events/stream        live run event push
Webhook      /internal/cvat/webhook              CVAT completion signal receiver
Health       /internal/health                    {status, db, minio, redis}
```

---

## Phase 1 vs Phase 2 Execution

**Phase 1** — executor runs inside the API process via FastAPI `BackgroundTasks`. No Redis enqueue, no worker containers needed. Steps execute synchronously after the HTTP response is returned.

**Phase 2** — API creates a `runs` row, then does `XADD` to the appropriate Redis Stream. Worker containers pick up the job. API never waits for completion.

The switch between phases is in `engine/executor.py` only. No other code changes.

---

## Does NOT

```
✗ proxy image bytes, model weights, or export archives — issues presigned URLs instead
✗ execute long-running step logic in the request thread (Phase 2)
✗ hold the Docker socket
✗ talk to CVAT directly
✗ know what a "frame", "RF capture", or "audio segment" is — domain-agnostic
```
