"""Test fixtures for the model-deployer service.

model-deployer uses a flat module layout (``app.py`` does ``from deployer
import deploy``), so the service directory must be on ``sys.path`` for the
imports to resolve.

``deployer.py`` imports ``from ultralytics import YOLO`` at module load, and
``ultralytics`` is intentionally NOT installed in the test venv (it is heavy —
it pulls in torch). We inject a lightweight stub into ``sys.modules`` before
importing ``app`` so the real model code never runs. The HTTP-layer tests
monkeypatch ``app.deploy`` anyway, so the stub only needs to satisfy the
import.
"""

import os
import sys
import types
from pathlib import Path

import pytest

os.environ.setdefault("WORKER_TOKEN", "test-token")
TEST_TOKEN = os.environ["WORKER_TOKEN"]

SERVICE_DIR = Path(__file__).resolve().parent.parent

# Make the flat modules (app.py, deployer.py) importable.
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

# Stub out ultralytics before deployer.py is imported.
if "ultralytics" not in sys.modules:
    _ultralytics = types.ModuleType("ultralytics")

    class _StubYOLO:  # noqa: D401 - test stub
        def __init__(self, *args, **kwargs):
            self.names = {0: "object"}

    _ultralytics.YOLO = _StubYOLO
    sys.modules["ultralytics"] = _ultralytics

# Stub out cvops_cvat_client (heavy SDK, not installed in test env).
if "cvops_cvat_client" not in sys.modules:
    _cvat_client = types.ModuleType("cvops_cvat_client")
    _cvat_client.annotate = lambda **kwargs: {}
    _cvat_client.list_models = lambda: []
    sys.modules["cvops_cvat_client"] = _cvat_client


@pytest.fixture
def client():
    """A TestClient bound to the model-deployer FastAPI app, pre-authorised."""
    from fastapi.testclient import TestClient

    import app as app_module

    return TestClient(app_module.app, headers={"Authorization": f"Bearer {TEST_TOKEN}"})


@pytest.fixture
def unauth_client():
    """A TestClient with no auth header, for testing 401 responses."""
    from fastapi.testclient import TestClient

    import app as app_module

    return TestClient(app_module.app, raise_server_exceptions=False)


@pytest.fixture
def app_module():
    """The imported ``app`` module, for monkeypatching the symbols it bound
    (``deploy``, ``list_models``, ``annotate``)."""
    import app as app_module

    return app_module
