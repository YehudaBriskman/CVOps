"""train — clone a trainer repo and run it against an exported dataset commit.

The canonical, registry-backed implementation of ``step.train``. The API process
imports this for its config schema / queue routing; the ``worker-training`` service
imports the same class to execute it (see ``services/worker-training``).

Execution model (no privileged Docker required): for each run the worker

1. downloads + extracts the YOLO dataset tar.gz (``export_blob_hash`` input),
2. ``git clone``s ``git_url`` (optional ``branch``),
3. creates a **throwaway venv with ``--system-site-packages``** so the worker's
   global packages (torch, ultralytics, mlflow, …) are visible and the repo's
   ``requirements.txt`` is layered *on top* into the venv only,
4. runs the repo's ``entry_point`` with that venv's interpreter, passing
   ``DATASET_PATH`` / ``OUTPUT_DIR`` / ``MLFLOW_TRACKING_URI`` and the
   hyperparam→env mapping from ``training_containers.icd_config``,
5. reads ``metrics.json``, uploads the weights dir as a content-addressed blob,
   and writes a ``ModelVersion`` row (with ``mlflow_run_id`` if the script emits it).

The whole workdir — venv included — is removed afterwards, so each train is
isolated and disposable without spawning containers.
"""

from __future__ import annotations

import io
import json
import logging
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cvops_api.db.models.models import ModelVersion, TrainingContainer
from cvops_api.engine.step import Step, StepContext

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 7200  # seconds
_LOG_TAIL_CHARS = 2000
_VENV_TIMEOUT = 120  # seconds to build the per-run venv
_PIP_TIMEOUT = 600  # seconds to install repo requirements

with open(Path(__file__).parent / "schemas" / "train.json") as _f:
    _SCHEMA = json.load(_f)


# ── Helpers ────────────────────────────────────────────────────────────────


async def _load_training_container(
    session: AsyncSession, tc_id: str
) -> TrainingContainer:
    result = await session.execute(
        select(TrainingContainer).where(TrainingContainer.id == UUID(tc_id))  # type: ignore[arg-type]
    )
    tc = result.scalar_one_or_none()
    if tc is None:
        raise RuntimeError(f"TrainingContainer {tc_id!r} not found")
    return tc


async def _download_dataset(
    ctx: StepContext, export_blob_hash: str | None, workdir: Path
) -> Path | None:
    """Download and extract dataset tar.gz. Returns dataset dir or None."""
    if not export_blob_hash:
        return None

    data = await ctx.storage.get_bytes(export_blob_hash)
    dataset_dir = workdir / "dataset"
    dataset_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        tf.extractall(dataset_dir, filter="data")  # noqa: S202 — controlled path from trusted MinIO

    return dataset_dir


def _clone_repo(git_url: str, branch: str | None, workdir: Path) -> Path:
    repo_dir = workdir / "repo"
    cmd = ["git", "clone"]
    if branch:
        cmd += ["--branch", branch]
    cmd += [git_url, str(repo_dir)]
    result = subprocess.run(cmd, capture_output=True, timeout=300)  # noqa: S603
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"git clone failed: {stderr[-_LOG_TAIL_CHARS:]}")
    return repo_dir


def _create_venv(workdir: Path) -> tuple[Path, Path]:
    """Create a throwaway venv that inherits the worker's global packages.

    ``--system-site-packages`` means torch/ultralytics/mlflow installed in the
    worker image are visible without re-installing; the repo's requirements are
    layered into this venv only and discarded with the workdir. Returns
    (python_path, pip_path) for the new venv.
    """
    venv_dir = workdir / "venv"
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "venv", "--system-site-packages", str(venv_dir)],
        capture_output=True,
        timeout=_VENV_TIMEOUT,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"venv creation failed: {stderr[-_LOG_TAIL_CHARS:]}")
    bin_dir = venv_dir / ("Scripts" if os.name == "nt" else "bin")
    return bin_dir / "python", bin_dir / "pip"


def _install_requirements(repo_dir: Path, pip_path: Path) -> None:
    """Layer the repo's requirements.txt into the per-run venv (no-op if absent)."""
    req_file = repo_dir / "requirements.txt"
    if not req_file.exists():
        return
    result = subprocess.run(  # noqa: S603
        [str(pip_path), "install", "-r", str(req_file)],
        capture_output=True,
        timeout=_PIP_TIMEOUT,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"pip install failed: {stderr[-_LOG_TAIL_CHARS:]}")


def _build_env(
    icd_config: dict[str, Any],
    hyperparams: dict[str, Any],
    dataset_dir: Path | None,
    output_dir: Path,
    venv_python: Path | None = None,
) -> dict[str, str]:
    """Build the subprocess environment from icd_config input mappings."""
    env = {**os.environ}

    # Activate the per-run venv for the training process and anything it spawns.
    if venv_python is not None:
        bin_dir = str(venv_python.parent)
        env["VIRTUAL_ENV"] = str(venv_python.parent.parent)
        env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
        env.pop("PYTHONHOME", None)

    # Map hyperparams to env vars via icd_config["inputs"]
    inputs_spec = icd_config.get("inputs", {})
    for param_name, mapping in inputs_spec.items():
        if "env" in mapping and param_name in hyperparams:
            env[mapping["env"]] = str(hyperparams[param_name])

    if dataset_dir is not None:
        env["DATASET_PATH"] = str(dataset_dir)

    mlflow_uri = icd_config.get("mlflow_tracking_uri") or os.environ.get(
        "MLFLOW_TRACKING_URI"
    )
    if mlflow_uri:
        env["MLFLOW_TRACKING_URI"] = mlflow_uri

    env["OUTPUT_DIR"] = str(output_dir)
    return env


def _run_training(
    repo_dir: Path,
    entry_point: str,
    env: dict[str, str],
    timeout: int,
    python_path: Path,
) -> tuple[int, str]:
    """Run the training script with the per-run venv's interpreter.

    Returns (returncode, combined_logs[-_LOG_TAIL_CHARS:]).
    """
    script = (repo_dir / entry_point).resolve()
    if not str(script).startswith(str(repo_dir.resolve()) + "/"):
        raise RuntimeError(f"entry_point escapes repo directory: {entry_point!r}")
    result = subprocess.run(  # noqa: S603
        [str(python_path), str(script)],
        env=env,
        cwd=str(repo_dir),
        capture_output=True,
        timeout=timeout,
    )
    logs = (result.stdout + result.stderr).decode("utf-8", errors="replace")[-_LOG_TAIL_CHARS:]
    return result.returncode, logs


def _read_metrics(output_dir: Path, metrics_path_spec: str) -> dict[str, Any]:
    """Parse metrics.json from the output directory.

    `metrics_path_spec` is the value from icd_config["outputs"]["metrics_file"]["path"],
    e.g. "/output/metrics.json". We use only the basename and look in output_dir.
    """
    spec = Path(metrics_path_spec)
    metrics_file = output_dir / spec.name

    if not metrics_file.exists():
        raise RuntimeError("metrics.json not found")

    with metrics_file.open() as fh:
        return json.load(fh)  # type: ignore[no-any-return]


async def _upload_weights(
    ctx: StepContext, output_dir: Path, weights_path_spec: str
) -> str:
    """Tar the weights directory and upload to storage. Returns blob_hash."""
    spec = Path(weights_path_spec)
    weights_dir = output_dir / spec.name

    if not weights_dir.exists() or not any(weights_dir.iterdir()):
        raise RuntimeError("weights not found")

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        tf.add(str(weights_dir), arcname=weights_dir.name)
    weights_bytes = buf.getvalue()

    return await ctx.storage.save_bytes(weights_bytes, "application/x-tar")


async def _write_model_version(
    ctx: StepContext,
    tc: TrainingContainer,
    commit_id: str,
    weights_blob_hash: str,
    metrics: dict[str, Any],
    hyperparams: dict[str, Any],
) -> str:
    """Insert ModelVersion row. Returns str(mv.id)."""
    mlflow_run_id: str | None = metrics.get("mlflow_run_id")
    clean_metrics = {k: v for k, v in metrics.items() if k != "mlflow_run_id"}
    mv = ModelVersion(
        project_id=UUID(ctx.project_id),
        blob_hash=weights_blob_hash,
        trained_on_commit_id=UUID(commit_id),
        training_container_id=tc.id,
        hyperparams=hyperparams or None,
        metrics=clean_metrics or None,
        mlflow_run_id=mlflow_run_id,
        seed=hyperparams.get("seed"),
    )
    ctx.session.add(mv)
    await ctx.session.flush()
    return str(mv.id)


# ── Step implementation ────────────────────────────────────────────────────


class TrainStep(Step):
    type_key = "step.train"
    config_schema = _SCHEMA
    queue = "training"

    async def run(
        self, ctx: StepContext, config: dict[str, Any], inputs: dict[str, Any]
    ) -> dict[str, Any]:
        tc_id = config["training_container_id"]
        git_url = config["git_url"]
        branch: str | None = config.get("branch")
        entry_point: str = config.get("entry_point", "train.py")
        hyperparams: dict[str, Any] = config.get("hyperparams") or {}
        export_blob_hash: str | None = inputs.get("export_blob_hash")
        # commit_id flows in from the upstream export step's outputs (wired as
        # $steps.<export>.outputs.commit_id), not config — it's a runtime value.
        # It anchors reproducibility (ModelVersion.trained_on_commit_id, NOT NULL).
        commit_id: str | None = inputs.get("commit_id")
        if not commit_id:
            raise RuntimeError(
                "step.train requires a 'commit_id' input — wire it from the export "
                "step, e.g. inputs.commit_id = $steps.<export>.outputs.commit_id"
            )

        timeout = int(os.environ.get("TRAINING_TIMEOUT", _DEFAULT_TIMEOUT))

        # 1. Load TrainingContainer
        tc = await _load_training_container(ctx.session, tc_id)
        icd_config: dict[str, Any] = tc.icd_config

        workdir = Path(tempfile.mkdtemp())
        try:
            # 2. Download dataset (optional)
            dataset_dir = await _download_dataset(ctx, export_blob_hash, workdir)

            # 3. Clone repo
            repo_dir = _clone_repo(git_url, branch, workdir)

            # 4. Per-run venv (inherits global packages) + repo requirements
            venv_python, venv_pip = _create_venv(workdir)
            _install_requirements(repo_dir, venv_pip)

            # 5. Build env
            output_dir = workdir / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            env = _build_env(icd_config, hyperparams, dataset_dir, output_dir, venv_python)

            # 6. Run training
            returncode, logs = _run_training(
                repo_dir, entry_point, env, timeout, venv_python
            )

            # 7. Handle result
            if returncode != 0:
                raise RuntimeError(logs)

            # 8a. Read metrics
            metrics_path_spec = (
                icd_config.get("outputs", {})
                .get("metrics_file", {})
                .get("path", "/output/metrics.json")
            )
            metrics = _read_metrics(output_dir, metrics_path_spec)

            # 8b. Upload weights
            weights_path_spec = (
                icd_config.get("outputs", {})
                .get("weights_path", {})
                .get("path", "/output/weights/")
            )
            weights_blob_hash = await _upload_weights(ctx, output_dir, weights_path_spec)

            # 8c. Write ModelVersion
            model_version_id = await _write_model_version(
                ctx, tc, commit_id, weights_blob_hash, metrics, hyperparams
            )

            # 8d. Emit event
            await ctx.emit_event(
                actor_id=ctx.actor_id,
                actor_type="service",
                entity_type="run",
                entity_id=ctx.run_id,
                action="train.completed",
                payload={"model_version_id": model_version_id},
            )

            return {"model_version_id": model_version_id}

        finally:
            try:
                shutil.rmtree(workdir, ignore_errors=True)
            except Exception as exc:  # pragma: no cover
                logger.warning("Failed to clean up workdir %s: %s", workdir, exc)
