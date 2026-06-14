# Projects

## Purpose

`Project` is the top-level workspace container in CVOps. Every ML artifact — samples, datasets,
workflows, runs, and models — belongs to exactly one project. Projects themselves belong to an
`Org`, making the ownership hierarchy: **Org → Project → everything else**.

---

## Tables

### `projects`

Inherits the standard `EntityBase` columns (`id`, `created_at`, `updated_at`, `deleted_at`).

| Column | Type | Constraints |
|---|---|---|
| `org_id` | UUID | FK → `orgs.id`, NOT NULL, indexed |
| `name` | TEXT | NOT NULL |
| `task_type` | TEXT | NOT NULL, default `'detection'` |
| `default_ontology_id` | UUID | FK → `ontologies.id`, nullable |
| `default_ingest_workflow_id` | UUID | FK → `workflows.id`, nullable |
| `settings` | JSONB | nullable |

> `default_ontology_id` and `default_ingest_workflow_id` are added via deferred
> `ALTER TABLE`s (both target tables reference `projects`, so the FK is created
> after) — `default_ingest_workflow_id` lands in migration `0002`. See
> [Circular FK](#circular-fk-projects--ontologies) below.
>
> `default_ingest_workflow_id` is the workflow auto-dispatched by
> `confirm-upload` when a data source finishes uploading (backend-triggered
> ingest). Set it the same deferred way as `default_ontology_id` (never in the
> project INSERT transaction).

---

## `task_type` Values

| Value | Meaning |
|---|---|
| `detection` | Object detection — bounding-box annotations |
| `segmentation` | Pixel-level mask annotations |
| `classification` | Image-level class-label annotations |

---

## Circular FK: `projects` ↔ `ontologies`

Two tables reference each other:

- `projects.default_ontology_id` → `ontologies.id`
- `ontologies.project_id` → `projects.id`

A standard `CREATE TABLE` cannot express both FKs simultaneously, so the migration resolves the
cycle by:

1. Creating `projects` **without** `default_ontology_id`.
2. Creating `ontologies` with `ontologies.project_id → projects.id`.
3. Running `ALTER TABLE projects ADD COLUMN default_ontology_id UUID REFERENCES ontologies(id)`
   after both tables exist.

**Rule:** Never set `default_ontology_id` at project creation time. The safe sequence is:

1. `INSERT` into `projects` (leave `default_ontology_id` NULL), commit.
2. `INSERT` into `ontologies` with the new `project_id`, commit.
3. `UPDATE projects SET default_ontology_id = <ontology_id>` in a separate statement/transaction.

Setting `default_ontology_id` and creating its referenced ontology in the same transaction risks
FK ordering failures and violates the intent of the deferred constraint.

---

## Soft Delete

Projects use soft-delete via the `deleted_at` timestamp from `EntityBase`. A project is
considered deleted when `deleted_at IS NOT NULL`.

**Child resources are not touched.** Samples, datasets, runs, and all other child records remain
intact in the database. Hide a soft-deleted project from active listings by always filtering:

```sql
WHERE projects.deleted_at IS NULL
```

This makes it straightforward to restore a project or audit historical data without data loss.

---

## Common Query Patterns

**List active projects for an org:**

```sql
SELECT *
FROM projects
WHERE org_id = $1
  AND deleted_at IS NULL
ORDER BY created_at DESC;
```

**Get a project together with its default ontology:**

```sql
SELECT
  p.*,
  o.id          AS ontology_id,
  o.name        AS ontology_name,
  o.label_map   AS ontology_label_map
FROM projects p
LEFT JOIN ontologies o ON o.id = p.default_ontology_id
WHERE p.id = $1
  AND p.deleted_at IS NULL;
```

---

## What NOT To Do

- **Never hard-delete a project** if samples or audit events are linked to it. Hard deletes
  cascade unpredictably and destroy audit trails. Always use soft-delete.
- **Never set `default_ontology_id` in the same transaction as the project INSERT.** The
  ontology row must already exist before the FK can be satisfied. Insert the project, commit,
  create the ontology, then update the project in a separate operation.
- **Never create an ontology without a valid `project_id`.** Orphaned ontologies have no
  meaningful context and break the ownership hierarchy.
