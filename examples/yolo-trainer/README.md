# CVOps example trainer — YOLO + Optuna + MLflow

A reference trainer repo for the CVOps `step.train` step. It runs an
[Optuna](https://optuna.org/) hyperparameter search over short
[ultralytics YOLO](https://docs.ultralytics.com/) trainings on an exported
dataset, logs every trial to MLflow, and hands the best model back to CVOps.

## How CVOps runs it

`step.train` (the `training`-queue worker) does, per run:

1. Downloads the dataset (`step.export_yolo` output) and extracts it.
2. `git clone` this repo.
3. `python -m venv --system-site-packages` (so the worker image's
   torch/ultralytics/mlflow are visible) and `pip install -r requirements.txt`
   (installs `optuna`).
4. Runs `python train.py` with the contract below.
5. Reads back `weights/best.pt` and `metrics.json`, uploads the weights, and
   creates a `ModelVersion`.

## Contract

**Inputs (environment variables):**

| Var | Meaning |
|---|---|
| `DATASET_PATH` | Extracted YOLO export: `data.yaml`, `images/{train,val[,test]}/`, `labels/...` |
| `OUTPUT_DIR` | Where to write outputs |
| `MLFLOW_TRACKING_URI` | MLflow server (optional) |
| `N_TRIALS` | Optuna trials (default 5) |
| `EPOCHS` | Epochs per trial (default 3) |
| `IMGSZ` | Image size (default 640) |
| `MODEL` | Base model (default `yolov8n.pt`) |

`N_TRIALS`/`EPOCHS`/`IMGSZ`/`MODEL` come from the **Train dialog's
hyperparameters** (the step upper-cases keys → env vars).

**Outputs (written to `OUTPUT_DIR`):**

| Path | Meaning |
|---|---|
| `weights/best.pt` | Best model across all trials (required, non-empty) |
| `metrics.json` | `{map50_95, best_params, n_trials, mlflow_run_id}` |

`mlflow_run_id` is the parent **study** run; each Optuna trial is a nested run
under it (sampled params + that trial's `map50_95`). CVOps pins this id on the
`ModelVersion`, so "View in MLflow" opens the study.

## Use it

1. Push this directory as its own git repo (e.g. GitHub).
2. In CVOps: open a dataset commit → **Train** → set **Git repository URL** to
   the repo, **Entry point** `train.py`, and hyperparameters e.g. `n_trials=2`,
   `epochs=1` for a quick smoke run.
3. Watch the run; the resulting model version links to the MLflow study.

> Note: needs a `val` split for a meaningful HPO metric — it falls back to
> validating on `train` (and warns) if the export has none.
