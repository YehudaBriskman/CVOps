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

import asyncio
import io
import json
import logging
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from collections import deque
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from cvops_api.config import settings
from cvops_api.core.storage import StorageBackend
from cvops_api.db.models.models import ModelVersion, TrainingContainer
from cvops_api.engine.step import Step, StepContext

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 7200  # seconds
_LOG_TAIL_CHARS = 2000
_LOG_TAIL_LINES = 200  # streamed lines kept for error reporting
_VENV_TIMEOUT = 120  # seconds to build the per-run venv
_PIP_TIMEOUT = 600  # seconds to install repo requirements

# Markers the trainer prints on its own stdout so the step can surface live
# progress without waiting for the run to finish. The example trainer emits the
# MLflow parent run + experiment ids the moment it opens the study run, so the
# dashboard can link to MLflow while training is still going.
_MARK_RUN_ID = "CVOPS_MLFLOW_RUN_ID"
_MARK_EXP_ID = "CVOPS_MLFLOW_EXPERIMENT_ID"

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

    # Map hyperparams to env vars via icd_config["inputs"]; any hyperparam
    # without an explicit mapping defaults to an env var named by its uppercased
    # key (e.g. epochs → EPOCHS), so an ad-hoc train needs no container.
    inputs_spec = icd_config.get("inputs", {})
    for param_name, value in hyperparams.items():
        mapping = inputs_spec.get(param_name, {})
        env_name = mapping.get("env", param_name.upper())
        env[env_name] = str(value)

    if dataset_dir is not None:
        env["DATASET_PATH"] = str(dataset_dir)

    mlflow_uri = icd_config.get("mlflow_tracking_uri") or os.environ.get(
        "MLFLOW_TRACKING_URI"
    )
    if mlflow_uri:
        env["MLFLOW_TRACKING_URI"] = mlflow_uri

    env["OUTPUT_DIR"] = str(output_dir)
    return env


async def _run_training(
    repo_dir: Path,
    entry_point: str,
    env: dict[str, str],
    timeout: int,
    python_path: Path,
    on_marker: Callable[[str, str], Awaitable[None]] | None = None,
) -> tuple[int, str]:
    """Run the training script with the per-run venv's interpreter, streaming
    its output line-by-line to the worker log (so a long train is followable in
    `worker-training` logs in real time) instead of buffering until exit.

    stderr is merged into stdout; each line is logged and kept in a bounded tail
    for error reporting. ``CVOPS_MLFLOW_*`` marker lines are forwarded to
    ``on_marker`` as soon as they appear, letting the caller surface live links.

    Returns (returncode, combined_logs_tail[-_LOG_TAIL_CHARS:]).
    """
    script = (repo_dir / entry_point).resolve()
    if not str(script).startswith(str(repo_dir.resolve()) + os.sep):
        raise RuntimeError(f"entry_point escapes repo directory: {entry_point!r}")

    proc = await asyncio.create_subprocess_exec(
        str(python_path),
        str(script),
        cwd=str(repo_dir),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    tail: deque[str] = deque(maxlen=_LOG_TAIL_LINES)

    async def _drain() -> None:
        assert proc.stdout is not None
        async for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace").rstrip("\n")
            logger.info("[train] %s", line)
            tail.append(line)
            if on_marker and line.startswith((_MARK_RUN_ID, _MARK_EXP_ID)) and "=" in line:
                key, _, value = line.partition("=")
                await on_marker(key.strip(), value.strip())
        await proc.wait()

    try:
        await asyncio.wait_for(_drain(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        raise RuntimeError(f"training timed out after {timeout}s") from None

    return proc.returncode or 0, "\n".join(tail)[-_LOG_TAIL_CHARS:]


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

    blob_hash = await ctx.storage.save_bytes(weights_bytes, "application/x-tar")
    # save_bytes only uploads the object; register the blobs row too so the
    # ModelVersion.blob_hash FK (fk_model_versions_blob_hash) resolves. Mirrors
    # export_yolo's blob registration. ON CONFLICT keeps re-runs idempotent.
    await ctx.session.execute(
        text(
            "INSERT INTO blobs (hash, storage_backend, storage_key, "
            "size_bytes, media_type) VALUES (:h, :sb, :sk, :sz, :mt) "
            "ON CONFLICT (hash) DO NOTHING"
        ),
        {
            "h": blob_hash,
            "sb": settings.S3_BACKEND,
            "sk": StorageBackend._bucket_key(blob_hash),
            "sz": len(weights_bytes),
            "mt": "application/x-tar",
        },
    )
    return blob_hash


async def _write_model_version(
    ctx: StepContext,
    tc: TrainingContainer | None,
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
        training_container_id=tc.id if tc is not None else None,
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
        tc_id: str | None = config.get("training_container_id")
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

        # 1. Load TrainingContainer (optional — ad-hoc trains have none, and
        #    fall back to default env mapping + output paths).
        tc: TrainingContainer | None = None
        icd_config: dict[str, Any] = {}
        if tc_id:
            tc = await _load_training_container(ctx.session, tc_id)
            icd_config = tc.icd_config

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

            # 6. Run training, surfacing the MLflow run as soon as the trainer
            #    opens it. Persisting to runs.metrics here also commits the
            #    'running' transition the runner left uncommitted (and releases
            #    the run-row lock), so the dashboard can link to MLflow and
            #    follow along live rather than only seeing the final result.
            live: dict[str, str] = {}

            async def _on_marker(key: str, value: str) -> None:
                field = {
                    _MARK_RUN_ID: "mlflow_run_id",
                    _MARK_EXP_ID: "mlflow_experiment_id",
                }.get(key)
                if not field or not value:
                    return
                live[field] = value
                await ctx.session.execute(
                    text(
                        "UPDATE runs SET metrics = "
                        "COALESCE(metrics, '{}'::jsonb) || CAST(:m AS jsonb) "
                        "WHERE id = CAST(:i AS uuid)"
                    ),
                    {"m": json.dumps(live), "i": ctx.run_id},
                )
                await ctx.session.commit()

            returncode, logs = await _run_training(
                repo_dir, entry_point, env, timeout, venv_python, _on_marker
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
