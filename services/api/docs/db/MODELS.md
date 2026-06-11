# Model Versions Domain

## Purpose

`ModelVersion` records every trained model artifact produced by the system. Each row links a model's weights blob to the exact dataset commit it was trained on and to the training container (Docker image + ICD config) that produced it. This three-way relationship — commit, container, hyperparams — is what makes any model version fully reproducible.

---

## Tables

### `training_containers`

Extends `EntityBase`.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| *(EntityBase)* | — | `id`, `created_at`, `updated_at` | |
| `project_id` | UUID FK → `projects` | NOT NULL | Owning project |
| `name` | TEXT | NOT NULL | Human-readable container name |
| `description` | TEXT | Nullable | Optional description |
| `image` | TEXT | NOT NULL | Docker image tag, e.g. `"registry.io/cvops/trainer:1.4.2"` |
| `icd_config` | JSONB | NOT NULL | Interface-control document — see shape below |
| `icd_schema_version` | TEXT | NOT NULL, default `"1.0"` | Version of the ICD schema itself |

**Unique constraint:** `UNIQUE(project_id, name)`

#### ICD Config Shape

The `icd_config` document defines exactly how the training container receives inputs and exposes outputs. CVOps reads this document at train-step execution time to build the Docker environment.

```json
{
  "inputs": {
    "dataset_path": {"env": "DATASET_PATH"},
    "epochs": {"env": "EPOCHS"}
  },
  "outputs": {
    "metrics_file": {"path": "/output/metrics.json"},
    "weights_path": {"path": "/output/weights/"}
  },
  "volume_mount": "/data/dataset"
}
```

- **`inputs`** — each key maps to an environment variable name (`env`) that the container reads at startup.
- **`outputs`** — paths inside the container where the training process writes its results. CVOps reads these paths after the container exits.
- **`volume_mount`** — the path inside the container where CVOps mounts the dataset volume.

---

### `model_versions`

Extends `EntityBase`.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| *(EntityBase)* | — | `id`, `created_at`, `updated_at` | |
| `project_id` | UUID FK → `projects` | NOT NULL | Owning project |
| `blob_hash` | TEXT FK → `blobs` | NOT NULL | SHA-256 hash of the weights tar.gz |
| `trained_on_commit_id` | UUID FK → `commits` | NOT NULL | Exact dataset snapshot used for training |
| `training_container_id` | UUID FK → `training_containers` | NOT NULL | Container image and ICD that produced this model |
| `base_model` | TEXT | Nullable | Starting checkpoint, e.g. `"yolov8n"`, `"yolov8s"` |
| `hyperparams` | JSONB | Nullable | Training hyperparameters at run time |
| `metrics` | JSONB | Nullable | Output metrics ingested from `metrics_file` |
| `code_version` | TEXT | Nullable | Training code version or git ref |
| `env_hash` | TEXT | Nullable | Hash of the Python/system environment for reproducibility auditing |
| `seed` | INTEGER | Nullable | Random seed passed to the training process |
| `mlflow_run_id` | TEXT | Nullable | MLflow run identifier if experiment tracking is enabled |

---

## Reproducibility

The combination of four fields uniquely specifies how to reproduce a model version:

| Field | What it pins |
|---|---|
| `trained_on_commit_id` | Exact set of samples and labels used |
| `training_container_id` | Docker image tag and ICD config |
| `hyperparams` | All training knobs passed as env vars |
| `seed` | Random number generator state |

Given these four values, any future run of the same container against the same commit should produce bit-for-bit equivalent weights (subject to hardware determinism). All four must be populated before a model version is considered reproducible.

---

## What the `train` Step Does

1. Resolves the dataset commit from the current workflow context (`runs.output_refs` or step inputs).
2. Looks up the `training_container` row to retrieve `image` and `icd_config`.
3. Constructs Docker environment variables from `icd_config.inputs`, injecting dataset path, epoch count, and any hyperparams.
4. Mounts the dataset volume at `icd_config.volume_mount` and runs the container.
5. After the container exits, reads the file at `icd_config.outputs.metrics_file` and parses it as JSON.
6. Uploads the weights directory at `icd_config.outputs.weights_path` as a tar.gz blob.
7. Inserts a `model_versions` row with `trained_on_commit_id` pointing to the resolved commit, `blob_hash` pointing to the uploaded weights, and `metrics` populated from the parsed JSON.

---

## Common Query Patterns

**All models trained on a specific commit:**

```sql
SELECT id, blob_hash, metrics, created_at
FROM model_versions
WHERE trained_on_commit_id = $1
ORDER BY created_at DESC;
```

**Trace the ontology that was active when a model was trained:**

```sql
SELECT o.id, o.name, o.version
FROM model_versions mv
JOIN commits          c  ON c.id         = mv.trained_on_commit_id
JOIN ontologies       o  ON o.id         = c.ontology_id
WHERE mv.id = $1;
```

**Latest model version for a project:**

```sql
SELECT id, blob_hash, trained_on_commit_id, metrics
FROM model_versions
WHERE project_id = $1
ORDER BY created_at DESC
LIMIT 1;
```

---

## What NOT To Do

- **Never use a `model_version` row without checking `trained_on_commit_id`.** That commit defines which label classes the model was trained against. Deploying a model without knowing its commit means you cannot safely map its outputs back to `class_key` values or verify that the ontology still matches.

- **Never change `trained_on_commit_id` after creation.** The row is a permanent record of which dataset produced these weights. Updating this field corrupts the audit trail and invalidates the reproducibility guarantee.

- **Never delete a `training_container` that is referenced by any `model_versions` row.** Removing it breaks the FK and makes it impossible to audit what image produced those weights.
