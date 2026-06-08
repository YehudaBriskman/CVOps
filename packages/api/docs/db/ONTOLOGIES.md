# Ontologies

## Purpose

Ontologies define the label vocabulary for a project. Each ontology contains an ordered set of `LabelClass` records identified by a stable `class_key` string (e.g. `"vehicle.car"`). A `class_key` is never a YOLO integer — it is mapped to a YOLO class integer only at export time via `sort_order`. This design prevents class ID drift when labels are added or reordered.

---

## Tables

### `ontologies`

Extends `EntityBase`.

| Column       | Type    | Constraints                          | Notes                          |
|--------------|---------|--------------------------------------|--------------------------------|
| `project_id` | FK      | NOT NULL, references `projects(id)`  | Owning project                 |
| `name`       | TEXT    | NOT NULL                             | Human-readable ontology name   |
| `version`    | INTEGER | NOT NULL, default `1`                | Incremented on schema changes  |

**Unique constraint:** `UNIQUE(project_id, name)`

---

### `label_classes`

Extends `EntityBase`.

| Column         | Type    | Constraints                             | Notes                                               |
|----------------|---------|-----------------------------------------|-----------------------------------------------------|
| `ontology_id`  | FK      | NOT NULL, references `ontologies(id)`   | Owning ontology                                     |
| `class_key`    | TEXT    | NOT NULL                                | Stable string identifier, e.g. `"vehicle.car"`      |
| `display_name` | TEXT    | NOT NULL                                | Human-readable label shown in the UI                |
| `color`        | TEXT    | NOT NULL, default `"#FF0000"`           | Hex color for UI rendering                          |
| `sort_order`   | INTEGER | NOT NULL                                | Determines YOLO class integer at export time        |

**Unique constraints:**
- `UNIQUE(ontology_id, class_key)` — a stable string key is unique within an ontology
- `UNIQUE(ontology_id, sort_order)` — no two classes may share the same export integer

---

## Critical Design: Why `class_key`, Not an Integer ID

### The YOLO class ID fragility problem

YOLO's on-disk label format stores class identity as a **positional integer** (0, 1, 2, ...). There is no name, no hash — only a number. This creates a fragile coupling between class order and label meaning:

- If you **insert** a new class in the middle of the list, every integer after the insertion point shifts by one. All existing `.txt` annotation files are now silently mislabelled.
- If you **delete** a class and close the gap, the same silent corruption occurs.
- There is no error or warning — YOLO will train happily on corrupted labels.

### How CVOps avoids this

CVOps never stores a raw YOLO integer in its database. Instead:

1. Each `LabelClass` carries a `class_key` — a stable, human-readable string (`"person.standing"`, `"vehicle.truck"`) that is set at class creation and **never changed**.
2. At export time, `class_id = sort_order`. The mapping from string to integer is computed on demand and frozen inside the export blob.
3. Existing annotation files remain correct regardless of what is added to the ontology later, because the sort_order of existing classes is immutable.

---

## `sort_order` Rules

- `sort_order` is assigned when a `LabelClass` is created and **never modified afterward**.
- `sort_order` is the sole source of truth for the YOLO integer class ID in every export.
- To add a new class, append it with a `sort_order` value higher than all existing classes. Never insert into the middle of the sequence.
- **Never reuse a retired `sort_order`.** If a class is soft-deleted, its `sort_order` is permanently reserved to prevent silent collisions in historical exports.

---

## Ontology Versioning

- The `version` column on `ontologies` is incremented whenever label classes are added or their display metadata (name, color) is modified.
- `class_key` and `sort_order` are immutable — they are never part of a version bump because changing them would invalidate existing data.
- Each `annotation_revision` record stores the `ontology_version` at creation time, providing full lineage: you can reconstruct exactly which label vocabulary was in effect for any annotation in the system.

---

## Common Query Patterns

**Get all label classes ordered for YOLO export:**

```sql
SELECT class_key, display_name, sort_order
FROM label_classes
WHERE ontology_id = $1
ORDER BY sort_order ASC;
```

**Validate that a `class_key` exists in an ontology:**

```sql
SELECT id
FROM label_classes
WHERE ontology_id = $1
  AND class_key   = $2
LIMIT 1;
```

---

## What NOT To Do

- **Never change `sort_order` on an existing `LabelClass`.** This corrupts all existing exports and every annotation that was created against the original mapping.
- **Never delete a `LabelClass` that appears in any `annotation_revision` payload.** Use a soft-delete or a tombstone flag instead; hard deletion breaks historical lineage.
- **Never reuse a retired `sort_order` integer.** Even if a slot appears free, a historical export may already encode that integer as the retired class. Reusing it silently changes the meaning of those exports.
