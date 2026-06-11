# Dataset Versioning

## Purpose

Dataset versioning works like git for ML data. A `Dataset` has a history of immutable `Commit` rows. `Ref` rows (branches and tags) point at commits. Projects link to datasets via `ProjectDatasetLink`, which is either pinned to a specific commit or floating on a branch.

This model gives the same guarantees ML practitioners need: reproducibility (pin to a commit for a stable training snapshot), collaboration (multiple branches, merges), and auditability (commit history is append-only and never rewritten).

---

## Tables

### `datasets`

Inherits `EntityBase`.

| Column | Type | Notes |
|---|---|---|
| `project_id` | FK | Owning project |
| `name` | TEXT | Human-readable identifier |

Constraint: `UNIQUE(project_id, name)`

---

### `commits`

Does **not** inherit `EntityBase` — commits are immutable records, not updatable entities.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `created_at` | TIMESTAMPTZ | Set once at insert |
| `created_by` | FK | User who created the commit |
| `project_id` | FK | Owning project |
| `dataset_id` | FK | Parent dataset |
| `parent_commit_id` | FK → `commits` (nullable) | Previous commit in linear history |
| `second_parent_commit_id` | FK → `commits` (nullable) | Second parent for merge commits |
| `ontology_id` | FK | Ontology snapshot used |
| `ontology_version` | INTEGER | Pinned version of that ontology |
| `message` | TEXT | Default `''` |
| `stats` | JSONB | Precomputed at commit time, cached forever |

**`stats` shape:**

```json
{
  "total": 4200,
  "by_split": {
    "train": 3360,
    "val": 840
  },
  "by_class": {
    "vehicle.car": 1800
  },
  "review_status": {
    "accepted": 3100,
    "unreviewed": 1100
  }
}
```

---

### `commit_samples`

The materialized membership table. Records exactly which samples, at which annotation revision, appear in a given commit and in which split.

| Column | Type | Notes |
|---|---|---|
| `commit_id` | FK → `commits` | Part of composite PK |
| `sample_id` | FK | Part of composite PK |
| `annotation_revision_id` | FK | The annotation state captured at commit time |
| `split` | TEXT | `train`, `val`, or `test` |

Primary key: `(commit_id, sample_id)`

Rows in this table are **never deleted**. They are the durable, auditable record of what a commit contained.

---

### `refs`

Inherits `EntityBase`. A ref is a named pointer to a commit — either a mutable branch or an immutable tag.

| Column | Type | Notes |
|---|---|---|
| `dataset_id` | FK | Owning dataset |
| `ref_type` | TEXT | `branch` or `tag` |
| `name` | TEXT | Ref name (e.g. `main`, `v1.0`) |
| `target_commit_id` | FK → `commits` | The commit this ref currently points to |
| `is_mutable` | BOOL | `true` for branches, `false` for tags |

Constraint: `UNIQUE(dataset_id, ref_type, name)`

- **Branch**: `is_mutable = true`. `target_commit_id` advances with each new commit.
- **Tag**: `is_mutable = false`. `target_commit_id` is fixed at creation and must never change.

---

### `project_dataset_links`

Inherits `EntityBase`. Joins a project to a dataset and records how the project tracks it.

| Column | Type | Notes |
|---|---|---|
| `project_id` | FK | |
| `dataset_id` | FK | |
| `pinned_commit_id` | FK → `commits` (nullable) | Fixed snapshot |
| `ref_id` | FK → `refs` (nullable) | Floating branch pointer |

Constraints:
- `UNIQUE(project_id, dataset_id)` — a project can only link a given dataset once.
- `CHECK`: exactly one of `pinned_commit_id` or `ref_id` must be non-null. Both null and both set are invalid.

---

## Commit Immutability

Once a `commits` row is inserted, it is **never updated**. The `stats` column is computed at commit time and cached permanently. There is no mechanism to patch a commit after the fact; if the data changes, a new commit is created on top.

---

## Branch Advance via CAS

Advancing a branch head is a Compare-And-Swap (CAS) operation to prevent lost updates under concurrent writes:

```sql
UPDATE refs
SET target_commit_id = :new_commit_id,
    updated_at       = now()
WHERE id                = :ref_id
  AND target_commit_id  = :expected_head
```

If the `UPDATE` affects 0 rows, another process has already advanced the branch since the caller last read it. The caller must re-read the current head, resolve the conflict, and retry.

---

## Pinned vs Floating Dataset Links

| Mode | Column set | Behavior |
|---|---|---|
| **Pinned** | `pinned_commit_id` | The project always sees exactly that snapshot. Reproducible, immutable from the project's perspective. |
| **Floating** | `ref_id` | The project tracks the latest commit on the referenced branch. Moves forward automatically as new commits land. |

Pinned links are the right default for model training jobs where reproducibility is required. Floating links are useful for active development workflows where a project always wants the freshest data.

---

## Common Query Patterns

**Get the current sample set for a branch:**

```
refs → (target_commit_id) → commits → commit_samples
```

**Compare two commits:**

Compare their `commit_samples` sets by `commit_id`. The symmetric difference is what was added or removed.

**Resolve the training dataset for a model version:**

```
model_versions.trained_on_commit_id → commits → commit_samples
```

---

## What NOT To Do

- **Never `UPDATE` a `commits` row after insertion.** Commits are immutable. If you need to correct data, create a new commit.
- **Never advance a tag's `target_commit_id`.** `is_mutable = false` is a code-level convention; the database does not enforce it with a trigger. Enforce it in the application layer.
- **Never `DELETE` rows from `commit_samples`.** They are the materialized, auditable snapshot of each commit. Deletion would silently corrupt historical reproducibility.
