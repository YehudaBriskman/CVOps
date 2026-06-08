# Workflows

## Purpose

Workflows are data, not code. A workflow definition declares a directed acyclic graph (DAG) of steps — what each step does, how it is configured, and how its inputs are wired to upstream outputs or to the run's initial parameters. The executor reads this definition at runtime and drives execution; no workflow logic lives in application code.

---

## Table: `workflows`

Extends `EntityBase` (id, created_at, updated_at, deleted_at).

| Column | Type | Notes |
|---|---|---|
| `project_id` | UUID FK → projects | Owning project |
| `name` | TEXT | Human-readable identifier, unique within a project |
| `definition` | JSONB NOT NULL | The full DAG definition; see schema below |
| `version` | INTEGER | Default `1`; incremented on every definition change |

**Unique constraint:** `(project_id, name)`

---

## Definition Schema

The `definition` column holds a JSON object with the following shape:

```json
{
  "name": "intake-pipeline-v3",
  "steps": [
    {
      "id": "s1",
      "type": "extract_frames",
      "config": {
        "interval_seconds": 2,
        "max_frames": 5000
      },
      "inputs": {
        "source": "$run.params.video_source"
      }
    },
    {
      "id": "s2",
      "type": "auto_label",
      "config": {
        "model_version_id": "mv_abc",
        "confidence_threshold": 0.35
      },
      "inputs": {
        "sample_ids": "$steps.s1.outputs.sample_ids"
      }
    }
  ],
  "edges": [
    ["s1", "s2"],
    ["s2", "s3"]
  ]
}
```

### Top-level fields

| Field | Type | Description |
|---|---|---|
| `name` | string | Matches the `workflows.name` column; included for readability |
| `steps` | array | Ordered list of step declarations |
| `edges` | array of pairs | Explicit DAG edges as `[from_step_id, to_step_id]` |

### Step fields

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique within this definition; referenced in `$steps.sN.outputs.X` expressions |
| `type` | string | Step type key; must exist in the step registry |
| `config` | object | Static configuration passed to the step executor |
| `inputs` | object | Input wiring expressions; values are resolved at execution time |

---

## Input Wiring

Input values in a step's `inputs` map are wiring expressions resolved by the executor before the step starts.

| Expression form | Resolved from |
|---|---|
| `$run.params.X` | The workflow run's `input_refs`, keyed by `X` |
| `$steps.sN.outputs.X` | The `output_refs` of the completed step with `id="sN"`, keyed by `X` |

Wiring is validated at the start of a workflow run. If a referenced step has not yet produced output (i.e. the edge ordering is wrong), the executor will refuse to start the dependent step.

---

## Step Config Validation

Before a workflow run starts, the executor validates each step's `config` object against the JSON Schema registered for that step type. If any step's config is invalid, the entire workflow run is rejected with a validation error before any step executes. No partial execution occurs on a malformed definition.

---

## Versioning

`version` is a monotonically increasing integer. It increments every time the `definition` column changes.

When a workflow run is created, it records `workflow_version` as a snapshot. This means:

- You always know exactly which definition was in effect for any historical run.
- Changing a workflow definition after runs have started does not affect in-progress runs.
- If you need to query what a past run actually executed against, join `runs.workflow_version` with the version history.

---

## Common Query Patterns

**List all workflows for a project:**

```sql
SELECT id, name, version, created_at
FROM workflows
WHERE project_id = :project_id
  AND deleted_at IS NULL
ORDER BY name;
```

**Get the full definition for a workflow:**

```sql
SELECT definition
FROM workflows
WHERE id = :workflow_id;
```

**Determine which definition version a historical run used:**

```sql
SELECT r.id AS run_id, r.workflow_version, w.definition
FROM runs r
JOIN workflows w ON w.id = r.workflow_id
WHERE r.id = :run_id;
```

> Note: if you need to reconstruct the exact definition at the time of an old run, the version history must be preserved separately (e.g. via an audit event with the previous definition in the payload). The `workflows` table itself stores only the current definition.

---

## What NOT To Do

- **Never mutate the `definition` of a workflow that has in-progress runs referencing it.** Changing the definition mid-execution would make `runs.workflow_version` point at a definition that no longer matches what the executor was using. Always increment `version` by updating the row, and let in-flight runs complete against the version they started with.
- **Never bypass config validation.** All step configs must pass their registry schema check before execution begins. Skipping validation to unblock a run risks silent data corruption downstream.
- **Never hardcode step IDs as sequential integers.** Step `id` values are opaque strings within the definition. Callers should not assume ordering from the ID itself; use the `edges` array to determine execution order.
