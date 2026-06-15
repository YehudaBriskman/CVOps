"""
deployer.py — Deploy a YOLO .pt model to CVAT via Nuclio.

Flow:
  1. Extract class labels from the .pt file
  2. Write model.pt + handler (main.py) into a temp build context
  3. Generate function.yaml with baseImage + pip-install directives
  4. nuctl deploy --path <context> → Nuclio builds image and registers function in CVAT
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from ultralytics import YOLO

CVAT_NETWORK = os.environ.get("CVAT_NETWORK",              "cvat_cvat")
REDIS_HOST   = os.environ.get("CVAT_FUNCTIONS_REDIS_HOST", "cvat_redis_ondisk")
REDIS_PORT   = os.environ.get("CVAT_FUNCTIONS_REDIS_PORT", "6666")
BASE_IMAGE   = os.environ.get("YOLO_BASE_IMAGE",           "python:3.9-slim")
NUCTL        = os.environ.get("NUCTL_PATH",                "/usr/local/bin/nuctl")

_HANDLER_SRC = Path(__file__).parent / "nuclio_base" / "main.py"


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9-]", "-", name.lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return f"pth-custom-{slug}"


def _extract_labels(pt_path: Path) -> list[dict]:
    model = YOLO(str(pt_path))
    return [{"id": int(k), "name": v} for k, v in sorted(model.names.items())]


def _generate_function_yaml(func_name: str, display_name: str, labels: list[dict]) -> str:
    spec = json.dumps(labels)
    return f"""metadata:
  name: {func_name}
  namespace: cvat
  annotations:
    name: {display_name}
    type: detector
    framework: pytorch
    spec: '{spec}'

spec:
  description: {display_name} YOLO detector
  runtime: python:3.9
  handler: main:handler
  eventTimeout: 30s

  build:
    baseImage: {BASE_IMAGE}
    directives:
      preCopy:
        - kind: RUN
          value: apt-get update && apt-get install -y --no-install-recommends libxcb1 libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
        - kind: RUN
          value: pip install --no-cache-dir ultralytics pillow numpy
      postCopy:
        - kind: ENV
          value: MODEL_PATH=/opt/nuclio/model.pt

  triggers:
    myHttpTrigger:
      maxWorkers: 1
      kind: http
      workerAvailabilityTimeoutMilliseconds: 10000
      attributes:
        maxRequestBodySize: 33554432

  resources:
    requests:
      memory: 512Mi
    limits:
      memory: 2048Mi

platform:
  attributes:
    restartPolicy:
      name: always
      maximumRetryCount: 3
    mountMode: volume
"""


def _ensure_project() -> None:
    result = subprocess.run(
        [NUCTL, "get", "project", "cvat", "--platform", "local"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        subprocess.run(
            [NUCTL, "create", "project", "cvat", "--platform", "local"],
            capture_output=True, text=True, check=True,
        )


def deploy(pt_path: Path, model_name: str) -> str:
    """Deploy a YOLO .pt to Nuclio. Returns the function name."""
    func_name = _slugify(model_name)
    labels = _extract_labels(pt_path)
    _ensure_project()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Build context: handler + model file
        shutil.copy2(_HANDLER_SRC, tmp_path / "main.py")
        shutil.copy2(pt_path, tmp_path / "model.pt")

        yaml_path = tmp_path / "function.yaml"
        yaml_path.write_text(_generate_function_yaml(func_name, model_name, labels))

        result = subprocess.run(
            [
                NUCTL, "deploy", func_name,
                "--project-name", "cvat",
                "--platform", "local",
                "--path", str(tmp_path),
                "--file", str(yaml_path),
                "--env", f"CVAT_FUNCTIONS_REDIS_HOST={REDIS_HOST}",
                "--env", f"CVAT_FUNCTIONS_REDIS_PORT={REDIS_PORT}",
                "--platform-config", json.dumps({"attributes": {"network": CVAT_NETWORK}}),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr)

    return func_name
