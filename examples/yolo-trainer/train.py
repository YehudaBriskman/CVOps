"""Example CVOps trainer: Optuna HPO over ultralytics YOLO, logged to MLflow.

This is a reference trainer repo for CVOps `step.train`. The step clones this
repo, makes a venv (with torch/ultralytics/mlflow visible from the worker image
via --system-site-packages), `pip install -r requirements.txt` (installs optuna),
then runs this file with the contract below.

CONTRACT — CVOps passes these as environment variables:
  DATASET_PATH         extracted YOLO export: data.yaml, images/{train,val[,test]}/, labels/...
  OUTPUT_DIR           write weights/ and metrics.json here
  MLFLOW_TRACKING_URI  MLflow server (optional; if unset, MLflow logs locally)
  hyperparams (upper-cased)  N_TRIALS, EPOCHS, IMGSZ, MODEL  (from the Train dialog)

PRODUCES — CVOps reads these back to create a ModelVersion:
  {OUTPUT_DIR}/weights/best.pt   best model across all Optuna trials
  {OUTPUT_DIR}/metrics.json      {map50_95, best_params, n_trials, mlflow_run_id}

MLflow layout: one parent "optuna-study" run with each trial nested under it;
metrics.json pins the parent run id so the dashboard's "View in MLflow" opens it.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import mlflow
import optuna
import yaml
from ultralytics import YOLO, settings

# Drive MLflow logging explicitly (nested per trial) — disable ultralytics' own
# autolog so we don't get duplicate, un-nested runs.
settings.update({"mlflow": False})

OUTPUT_DIR = Path(os.environ["OUTPUT_DIR"])
DATASET_PATH = Path(os.environ["DATASET_PATH"])
N_TRIALS = int(os.environ.get("N_TRIALS", "5"))
EPOCHS = int(os.environ.get("EPOCHS", "3"))
IMGSZ = int(os.environ.get("IMGSZ", "640"))
MODEL = os.environ.get("MODEL", "yolov8n.pt")
TRIALS_DIR = OUTPUT_DIR / "trials"


def build_data_yaml() -> Path:
    """Normalize the export's data.yaml into an ultralytics-ready one: absolute
    `path`, explicit train/val, names carried over. Falls back to train-as-val
    when the export has no val split (HPO still needs a metric)."""
    src = yaml.safe_load((DATASET_PATH / "data.yaml").read_text())
    val_dir = DATASET_PATH / "images" / "val"
    has_val = val_dir.is_dir() and any(val_dir.iterdir())
    if not has_val:
        print("WARNING: export has no val split — validating on train; HPO metric is optimistic.")
    data = {
        "path": str(DATASET_PATH),
        "train": "images/train",
        "val": "images/val" if has_val else "images/train",
        "names": src.get("names"),
    }
    out = OUTPUT_DIR / "data.yaml"
    out.write_text(yaml.safe_dump(data))
    return out


def objective(trial: optuna.Trial, data_yaml: Path) -> float:
    params = {
        "lr0": trial.suggest_float("lr0", 1e-4, 1e-1, log=True),
        "momentum": trial.suggest_float("momentum", 0.85, 0.98),
        "weight_decay": trial.suggest_float("weight_decay", 1e-5, 1e-2, log=True),
        "optimizer": trial.suggest_categorical("optimizer", ["SGD", "Adam", "AdamW"]),
    }
    with mlflow.start_run(run_name=f"trial-{trial.number}", nested=True):
        mlflow.log_params({**params, "epochs": EPOCHS, "imgsz": IMGSZ, "model": MODEL})
        results = YOLO(MODEL).train(
            data=str(data_yaml),
            epochs=EPOCHS,
            imgsz=IMGSZ,
            project=str(TRIALS_DIR),
            name=f"t{trial.number}",
            exist_ok=True,
            verbose=False,
            **params,
        )
        score = float(results.box.map)  # mAP50-95
        mlflow.log_metric("map50_95", score)
        trial.set_user_attr("weights", str(TRIALS_DIR / f"t{trial.number}" / "weights" / "best.pt"))
    return score


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if os.environ.get("MLFLOW_TRACKING_URI"):
        mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
    mlflow.set_experiment("cvops-yolo-hpo")

    data_yaml = build_data_yaml()

    with mlflow.start_run(run_name="optuna-study") as parent:
        run_id = parent.info.run_id
        study = optuna.create_study(direction="maximize")
        study.optimize(lambda t: objective(t, data_yaml), n_trials=N_TRIALS)

        mlflow.log_params({f"best_{k}": v for k, v in study.best_params.items()})
        mlflow.log_metric("best_map50_95", study.best_value)

        best_weights = Path(study.best_trial.user_attrs["weights"])
        if not best_weights.exists():
            raise RuntimeError(f"best trial produced no weights at {best_weights}")
        weights_dir = OUTPUT_DIR / "weights"
        weights_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(best_weights, weights_dir / "best.pt")
        mlflow.log_artifacts(str(weights_dir), artifact_path="weights")

    (OUTPUT_DIR / "metrics.json").write_text(
        json.dumps(
            {
                "map50_95": study.best_value,
                "best_params": study.best_params,
                "n_trials": N_TRIALS,
                "mlflow_run_id": run_id,
            }
        )
    )
    print(f"Best mAP50-95={study.best_value:.4f} params={study.best_params}")


if __name__ == "__main__":
    main()
