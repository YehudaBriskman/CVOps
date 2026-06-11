# Annotations DB Layer

## Purpose

`AnnotationRevisions` are an append-only history of labels for each sample. Every new set of labels — from a model, from a human reviewer, or from a merge — adds a new revision row. The "current" annotation for a sample is its highest `revision_no`.

This design makes the full annotation history auditable, supports rollback to any prior revision without data loss, and separates the act of labeling from the act of reviewing.

---

## Table: `annotation_revisions`

This table does **not** inherit `EntityBase`. It has no `updated_at` and no `deleted_at` column — by design. Rows are immutable once written.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| `id` | `UUID` | PK | Surrogate key |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | Write timestamp |
| `created_by` | `UUID` | nullable FK → users | Null for automated/imported revisions |
| `project_id` | `UUID` | FK → projects | Owning project |
| `sample_id` | `UUID` | FK → samples | The sample this annotation describes |
| `ontology_id` | `UUID` | FK → ontologies | Ontology used for this revision |
| `ontology_version` | `INTEGER` | NOT NULL | Snapshot of ontology version at write time |
| `revision_no` | `INTEGER` | NOT NULL | Monotonically increasing per sample |
| `parent_revision_id` | `UUID` | nullable FK → self | Points to the revision this one supersedes |
| `payload` | `JSONB` | NOT NULL | Label array — see schema below |
| `provenance` | `JSONB` | NOT NULL | Origin metadata — see schema below |

**Index:** `(sample_id, revision_no)` — supports both point lookups and "latest revision" queries efficiently.

---

## Payload Schema

`payload` is a JSON array of annotation objects, one per labeled instance in the sample.

```json
[
  {
    "class_key": "vehicle.car",
    "geometry": {
      "type": "bbox",
      "coords": [cx, cy, w, h]
    },
    "confidence": 0.92,
    "track_id": null
  }
]
```

### Field notes

- **`class_key`** — dot-separated ontology class identifier (e.g. `vehicle.car`, `person.pedestrian`).
- **`geometry.type`** — one of: `bbox`, `polygon`, `oriented_bbox`, `keypoints`.
- **`geometry.coords`** — normalized to the range `[0, 1]` relative to the image dimensions. Format depends on geometry type.
- **`confidence`** — model confidence score `[0, 1]`; `null` for human-authored annotations.
- **`track_id`** — reserved for multi-frame tracking sequences; `null` for single-frame annotations.

---

## Provenance Schema

`provenance` is a single JSON object describing where this revision came from and its current review state.

```json
{
  "source": "model" | "human" | "import" | "merge",
  "model_version_id": "<uuid or null>",
  "author_user_id": "<uuid or null>",
  "confidence_threshold": 0.35,
  "review_status": "unreviewed" | "accepted" | "rejected" | "needs_second_review"
}
```

### Field notes

- **`source`** — origin of this revision:
  - `model` — produced by an inference run.
  - `human` — produced by a human annotator or reviewer (e.g. via CVAT).
  - `import` — ingested from an external dataset.
  - `merge` — produced by a merge step combining multiple revisions.
- **`model_version_id`** — UUID of the model version that produced this revision; `null` when `source` is not `model`.
- **`author_user_id`** — UUID of the user who created this revision; `null` for model/import sources.
- **`confidence_threshold`** — the threshold applied during inference or filtering when this revision was generated; `null` if not applicable.
- **`review_status`** — lifecycle state of this revision:
  - `unreviewed` — default for model/import revisions awaiting human review.
  - `accepted` — a reviewer confirmed this revision is correct.
  - `rejected` — a reviewer marked this revision as incorrect.
  - `needs_second_review` — flagged for a second opinion before acceptance.

---

## Append-Only Model

This table is **append-only**. No `UPDATE` or `DELETE` statements should ever touch it.

- **To edit an annotation:** insert a new row with `revision_no = MAX(prior revision_no) + 1` and set `parent_revision_id` to the `id` of the revision being superseded.
- **To accept during human review:** CVAT or the review tool writes back the corrected labels as a brand-new row with `source = "human"` and `review_status = "accepted"`. The prior model revision remains unchanged.
- **To reject:** insert a new row with `review_status = "rejected"` (or update the review workflow state externally — do not touch the revision row itself).

The `parent_revision_id` chain is the authoritative audit trail. Do not break it.

---

## Finding the Current Annotation

**Single sample — point lookup:**

```sql
SELECT *
FROM annotation_revisions
WHERE sample_id = ?
ORDER BY revision_no DESC
LIMIT 1;
```

**All samples in a project — bulk latest-revision query:**

```sql
SELECT DISTINCT ON (sample_id) *
FROM annotation_revisions
WHERE project_id = ?
ORDER BY sample_id, revision_no DESC;
```

`DISTINCT ON` with the correct `ORDER BY` is the canonical PostgreSQL pattern for this. It is single-pass and efficient when the `(sample_id, revision_no)` index is present.

---

## What NOT To Do

- **Never `UPDATE` `payload` or `provenance`** on an existing row. The row is a historical record the moment it is written.
- **Never `DELETE` a revision** that is referenced by `commit_samples.annotation_revision_id`. Doing so will break commit integrity and violate foreign key constraints.
- **Never reuse a `revision_no`** for the same `sample_id`. Revision numbers are monotonically increasing and must remain stable.
- **Never set `parent_revision_id` to a revision belonging to a different `sample_id`**. The parent chain must be scoped to a single sample.
