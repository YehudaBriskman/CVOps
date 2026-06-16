"""CVAT operations for the CVOps workers.

Wraps ``cvat_sdk`` with the handful of calls the lifecycle needs: list deployed
models, auto-annotate (kept compatible with the legacy model-deployer client),
push a human-review task (images + pre-labels), pull reviewed annotations, and
register a completion webhook.

``cvat_sdk`` is imported lazily inside each function so importing this module is
cheap and side-effect free — the step registry can import the package without the
SDK present, and only actual CVAT calls require it.

Geometry conversion lives in :mod:`cvops_cvat_client.geometry` (pure, tested).

.. note::
   The task/annotation/webhook functions below are written against the
   ``cvat_sdk`` 2.x high-level API but have **not** been verified against a live
   CVAT server (none is available in CI). Treat the SDK call shapes as
   provisional until exercised end-to-end by worker-cvat (tasks #4/#6).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cvops_cvat_client.geometry import cvat_rect_to_norm_bbox, norm_bbox_to_cvat_rect

# CVAT_URL is the spec name; CVAT_HOST is the legacy model-deployer name. Accept
# either so this client drops into both contexts.
CVAT_URL = os.environ.get("CVAT_URL") or os.environ.get("CVAT_HOST", "http://cvat_server:8080")
CVAT_USERNAME = os.environ.get("CVAT_USERNAME", "admin")
CVAT_PASSWORD = os.environ.get("CVAT_PASSWORD", "Admin1234!")
# Browser-reachable base for the links we hand back to the dashboard.
CVAT_PUBLIC_URL = os.environ.get("CVAT_PUBLIC_URL", "http://localhost:8080")


@dataclass
class ReviewImage:
    """One image to push into a review task, with its pre-labels.

    Frame order in the task follows the order these are passed to
    :func:`push_review_task`; ``pull_review_task`` returns annotations keyed by
    that same frame index, so the caller maps frame → sample by position.
    """

    path: Path
    width: int
    height: int
    # Canonical annotation objects: {"class_key", "geometry": {"coords": [...]}, ...}
    annotations: list[dict[str, Any]]


def _client():  # noqa: ANN202 — cvat_sdk.Client, imported lazily
    from cvat_sdk import Client

    c = Client(url=CVAT_URL, check_server_version=False)
    # Django's USE_X_FORWARDED_HOST=True needs these when we bypass the edge proxy.
    c.api_client.set_default_header("X-Forwarded-Host", "localhost")
    c.api_client.set_default_header("X-Forwarded-Proto", "http")
    c.login((CVAT_USERNAME, CVAT_PASSWORD))
    return c


def _task_url(task_id: int, job_id: int | None = None) -> str:
    if job_id is not None:
        return f"{CVAT_PUBLIC_URL}/tasks/{task_id}/jobs/{job_id}"
    return f"{CVAT_PUBLIC_URL}/tasks/{task_id}/jobs"


# --------------------------------------------------------------------------- #
# Model listing + auto-annotate (legacy model-deployer surface, kept stable)
# --------------------------------------------------------------------------- #
def list_models() -> list[dict]:
    """Return all Nuclio functions registered in CVAT."""
    import json

    from cvat_sdk.api_client.apis import LambdaApi

    client = _client()
    lambda_api = LambdaApi(client.api_client)
    _, resp = lambda_api.list_functions()
    functions = json.loads(resp.data)
    return [
        {
            "id": fn["id"],
            "name": fn.get("name", fn["id"]),
            "kind": fn.get("kind", ""),
            "description": fn.get("description", ""),
        }
        for fn in functions
    ]


def annotate(
    task_name: str,
    function_id: str,
    image_paths: list[Path],
    threshold: float = 0.3,
) -> dict:
    """Create a task, upload images, trigger Nuclio auto-annotation, wait."""
    from cvat_sdk.api_client.apis import LambdaApi
    from cvat_sdk.api_client.models import FunctionCallRequest
    from cvat_sdk.models import TaskWriteRequest

    client = _client()
    task = client.tasks.create(TaskWriteRequest(name=task_name, labels=[{"name": "object"}]))
    task.upload_data(resources=image_paths, params={"image_quality": 95})

    lambda_api = LambdaApi(client.api_client)
    result, _ = lambda_api.create_requests(
        FunctionCallRequest(function=function_id, task=task.id, cleanup=True, threshold=threshold)
    )
    request_id = str(result.id)

    for _ in range(120):
        time.sleep(5)
        res, _ = lambda_api.retrieve_requests(id=request_id)
        status = getattr(res, "status", "").lower()
        if status == "finished":
            break
        if status in ("failed", "error"):
            raise RuntimeError(f"Auto-annotation failed (status={status})")

    jobs_resp = client.api_client.jobs_api.list(task_id=task.id)
    job_id = jobs_resp[0].results[0].id
    return {"task_id": task.id, "job_id": job_id, "cvat_url": _task_url(task.id, job_id)}


# --------------------------------------------------------------------------- #
# Human-review push / pull (worker-cvat gate)
# --------------------------------------------------------------------------- #
def push_review_task(
    task_name: str, images: list[ReviewImage], label_names: list[str] | None = None
) -> dict:
    """Create a CVAT task with images and CVOps pre-labels for human review.

    The task's label classes are the union of ``label_names`` (the project
    ontology's class keys — the canonical set reviewers should annotate with)
    and any ``class_key``s present on the pre-labels. When ``label_names`` is
    omitted the set falls back to the pre-label keys alone. Uploads the images in
    order and sets pre-annotations converted from canonical normalized boxes to
    CVAT pixel rectangles.

    Returns ``{task_id, job_ids, cvat_url, label_map}`` where ``label_map`` is
    ``{class_key: label_id}`` and the frame order equals the order of ``images``.
    """
    from cvat_sdk.models import (
        LabeledDataRequest,
        LabeledShapeRequest,
        TaskWriteRequest,
    )

    class_keys = set(label_names or [])
    class_keys |= {a.get("class_key") for img in images for a in img.annotations}
    labels = [{"name": key} for key in sorted(k for k in class_keys if k)]

    client = _client()
    task = client.tasks.create(TaskWriteRequest(name=task_name, labels=labels))
    task.upload_data(resources=[img.path for img in images], params={"image_quality": 95})

    # class_key → CVAT label_id, resolved after creation.
    label_map = {lbl.name: lbl.id for lbl in task.get_labels()}

    shapes: list[Any] = []
    for frame, img in enumerate(images):
        for ann in img.annotations:
            key = ann.get("class_key")
            label_id = label_map.get(key)
            coords = (ann.get("geometry") or {}).get("coords")
            if label_id is None or not coords or len(coords) != 4:
                continue
            points = norm_bbox_to_cvat_rect(coords, img.width, img.height)
            shapes.append(
                LabeledShapeRequest(
                    type="rectangle",
                    frame=frame,
                    label_id=label_id,
                    points=points,
                    occluded=False,
                )
            )

    if shapes:
        task.set_annotations(LabeledDataRequest(shapes=shapes))

    job_ids = [j.id for j in client.api_client.jobs_api.list(task_id=task.id)[0].results]
    return {
        "task_id": task.id,
        "job_ids": job_ids,
        "cvat_url": _task_url(task.id, job_ids[0] if job_ids else None),
        "label_map": label_map,
    }


def pull_review_task(task_id: int, frame_dims: list[tuple[int, int]]) -> dict[int, list[dict]]:
    """Download reviewed annotations from a task, grouped by frame.

    Args:
        task_id: CVAT task id.
        frame_dims: ``[(width, height), ...]`` indexed by frame — needed to
            normalize CVAT pixel rects back to canonical coords. Must match the
            frame order used in :func:`push_review_task`.

    Returns:
        ``{frame_index: [canonical annotation, ...]}``. Frames with no boxes are
        omitted. The caller maps frame → sample by position.
    """
    client = _client()
    task = client.tasks.retrieve(task_id)
    label_names = {lbl.id: lbl.name for lbl in task.get_labels()}
    data = task.get_annotations()

    by_frame: dict[int, list[dict]] = {}
    for shape in getattr(data, "shapes", []):
        # shape.type is a cvat_sdk enum (str() == "rectangle"), not a plain
        # string — compare its string value, not the enum object.
        if str(getattr(shape, "type", "")) != "rectangle":
            continue  # gate is detection-only for now; skip polygons/polylines
        frame = shape.frame
        if frame >= len(frame_dims):
            continue
        w, h = frame_dims[frame]
        coords = cvat_rect_to_norm_bbox(list(shape.points), w, h)
        by_frame.setdefault(frame, []).append(
            {
                "class_key": label_names.get(shape.label_id),
                "geometry": {"type": "bbox", "coords": coords},
            }
        )
    return by_frame


def register_webhook(task_id: int, target_url: str, secret: str) -> int:
    """Register a CVAT webhook firing on annotation/job updates for a task.

    Returns the created webhook id. The receiver must validate ``secret``.

    NOTE: CVAT removed task-scoped webhooks — ``WebhookType`` now only allows
    ``organization``/``project``, so this task-scoped registration fails against
    CVAT >= 2.x. Callers (human_review) treat failure as non-fatal and fall back
    to polling/manual gate resolution. Re-scoping to a project webhook (and
    creating tasks under a CVAT project) is the proper fix for auto-resume.
    """
    from cvat_sdk.api_client.models import (
        EventsEnum,
        WebhookContentType,
        WebhookWriteRequest,
    )

    client = _client()
    webhook, _ = client.api_client.webhooks_api.create(
        WebhookWriteRequest(
            target_url=target_url,
            type="task",
            content_type=WebhookContentType("application/json"),
            secret=secret,
            events=[EventsEnum("update:job"), EventsEnum("update:task")],
            task_id=task_id,
            is_active=True,
            enable_ssl=False,
        )
    )
    return webhook.id
