"""
deployer.py — Deploy a YOLO .pt model to CVAT via Nuclio.

Flow:
  1. Ensure base image exists (built once from nuclio_base/)
  2. Extract class labels from the .pt file
  3. Build thin model image: base + model.pt
  4. Generate function.yaml with correct labels
  5. nuctl deploy --run-image → model visible in CVAT
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import docker
from ultralytics import YOLO

CVAT_NETWORK = os.environ.get("CVAT_NETWORK",              "cvat_cvat")
REDIS_HOST   = os.environ.get("CVAT_FUNCTIONS_REDIS_HOST", "cvat_redis_ondisk")
REDIS_PORT   = os.environ.get("CVAT_FUNCTIONS_REDIS_PORT", "6666")
BASE_IMAGE   = os.environ.get("YOLO_BASE_IMAGE",           "cvat/yolo-base:latest")
NUCTL        = os.environ.get("NUCTL_PATH",                "/usr/local/bin/nuctl")

_NUCLIO_BASE_DIR = Path(__file__).parent / "nuclio_base"


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9-]", "-", name.lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return f"pth-custom-{slug}"


def _ensure_base_image() -> None:
    client = docker.from_env()
    try:
        client.images.get(BASE_IMAGE)
    except docker.errors.ImageNotFound:
        client.images.build(path=str(_NUCLIO_BASE_DIR), tag=BASE_IMAGE, rm=True)


def _extract_labels(pt_path: Path) -> list[dict]:
    model = YOLO(str(pt_path))
    return [{"id": int(k), "name": v} for k, v in sorted(model.names.items())]


def _build_model_image(pt_path: Path, image_tag: str) -> None:
    dockerfile = (
        f"FROM {BASE_IMAGE}\n"
        "COPY model.pt /opt/nuclio/model.pt\n"
        "ENV MODEL_PATH=/opt/nuclio/model.pt\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        shutil.copy2(pt_path, tmp_path / "model.pt")
        (tmp_path / "Dockerfile").write_text(dockerfile)
        docker.from_env().images.build(path=str(tmp_path), tag=image_tag, rm=True)


def _generate_function_yaml(func_name: str, display_name: str, labels: list[dict], image_tag: str) -> str:
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

platform:
  attributes:
    restartPolicy:
      name: always
      maximumRetryCount: 3
    mountMode: volume

build:
  image: {image_tag}
  codeEntryType: image

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
"""


def deploy(pt_path: Path, model_name: str) -> str:
    """Deploy a YOLO .pt to Nuclio. Returns the function name."""
    func_name = _slugify(model_name)
    image_tag = f"cvat/{func_name}:latest"

    _ensure_base_image()
    labels = _extract_labels(pt_path)
    _build_model_image(pt_path, image_tag)

    with tempfile.TemporaryDirectory() as tmp:
        yaml_path = Path(tmp) / "function.yaml"
        yaml_path.write_text(_generate_function_yaml(func_name, model_name, labels, image_tag))

        result = subprocess.run(
            [
                NUCTL, "deploy", func_name,
                "--project-name", "cvat",
                "--platform", "local",
                "--run-image", image_tag,
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
