# CVOps — Service Contracts

Each service has its own ICD (Interface Control Document) in this directory.
An ICD defines what a service needs, what it reads, what it writes, and what it explicitly does NOT do.

**Last updated:** 2026-06-11

---

## Documents

| File | Service | Owner |
|---|---|---|
| [api.md](./api.md) | API (FastAPI) | Yehuda |
| [worker-preprocessing.md](./worker-preprocessing.md) | Preprocessing Worker | Nati / Yahav |
| [worker-labeling.md](./worker-labeling.md) | Labeling Worker | TBD |
| [worker-training.md](./worker-training.md) | Training Worker | Nati / Yahav |
| [frontend.md](./frontend.md) | Frontend (React) | TBD |
| [step-contract.md](./step-contract.md) | Step ABC (shared library) | Itai |
| [redis-streams.md](./redis-streams.md) | Redis Stream message format | Yehuda |

---

## Shared Concepts

### Job Lifecycle

Every unit of async work is a row in the `runs` table. This is the single source of truth for job state — Redis Streams carry only a wake-up signal.

```
pending   → worker picks it up        → running
running   → step completes            → succeeded
running   → step raises gate          → waiting    (human review pause)
waiting   → gate resolved             → running    (resumes next step)
running   → step raises error         → failed
failed    → user retries              → running    (attempt + 1)
```

### Worker Token

Workers authenticate to the API using a long-lived JWT (`WORKER_TOKEN` env var). Never use user credentials in workers.

### Presigned URL Pattern

No service proxies bytes. Ever.

```
wants bytes → asks API for presigned URL → API returns URL → goes directly to MinIO
```

The API is the gatekeeper (auth + authorization). MinIO is the byte store. They are never mixed.

---

## Communication Map

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
     │     │             │              │
     └─────┴─────────────┘              │
           │ write to PG                │
           ▼                            │
       PostgreSQL ─────────────────────►│
       (facts, job state)     presigned URL generation

  worker-labeling  ──► CVAT           (push tasks, pull annotations)
  worker-training  ──► Docker daemon  (launch training containers)
```

### Who talks to what

| From | To | How | What |
|---|---|---|---|
| Browser | API | HTTP REST | auth, CRUD, workflow runs |
| Browser | API | SSE | live run events |
| Browser | MinIO | HTTP presigned | upload / download bytes |
| API | PostgreSQL | SQLAlchemy async | all reads and writes |
| API | Redis | redis-py | locks, cache, XADD to streams |
| API | MinIO | boto3 | presigned URL generation only |
| worker-preprocessing | PostgreSQL | asyncpg | job pickup + result write |
| worker-preprocessing | MinIO | boto3 | read source blobs, write outputs |
| worker-preprocessing | Redis | redis-py | XREADGROUP, XACK |
| worker-labeling | PostgreSQL | asyncpg | job pickup + revision write |
| worker-labeling | Redis | redis-py | XREADGROUP, XACK |
| worker-labeling | CVAT | httpx REST | push tasks, pull annotations |
| worker-labeling | API | httpx REST | `POST /runs/{id}/gates/{step}/resolve` |
| worker-training | PostgreSQL | asyncpg | job pickup + model_version write |
| worker-training | MinIO | boto3 | read dataset, write weights |
| worker-training | Redis | redis-py | XREADGROUP, XACK |
| worker-training | Docker daemon | docker-py | container launch + monitor |
