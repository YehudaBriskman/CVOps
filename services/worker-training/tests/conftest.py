import io
import json
import tarfile
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from cvops_api.engine.step import StepContext


def _make_export_tar() -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        content = b"fake image"
        info = tarfile.TarInfo(name="images/train/img.jpg")
        info.size = len(content)
        tf.addfile(info, io.BytesIO(content))
    return buf.getvalue()


@pytest.fixture
def run_id():
    return str(uuid.uuid4())


@pytest.fixture
def training_container_id():
    return str(uuid.uuid4())


@pytest.fixture
def project_id():
    return str(uuid.uuid4())


@pytest.fixture
def commit_id():
    return str(uuid.uuid4())


@pytest.fixture
def mock_tc(training_container_id):
    tc = MagicMock()
    tc.id = uuid.UUID(training_container_id)
    tc.image = "placeholder"
    tc.icd_config = {
        "outputs": {
            "metrics_file": {"path": "/output/metrics.json"},
            "weights_path": {"path": "/output/weights/"},
        },
        "mlflow_tracking_uri": None,
    }
    return tc


@pytest.fixture
def mock_storage():
    storage = AsyncMock()
    storage.get_bytes.return_value = _make_export_tar()
    storage.save_bytes.return_value = "sha256:abc123deadbeef"
    return storage


@pytest.fixture
def mock_session(mock_tc):
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = mock_tc
    session.execute.return_value = result
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def ctx(run_id, project_id, mock_session, mock_storage):
    return StepContext(
        session=mock_session,
        storage=mock_storage,
        project_id=project_id,
        run_id=run_id,
        actor_id="service:worker",
        emit_event=AsyncMock(),
    )


@pytest.fixture
def base_config(training_container_id):
    return {
        "training_container_id": training_container_id,
        "git_url": "https://github.com/example/trainer.git",
        "branch": "main",
        "entry_point": "train.py",
        "hyperparams": {"epochs": 10, "batch_size": 16},
    }


@pytest.fixture
def base_inputs(commit_id):
    # commit_id is wired from the upstream export step's outputs, not config.
    return {
        "export_blob_hash": "sha256:exportdeadbeef",
        "commit_id": commit_id,
    }
