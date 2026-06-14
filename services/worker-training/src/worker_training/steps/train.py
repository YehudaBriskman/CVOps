from __future__ import annotations

import io
import json
import logging
import os
import shutil
import subprocess
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
        tf.extractall(dataset_dir)  # noqa: S202 — controlled path from trusted MinIO

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
        raise RuntimeError(f"git clone failed: {stderr[-500:]}")
    return repo_dir


def _install_requirements(repo_dir: Path) -> None:
    req_file = repo_dir / "requirements.txt"
    if not req_file.exists():
        return
    result = subprocess.run(  # noqa: S603
        ["pip", "install", "-r", str(req_file)],
        capture_output=True,
        timeout=600,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"pip install failed: {stderr[-500:]}")


def _build_env(
    icd_config: dict[str, Any],
    hyperparams: dict[str, Any],
    dataset_dir: Path | None,
    output_dir: Path,
) -> dict[str, str]:
    """Build the subprocess environment from icd_config input mappings."""
    env = {**os.environ}

    # Map hyperparams to env vars via icd_config["inputs"]
    inputs_spec = icd_config.get("inputs", {})
    for param_name, mapping in inputs_spec.items():
        if "env" in mapping and param_name in hyperparams:
            env[mapping["env"]] = str(hyperparams[param_name])

    if dataset_dir is not None:
        env["DATASET_PATH"] = str(dataset_dir)

    mlflow_uri = icd_config.get("mlflow_tracking_uri")
    if mlflow_uri:
        env["MLFLOW_TRACKING_URI"] = mlflow_uri

    env["OUTPUT_DIR"] = str(output_dir)
    return env


def _run_training(
    repo_dir: Path,
    entry_point: str,
    env: dict[str, str],
    timeout: int,
) -> tuple[int, str]:
    """Run the training script. Returns (returncode, combined_logs[-500:])."""
    script = repo_dir / entry_point
    result = subprocess.run(  # noqa: S603
        ["python", str(script)],
        env=env,
        capture_output=True,
        timeout=timeout,
    )
    logs = (result.stdout + result.stderr).decode("utf-8", errors="replace")[-500:]
    return result.returncode, logs


def _read_metrics(output_dir: Path, metrics_path_spec: str) -> dict[str, Any]:
    """Parse metrics.json from the output directory.

    `metrics_path_spec` is the value from icd_config["outputs"]["metrics_file"]["path"],
    e.g. "/output/metrics.json". We use only the basename and look in output_dir.
    """
    # Resolve the path: if the spec is relative, join to output_dir; if absolute,
    # rebase the filename into output_dir (the script writes to its own /output/).
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
    # Rebase into output_dir
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
    mlflow_run_id: str | None = metrics.pop("mlflow_run_id", None)
    mv = ModelVersion(
        project_id=UUID(ctx.project_id),
        blob_hash=weights_blob_hash,
        trained_on_commit_id=UUID(commit_id),
        training_container_id=tc.id,
        hyperparams=hyperparams or None,
        metrics=metrics or None,
        mlflow_run_id=mlflow_run_id,
        seed=hyperparams.get("seed"),
    )
    ctx.session.add(mv)
    await ctx.session.flush()
    return str(mv.id)


# ── Step implementation ────────────────────────────────────────────────────


class TrainStep(Step):
    type_key = "step.train"
    config_schema = {
        "type": "object",
        "properties": {
            "training_container_id": {"type": "string"},
            "git_url": {"type": "string"},
            "branch": {"type": "string"},
            "entry_point": {"type": "string"},
            "hyperparams": {"type": "object"},
            "commit_id": {"type": "string"},
        },
        "required": ["training_container_id", "git_url", "commit_id"],
    }

    async def run(
        self, ctx: StepContext, config: dict[str, Any], inputs: dict[str, Any]
    ) -> dict[str, Any]:
        tc_id = config["training_container_id"]
        git_url = config["git_url"]
        branch: str | None = config.get("branch")
        entry_point: str = config.get("entry_point", "train.py")
        hyperparams: dict[str, Any] = config.get("hyperparams") or {}
        commit_id = config["commit_id"]
        export_blob_hash: str | None = inputs.get("export_blob_hash")

        timeout = int(os.environ.get("DOCKER_TIMEOUT", _DEFAULT_TIMEOUT))

        # 1. Load TrainingContainer
        tc = await _load_training_container(ctx.session, tc_id)
        icd_config: dict[str, Any] = tc.icd_config

        workdir = Path(tempfile.mkdtemp())
        try:
            # 2. Download dataset (optional)
            dataset_dir = await _download_dataset(ctx, export_blob_hash, workdir)

            # 3. Clone repo
            repo_dir = _clone_repo(git_url, branch, workdir)

            # 4. Install requirements
            _install_requirements(repo_dir)

            # 5. Build env
            output_dir = workdir / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            env = _build_env(icd_config, hyperparams, dataset_dir, output_dir)

            # 6. Run training
            returncode, logs = _run_training(repo_dir, entry_point, env, timeout)

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
