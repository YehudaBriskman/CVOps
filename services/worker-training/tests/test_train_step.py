from __future__ import annotations

import io
import json
import tarfile
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from cvops_steps.train import (
    TrainStep,
    _build_env,
    _download_dataset,
    _read_metrics,
    _upload_weights,
    _write_model_version,
)


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_weights_tar(weights_dir: Path) -> bytes:
    """Create a fake weights tar.gz from a directory."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        tf.add(str(weights_dir), arcname=weights_dir.name)
    return buf.getvalue()


# ── Test: step metadata (registry/routing contract) ─────────────────────────


def test_train_step_routes_to_training_queue():
    # The API registers this same class; queue drives coordinator XADD routing.
    assert TrainStep.queue == "training"


def test_train_config_schema_requires_repo_fields():
    required = set(TrainStep.config_schema["required"])
    assert {"training_container_id", "git_url"} <= required
    # Schema and implementation agree on the repo-based contract.
    assert "git_url" in TrainStep.config_schema["properties"]
    assert "entry_point" in TrainStep.config_schema["properties"]
    # commit_id is a runtime value wired from the export edge, not config.
    assert "commit_id" not in TrainStep.config_schema["properties"]
    assert "commit_id" not in required


# ── Test: _download_dataset ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_download_dataset_extracts_to_tmpdir(ctx, base_inputs, tmp_path):
    dataset_dir = await _download_dataset(ctx, base_inputs["export_blob_hash"], tmp_path)

    ctx.storage.get_bytes.assert_awaited_once_with("sha256:exportdeadbeef")
    assert dataset_dir is not None
    assert dataset_dir.exists()
    assert dataset_dir == tmp_path / "dataset"
    assert (dataset_dir / "images" / "train" / "img.jpg").exists()


@pytest.mark.asyncio
async def test_download_dataset_returns_none_if_no_hash(ctx, tmp_path):
    dataset_dir = await _download_dataset(ctx, None, tmp_path)

    ctx.storage.get_bytes.assert_not_awaited()
    assert dataset_dir is None


# ── Test: _build_env ───────────────────────────────────────────────────────


def test_build_env_maps_hyperparams(tmp_path):
    icd_config = {
        "inputs": {
            "epochs": {"env": "EPOCHS"},
            "batch_size": {"env": "BATCH_SIZE"},
        },
        "outputs": {},
    }
    hyperparams = {"epochs": 10, "batch_size": 16}
    output_dir = tmp_path / "output"

    env = _build_env(icd_config, hyperparams, dataset_dir=None, output_dir=output_dir)

    assert env["EPOCHS"] == "10"
    assert env["BATCH_SIZE"] == "16"
    assert env["OUTPUT_DIR"] == str(output_dir)


def test_build_env_includes_mlflow_uri(tmp_path):
    icd_config = {
        "inputs": {},
        "outputs": {},
        "mlflow_tracking_uri": "http://mlflow:5000",
    }
    output_dir = tmp_path / "output"

    env = _build_env(icd_config, hyperparams={}, dataset_dir=None, output_dir=output_dir)

    assert env["MLFLOW_TRACKING_URI"] == "http://mlflow:5000"


def test_build_env_does_not_include_mlflow_if_none(tmp_path, monkeypatch):
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    icd_config = {
        "inputs": {},
        "outputs": {},
        "mlflow_tracking_uri": None,
    }
    output_dir = tmp_path / "output"

    env = _build_env(icd_config, hyperparams={}, dataset_dir=None, output_dir=output_dir)

    assert "MLFLOW_TRACKING_URI" not in env


def test_build_env_mlflow_falls_back_to_worker_environ(tmp_path, monkeypatch):
    # Centralized config: a worker-wide MLFLOW_TRACKING_URI applies when the
    # training container's icd_config doesn't pin its own.
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://central-mlflow:5000")
    icd_config = {"inputs": {}, "outputs": {}}
    output_dir = tmp_path / "output"

    env = _build_env(icd_config, hyperparams={}, dataset_dir=None, output_dir=output_dir)

    assert env["MLFLOW_TRACKING_URI"] == "http://central-mlflow:5000"


def test_build_env_activates_per_run_venv(tmp_path):
    icd_config = {"inputs": {}, "outputs": {}}
    output_dir = tmp_path / "output"
    venv_python = tmp_path / "venv" / "bin" / "python"

    env = _build_env(
        icd_config, hyperparams={}, dataset_dir=None, output_dir=output_dir,
        venv_python=venv_python,
    )

    assert env["VIRTUAL_ENV"] == str(tmp_path / "venv")
    assert env["PATH"].startswith(str(tmp_path / "venv" / "bin"))


def test_build_env_includes_dataset_path(tmp_path):
    icd_config = {"inputs": {}, "outputs": {}}
    dataset_dir = tmp_path / "dataset"
    output_dir = tmp_path / "output"

    env = _build_env(icd_config, hyperparams={}, dataset_dir=dataset_dir, output_dir=output_dir)

    assert env["DATASET_PATH"] == str(dataset_dir)


def test_build_env_no_dataset_path_if_none(tmp_path):
    icd_config = {"inputs": {}, "outputs": {}}
    output_dir = tmp_path / "output"

    env = _build_env(icd_config, hyperparams={}, dataset_dir=None, output_dir=output_dir)

    assert "DATASET_PATH" not in env


# ── Test: _read_metrics ────────────────────────────────────────────────────


def test_read_metrics_parses_json(tmp_path):
    metrics_data = {"accuracy": 0.95, "loss": 0.05}
    metrics_file = tmp_path / "metrics.json"
    metrics_file.write_text(json.dumps(metrics_data))

    result = _read_metrics(tmp_path, "/output/metrics.json")

    assert result == metrics_data


def test_read_metrics_raises_if_missing(tmp_path):
    with pytest.raises(RuntimeError, match="metrics.json not found"):
        _read_metrics(tmp_path, "/output/metrics.json")


# ── Test: _upload_weights ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_weights_returns_blob_hash(ctx, tmp_path):
    weights_dir = tmp_path / "weights"
    weights_dir.mkdir()
    (weights_dir / "model.pt").write_bytes(b"fake-weights")

    result = await _upload_weights(ctx, tmp_path, "/output/weights/")

    ctx.storage.save_bytes.assert_awaited_once()
    call_kwargs = ctx.storage.save_bytes.call_args
    assert call_kwargs[0][1] == "application/x-tar"
    assert result == "sha256:abc123deadbeef"


@pytest.mark.asyncio
async def test_upload_weights_raises_if_missing(ctx, tmp_path):
    with pytest.raises(RuntimeError, match="weights not found"):
        await _upload_weights(ctx, tmp_path, "/output/weights/")


@pytest.mark.asyncio
async def test_upload_weights_raises_if_empty_dir(ctx, tmp_path):
    weights_dir = tmp_path / "weights"
    weights_dir.mkdir()
    # Directory exists but is empty

    with pytest.raises(RuntimeError, match="weights not found"):
        await _upload_weights(ctx, tmp_path, "/output/weights/")


# ── Test: _write_model_version ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_write_model_version_inserts_row(ctx, mock_tc, commit_id):
    from cvops_api.db.models.models import ModelVersion

    await _write_model_version(
        ctx,
        tc=mock_tc,
        commit_id=commit_id,
        weights_blob_hash="sha256:abc123deadbeef",
        metrics={"accuracy": 0.9},
        hyperparams={"epochs": 10, "seed": 42},
    )

    ctx.session.add.assert_called_once()
    ctx.session.flush.assert_awaited_once()

    added_obj = ctx.session.add.call_args[0][0]
    assert isinstance(added_obj, ModelVersion)
    assert added_obj.blob_hash == "sha256:abc123deadbeef"
    assert added_obj.trained_on_commit_id == uuid.UUID(commit_id)
    assert added_obj.training_container_id == mock_tc.id
    assert added_obj.seed == 42


@pytest.mark.asyncio
async def test_write_model_version_extracts_mlflow_run_id(ctx, mock_tc, commit_id):
    from cvops_api.db.models.models import ModelVersion

    metrics = {"accuracy": 0.9, "mlflow_run_id": "mlflow-run-abc"}
    await _write_model_version(
        ctx,
        tc=mock_tc,
        commit_id=commit_id,
        weights_blob_hash="sha256:abc123deadbeef",
        metrics=metrics,
        hyperparams={},
    )

    added_obj = ctx.session.add.call_args[0][0]
    assert isinstance(added_obj, ModelVersion)
    assert added_obj.mlflow_run_id == "mlflow-run-abc"
    # mlflow_run_id is extracted into its own column; metrics stored without it
    assert "mlflow_run_id" not in added_obj.metrics


# ── Test: TrainStep.run() — integration-level with mocked subprocesses ────


@pytest.mark.asyncio
async def test_run_nonzero_exit_raises_runtime_error(ctx, base_config, base_inputs, mock_tc, tmp_path):
    """Non-zero exit code from the training script raises RuntimeError."""
    venv = (tmp_path / "venv" / "bin" / "python", tmp_path / "venv" / "bin" / "pip")
    with (
        patch("cvops_steps.train._load_training_container", new=AsyncMock(return_value=mock_tc)),
        patch("cvops_steps.train._download_dataset", new=AsyncMock(return_value=None)),
        patch("cvops_steps.train._clone_repo", return_value=tmp_path / "repo"),
        patch("cvops_steps.train._create_venv", return_value=venv),
        patch("cvops_steps.train._install_requirements"),
        patch("cvops_steps.train._run_training", return_value=(1, "crash log output")),
        patch("tempfile.mkdtemp", return_value=str(tmp_path)),
        patch("cvops_steps.train.shutil.rmtree"),
    ):
        step = TrainStep()
        with pytest.raises(RuntimeError, match="crash log output"):
            await step.run(ctx, base_config, base_inputs)


@pytest.mark.asyncio
async def test_run_cleans_up_tmpdir_on_failure(ctx, base_config, base_inputs, mock_tc, tmp_path):
    """shutil.rmtree is called on the workdir even when training fails."""
    venv = (tmp_path / "venv" / "bin" / "python", tmp_path / "venv" / "bin" / "pip")
    with (
        patch("cvops_steps.train._load_training_container", new=AsyncMock(return_value=mock_tc)),
        patch("cvops_steps.train._download_dataset", new=AsyncMock(return_value=None)),
        patch("cvops_steps.train._clone_repo", return_value=tmp_path / "repo"),
        patch("cvops_steps.train._create_venv", return_value=venv),
        patch("cvops_steps.train._install_requirements"),
        patch("cvops_steps.train._run_training", return_value=(1, "error")),
        patch("tempfile.mkdtemp", return_value=str(tmp_path)),
        patch("cvops_steps.train.shutil.rmtree") as mock_rmtree,
    ):
        step = TrainStep()
        with pytest.raises(RuntimeError):
            await step.run(ctx, base_config, base_inputs)

        mock_rmtree.assert_called_once_with(tmp_path, ignore_errors=True)


@pytest.mark.asyncio
async def test_run_cleans_up_tmpdir_on_success(ctx, base_config, base_inputs, tmp_path, mock_tc):
    """shutil.rmtree is called even when training succeeds."""
    model_version_id = str(uuid.uuid4())
    venv = (tmp_path / "venv" / "bin" / "python", tmp_path / "venv" / "bin" / "pip")

    with (
        patch("cvops_steps.train._load_training_container", new=AsyncMock(return_value=mock_tc)),
        patch("cvops_steps.train._download_dataset", new=AsyncMock(return_value=None)),
        patch("cvops_steps.train._clone_repo", return_value=tmp_path / "repo"),
        patch("cvops_steps.train._create_venv", return_value=venv),
        patch("cvops_steps.train._install_requirements"),
        patch("cvops_steps.train._run_training", return_value=(0, "")),
        patch("cvops_steps.train._read_metrics", return_value={"accuracy": 0.9}),
        patch("cvops_steps.train._upload_weights", new=AsyncMock(return_value="sha256:abc")),
        patch("cvops_steps.train._write_model_version", new=AsyncMock(return_value=model_version_id)),
        patch("tempfile.mkdtemp", return_value=str(tmp_path)),
        patch("cvops_steps.train.shutil.rmtree") as mock_rmtree,
    ):
        step = TrainStep()
        result = await step.run(ctx, base_config, base_inputs)

        mock_rmtree.assert_called_once_with(tmp_path, ignore_errors=True)
        assert result == {"model_version_id": model_version_id}


@pytest.mark.asyncio
async def test_run_raises_when_commit_id_missing(ctx, base_config, mock_tc):
    """commit_id must be wired from the export edge; absent → clear error."""
    with patch(
        "cvops_steps.train._load_training_container", new=AsyncMock(return_value=mock_tc)
    ):
        step = TrainStep()
        with pytest.raises(RuntimeError, match="commit_id"):
            await step.run(ctx, base_config, inputs={"export_blob_hash": "sha256:x"})
