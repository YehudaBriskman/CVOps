# Runs & Events

## Purpose

Runs are the execution record for every workflow and step invocation. Every time the executor fires a workflow or a single step, it creates a `run` row and updates it as execution progresses.

Events are the append-only audit log for the entire system. Every meaningful state mutation calls `emit_event()` inside the same database transaction, producing an immutable history entry.

---

## Tables

### `runs`

Extends `EntityBase` (id, created_at, updated_at, deleted_at).

| Column | Type | Notes |
|---|---|---|
| `project_id` | UUID FK → projects | Owning project |
| `kind` | TEXT | `workflow` \| `step` \| `gc` |
| `parent_run_id` | UUID FK → runs(id) | Step runs point at their workflow run; NULL for workflow runs |
| `workflow_id` | UUID FK → workflows | Nullable (step-only runs may omit) |
| `workflow_version` | INTEGER | Snapshot of the version at run time |
| `step_id` | TEXT | Matches `steps[].id` in the workflow definition |
| `step_type` | TEXT | Denormalized from the registry for quick filtering |
| `status` | TEXT | Default `pending`; see status machine below |
| `input_refs` | JSONB | Blob hashes / ref pointers for inputs — immutable after run starts |
| `output_refs` | JSONB | Blob hashes / ref pointers for outputs |
| `config` | JSONB | Snapshot of step config at execution time — immutable after run starts |
| `metrics` | JSONB | Optional executor-reported metrics (duration, token counts, etc.) |
| `logs_blob_hash` | TEXT FK → blobs | Pointer to captured log output |
| `attempt` | INTEGER | Default `1`; incremented on retry |
| `error` | TEXT | Human-readable error message on failure |
| `started_at` | TIMESTAMPTZ | Set when status transitions to `running` |
| `finished_at` | TIMESTAMPTZ | Set when status reaches a terminal state |

---

### `events`

Append-only audit log. Rows are never updated or deleted.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `created_at` | TIMESTAMPTZ | Insertion timestamp |
| `actor_id` | UUID | Nullable; the user or service that triggered the action |
| `actor_type` | TEXT | e.g. `user`, `executor`, `system` |
| `entity_type` | TEXT | The domain object being described, e.g. `run`, `ref`, `model_version` |
| `entity_id` | UUID | ID of the affected entity |
| `action` | TEXT | Dot-namespaced verb, e.g. `run.started`, `branch.advanced` |
| `payload` | JSONB | Nullable; additional context relevant to the action |

**Index:** composite on `(entity_type, entity_id, created_at)` to support efficient per-entity history queries.

---

## Run Hierarchy

```
workflow run  (kind="workflow", parent_run_id=NULL)
  └── step run  (kind="step", parent_run_id=<workflow_run.id>, step_id="s1")
  └── step run  (kind="step", parent_run_id=<workflow_run.id>, step_id="s2")
  └── ...
```

A workflow run is the root. All step runs for that execution share the same `parent_run_id`. Garbage-collection housekeeping runs use `kind="gc"` and are not tied to a workflow.

---

## Status Machine

Standard path:

```
pending → running → succeeded
                 → failed
                 → canceled
```

Gate-step path (step is waiting for an external signal):

```
pending → running → waiting → running → succeeded
```

- `pending`: created, not yet picked up by the executor
- `running`: executor has begun processing
- `waiting`: step is blocked on a gate condition
- `succeeded`: terminal — step completed without error
- `failed`: terminal — step raised an unrecoverable error
- `canceled`: terminal — canceled by user or upstream failure policy

---

## Idempotency

Each step run carries an `idempotency_key` computed as:

```
SHA256(step_type + canonical(config) + canonical(input_refs))
```

Before the executor starts a step, it checks whether a run with the same key already has `status='succeeded'`. If one exists, the executor reuses its `output_refs` and skips execution. This makes replaying or retrying a workflow safe when upstream steps have not changed.

---

## Events: `emit_event()` Pattern

Every meaningful mutation calls `emit_event()` within the same transaction so the audit log is always consistent with the data it describes.

**Common action names:**

| `action` | `entity_type` | Fired when |
|---|---|---|
| `run.created` | `run` | A new run row is inserted |
| `run.started` | `run` | Status transitions to `running` |
| `run.succeeded` | `run` | Status transitions to `succeeded` |
| `run.failed` | `run` | Status transitions to `failed` |
| `run.canceled` | `run` | Status transitions to `canceled` |
| `branch.advanced` | `ref` | A git-style ref pointer moves forward |
| `model_version.created` | `model_version` | A new model version is registered |

---

## Common Query Patterns

**All step runs in a workflow execution:**

```sql
SELECT *
FROM runs
WHERE parent_run_id = :workflow_run_id
ORDER BY created_at;
```

**Failed runs in the last 24 hours:**

```sql
SELECT *
FROM runs
WHERE status = 'failed'
  AND created_at > now() - interval '24 hours'
ORDER BY created_at DESC;
```

**Audit history for a project (across all entity types):**

```sql
SELECT *
FROM events
WHERE entity_type IN ('run', 'ref', 'model_version')
  AND payload->>'project_id' = :project_id
ORDER BY created_at DESC;
```

**Per-entity audit trail:**

```sql
SELECT *
FROM events
WHERE entity_type = 'run'
  AND entity_id = :run_id
ORDER BY created_at;
```

---

## What NOT To Do

- **Never update `input_refs`, `output_refs`, or `config` after a run has started.** These fields are a snapshot taken at execution time. Mutating them after the fact breaks idempotency checks and makes the audit log meaningless.
- **Never update or delete rows in `events`.** The table is append-only by design. All history is permanent. If a correction is needed, emit a new corrective event.
- **Never transition a run backwards through the status machine.** A `succeeded` or `failed` run must not be moved back to `pending` or `running`. Create a new run with an incremented `attempt` instead.
