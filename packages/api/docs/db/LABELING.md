# Labeling Jobs Domain

## Purpose

`LabelingJob` represents a "lease" of annotation work dispatched to CVAT. When a workflow reaches the `human_review` step, CVOps pushes existing annotation revisions to CVAT as pre-labels, pauses the workflow, and waits for human annotators to review and correct them. Once CVAT signals completion, CVOps ingests the results as new `AnnotationRevision` rows (`source="human"`) and resumes the workflow. CVAT is purely a review tool — CVOps owns the annotations at all times.

---

## Table: `labeling_jobs`

Extends `EntityBase`.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| *(EntityBase)* | — | `id`, `created_at`, `updated_at` | |
| `project_id` | UUID FK → `projects` | NOT NULL | Owning project |
| `run_id` | UUID FK → `runs` | NOT NULL | The `human_review` step run that created this job |
| `step_id` | TEXT | NOT NULL | Step identifier within the workflow definition |
| `cvat_project_id` | INTEGER | Nullable | CVAT project housing this task, if applicable |
| `cvat_task_id` | INTEGER | NOT NULL | CVAT task created for this batch of samples |
| `cvat_job_ids` | JSONB | NOT NULL, default `[]` | Array of individual CVAT job IDs within the task |
| `status` | TEXT | NOT NULL, default `"pushed"` | See lifecycle below |
| `completed_at` | TIMESTAMPTZ | Nullable | Set when status transitions to `"completed"` |
| `sync_error` | TEXT | Nullable | Last error message from a failed ingest attempt |
| `sample_count` | INTEGER | NOT NULL | Number of samples in this batch |
| `annotation_revision_ids_in` | JSONB | Nullable | IDs of `AnnotationRevision` rows sent as pre-labels |
| `annotation_revision_ids_out` | JSONB | Nullable | IDs of new `AnnotationRevision` rows created after ingest |

**Status values:** `pushed` | `in_progress` | `completed` | `failed`

---

## Lifecycle

```
human_review step runs
        │
        ▼
LabelingJob created (status="pushed")
Pre-labels pushed to CVAT
GateException raised → run.status="waiting"
        │
        ▼
Annotators work in CVAT
CVAT webhook / polling fires
        │
        ▼
LabelingJob.status → "completed"
        │
        ▼
CVOps pulls results from CVAT
New AnnotationRevision rows created (source="human", review_status="accepted")
annotation_revision_ids_out populated
        │
        ▼
Workflow gate resolved → run.status="running"
Workflow resumes with new revision IDs
```

### Status Transitions

| From | To | Trigger |
|---|---|---|
| `pushed` | `in_progress` | CVAT signals an annotator has started |
| `in_progress` | `completed` | All `cvat_job_ids` are done |
| `pushed` / `in_progress` | `failed` | Sync error or CVAT API failure |
| `failed` | `pushed` | Retry — re-push to CVAT |

---

## Gate Step Pattern

The `human_review` step is a **gate** — it halts workflow execution rather than completing normally.

1. The step creates the `LabelingJob` row and pushes pre-labels to CVAT.
2. It raises a `GateException` before returning, which causes the engine to set `run.status = "waiting"` instead of advancing to the next step.
3. The step stores its gate data in `runs.output_refs`:
   ```json
   {"labeling_job_id": "<uuid>"}
   ```
4. When the gate is resolved (CVAT work complete and results ingested), the engine reads `output_refs`, locates the `LabelingJob`, and resumes the workflow from the step immediately following `human_review`.

The gate pattern allows the workflow engine to treat long-running human tasks the same as any other async step — the run simply sits in `waiting` state until an external event resolves it.

---

## CVAT Ownership Model

CVOps is the system of record for all annotations. CVAT is a UI for human review, not a database.

- Pre-labels pushed to CVAT are a **copy** of existing `AnnotationRevision` rows. They are never authoritative.
- Corrections made by annotators in CVAT are ingested back into CVOps as **new** `AnnotationRevision` rows with `source="human"`. The original rows are untouched.
- The workflow always references CVOps `AnnotationRevision` IDs, never raw CVAT annotation IDs.

---

## Common Query Patterns

**Find the active labeling job for a run:**

```sql
SELECT id, cvat_task_id, status, sample_count, annotation_revision_ids_out
FROM labeling_jobs
WHERE run_id = $1
ORDER BY created_at DESC
LIMIT 1;
```

**All jobs currently waiting for human review across a project:**

```sql
SELECT id, run_id, cvat_task_id, sample_count, created_at
FROM labeling_jobs
WHERE project_id = $1
  AND status IN ('pushed', 'in_progress')
ORDER BY created_at ASC;
```

**Jobs that failed to sync:**

```sql
SELECT id, cvat_task_id, sync_error, updated_at
FROM labeling_jobs
WHERE project_id = $1
  AND status = 'failed'
ORDER BY updated_at DESC;
```

---

## What NOT To Do

- **Never modify `annotation_revision_ids_in` after the job is sent.** This array is the permanent record of what pre-labels were dispatched to CVAT. Changing it after the fact makes it impossible to audit what the annotators were shown or to detect if CVOps and CVAT drifted out of sync.

- **Never mark a job `completed` before all `cvat_job_ids` are done.** CVAT tasks can contain multiple jobs assigned to different annotators. Marking the parent job complete while any child job is still open will cause the gate to resolve early and the workflow to resume with a partial result set.

- **Never let CVAT become the source of truth.** Do not read annotations directly from the CVAT API and use them in downstream steps without first writing them back as `AnnotationRevision` rows. All workflow steps consume CVOps data — a CVAT-only annotation is invisible to the rest of the system.

- **Never delete a `LabelingJob` row while its `run_id` points to a run in `waiting` status.** The engine resolves the gate by reading `runs.output_refs.labeling_job_id`. Deleting the row leaves the run permanently stuck with no gate to resolve.
