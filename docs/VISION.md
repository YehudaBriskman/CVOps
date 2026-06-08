# CVOps — Full Product Vision

> This document explains what we are building, why, how the user experiences it, and how the system works underneath. Written for the team to align on the full picture before dividing work.

---

## What Is CVOps?

CVOps is a **general-purpose ML lifecycle dashboard**. It is the platform that sits between raw data and a trained model — handling everything in between: data ingestion, human labeling, dataset versioning, and training dispatch.

It is **model-agnostic**. It does not care what you are training. YOLO, a segmentation model, a custom architecture — if you can put it in a Docker container, CVOps can run it.

It is **annotation-agnostic**. All human labeling happens in CVAT (self-hosted), which CVOps integrates with via API. CVOps does not build its own labeling UI.

The user brings two things:
1. Their raw data (videos or images)
2. Their training container (a Docker image they built, with a small config telling CVOps how to talk to it)

CVOps provides everything else.

---

## The Core Concepts

Before the lifecycle, there are a few concepts to internalize. Everything else follows from them.

### Projects and Workflows

A **project** is the top-level unit — one problem domain, one team. For example: "Road traffic detection" or "Medical scan classification."

A **workflow** is a reusable pipeline the user defines once and re-runs as many times as needed. It is a sequence of steps:

```
ingest data → push to CVAT → [human labels] → sync from CVAT → version dataset → export → train
```

Workflows are saved. A project can have multiple workflows. A user can clone and modify an existing one.

### Dataset Versioning (the most important concept)

Every time a labeling cycle completes, CVOps takes a **snapshot** of the dataset — a frozen, immutable record of exactly which images existed, what the labels were, and which split (train/val/test) each image belonged to. We call this a **commit**, borrowing the idea from git.

A commit never changes. It is permanent. This means:
- You can always go back and re-train on the exact data that produced a previous model
- Multiple projects can share the same dataset without ever conflicting
- Every model is permanently linked to the exact dataset commit it was trained on

Commits are organized into **branches** (a moving line of work, like `main`) and **tags** (a permanent label, like `v1.0`).

### The Training Container + ICD

The user's training logic lives in a Docker container they build themselves. CVOps does not care what is inside it. To launch it, CVOps needs a small configuration — the **ICD (Interface Control Document)** — that describes:

- Which Docker image to use
- How to pass the dataset to it (environment variables, mounted volume path)
- Where it writes its model output and metrics

Once the user defines their ICD once, CVOps can launch their container on every training run, passing the right dataset version every time.

---

## The Full User Lifecycle

### Phase 1 — Setup (done once per project)

1. **Create a project** — name it, set the task type (detection, segmentation, etc.), define the label classes (e.g. `car`, `pedestrian`, `truck`)
2. **Define a workflow** — pick the steps, configure each one (frame extraction interval, auto-label confidence threshold, split ratio, etc.), save it
3. **Register a training container** — provide the ICD: Docker image name, how to pass the dataset, where to read results back from

This is a one-time setup. After this, the user just runs the workflow repeatedly as new data arrives.

---

### Phase 2 — Running the Pipeline

#### Step 1: Data Ingestion
The user provides data in one of two ways:
- Uploads files directly through the dashboard
- Points to an existing location (a folder path or object storage bucket)

The system receives the data. If it is video, frames are extracted at the configured interval. Images are deduplicated — if a frame was already ingested before (identical bytes), it is not stored twice.

#### Step 2: Push to CVAT
The backend creates (or reuses) a CVAT project and task for this run:
- If a CVAT project for this CVOps project already exists, reuse it
- Create a new CVAT task for this batch of data
- Upload all images to CVAT
- Upload any existing annotations as pre-labels (so annotators only need to correct, not start from scratch)

The pipeline pauses and waits.

#### Step 3: Human Labeling
The dashboard shows the user a direct link: **"Open in CVAT →"**

The user (or their annotators) open CVAT and do their work there — drawing boxes, correcting auto-generated labels, accepting or rejecting predictions. CVOps does not touch this step. CVAT is the tool; the user is in control.

When labeling is complete, the annotator marks the job as done in CVAT.

#### Step 4: Sync Back
CVOps detects the completed job (via CVAT webhook or polling). It:
- Pulls all annotations from CVAT
- Converts them to the internal format
- Stores them as a new **annotation revision** — a permanent, traceable record of who labeled what and when (human vs. auto-generated)

#### Step 5: Create a Dataset Commit
A frozen snapshot of the dataset is created:
- Which images are included
- Which annotation revision each image uses
- Which split (train / val / test) each image belongs to — **assigned at the source/video level**, never randomly per-frame, to prevent data leakage
- Class statistics and counts

This commit is immutable. It gets a unique ID. The branch head advances to point at it.

#### Step 6: Export
The dataset is materialized into the format the training container expects (e.g. YOLO folder layout with `data.yaml`, or COCO JSON). The export is itself stored as a content-addressed artifact — exporting the same commit again is a no-op, the cached result is returned.

#### Step 7: Train
CVOps launches the user's Docker container, passing:
- The path to the exported dataset
- The hyperparameters from the workflow config
- Any other fields defined in the ICD

The container trains. CVOps monitors it.

#### Step 8: Results
When training completes, CVOps:
- Reads the metrics and model weights path from the output defined in the ICD
- Creates a **model version** record in the database
- Links it permanently to the dataset commit it trained on
- Displays results in the dashboard: accuracy, loss, any metrics the container reported

---

### Phase 3 — Iteration

The user now has a trained model and a versioned dataset. On the next iteration:
- New data arrives → run the workflow again
- A new commit is created (building on the previous one)
- A new training run is triggered
- The dashboard shows: **model v2 trained on commit #a3f9** vs **model v1 trained on commit #8c12** — compare metrics on equal ground

The loop repeats. Each cycle produces a better model, and every step of every cycle is fully traceable.

---

## System Components

| Component | What it does | Tech |
|---|---|---|
| **Dashboard** | The user-facing web app — project management, workflow builder, dataset browser, run monitoring | React + TypeScript |
| **API** | The backend — auth, CRUD, job dispatch. Never does heavy work itself | FastAPI (Python) |
| **Celery Workers** | Execute all heavy/async steps — frame extraction, CVAT sync, export, training dispatch | Celery + Redis |
| **PostgreSQL** | All structured data — projects, samples, annotations, commits, runs, events | PostgreSQL |
| **MinIO** | All binary data — images, frames, exports, model weights. Content-addressed | MinIO (S3-compatible) |
| **Redis** | Job queue between API and workers; also caches run results | Redis |
| **CVAT** | Human labeling UI. Self-hosted. CVOps pushes tasks in and pulls results out via CVAT API | CVAT (self-hosted) |
| **Training Container** | User-built Docker image. CVOps launches it; it trains and writes results | Any Docker image |
| **Nginx** | Single entry point — routes everything under one host and port | Nginx |

Everything runs via Docker Compose. No external cloud dependencies required.

---

## The Training Container Interface (ICD)

The ICD is a small YAML config the user provides when registering their training container. Example:

```yaml
image: my-org/yolo-trainer:latest

inputs:
  dataset_path:   env: DATASET_PATH      # CVOps sets this to the exported dataset location
  epochs:         env: EPOCHS
  batch_size:     env: BATCH_SIZE
  seed:           env: SEED

outputs:
  metrics_file:   path: /output/metrics.json   # CVOps reads this when the run ends
  weights_path:   path: /output/weights/        # CVOps stores this in MinIO
```

CVOps reads this config, launches the container with the right environment, mounts the dataset volume, and reads results from the defined output paths when the run finishes. The training logic is entirely the user's — CVOps only manages the launch and the result capture.

This is what makes the platform model-agnostic. Any model, any framework, any training loop — as long as it runs in Docker and speaks this interface.

---

## MLflow Integration (Planned)

When the user's training container is configured to report to MLflow, CVOps will:

- Detect the MLflow tracking URI from the container's output or ICD config
- Store a reference to the MLflow run ID alongside the model version record
- Display a **"View in MLflow →"** link on the training run page in the dashboard

CVOps does not replicate MLflow's UI or functionality. It links to it. The user gets the full MLflow experiment view (loss curves, hyperparameter comparison, artifact browser) by following the link, while CVOps manages the data versioning and pipeline orchestration around it.

In later phases, CVOps may also read summary metrics back from MLflow (via its API) and surface them natively in the model comparison view, so users can compare runs without leaving the dashboard.

---

## What CVOps Does NOT Do

To keep scope clear:

- **Does not build a labeling UI** — CVAT handles all annotation. CVOps only orchestrates it.
- **Does not implement training logic** — the user's container does that. CVOps only dispatches and monitors.
- **Does not replace MLflow** — it integrates with it and links to it.
- **Does not lock you to YOLO** — it is format and model agnostic.

---

## Team Work Areas (Proposed Division)

| Area | Scope |
|---|---|
| **Data substrate** | PostgreSQL schema, dataset versioning (commits/branches/refs), annotation revisions, the blob store, migrations |
| **Ingestion + extraction** | Frame extractor worker (FFmpeg), deduplication, data source handling |
| **CVAT integration** | Push tasks to CVAT, pull completed annotations back, webhook/poll handler, annotation revision writer |
| **Workflow engine** | Step contract, step registry, synchronous executor (Phase 1), run state machine, the `runs`/`events` tables |
| **Export + training dispatch** | YOLO exporter, ICD config loader, Docker container launcher, result reader, model version recorder |
| **Dashboard + API** | React frontend (project pages, workflow builder, dataset browser, run view), FastAPI endpoints |
| **Infrastructure** | Docker Compose setup, Nginx config, MinIO, Redis, CVAT self-hosted deployment |

---

## The One-Paragraph Summary

CVOps is a dashboard where a user manages the full lifecycle of an ML project — from raw video or images, through human labeling in CVAT, to a versioned dataset, to a trained model in their own Docker container. Every labeled dataset state is permanently versioned like a git commit. Every trained model is linked to the exact data that produced it. The user defines a workflow once and re-runs it as new data arrives. The platform is general — any label type, any model, any training framework — as long as the training container speaks the ICD. The whole stack runs self-hosted with a single `docker compose up`.
