"""
cvat_client.py — CVAT operations: list models, create task, trigger annotation.
"""

import os
import time
from pathlib import Path

from cvat_sdk import Client
from cvat_sdk.models import TaskWriteRequest
from cvat_sdk.api_client.apis import LambdaApi
from cvat_sdk.api_client.models import FunctionCallRequest

CVAT_HOST     = os.environ.get("CVAT_HOST",     "http://cvat_server:8080")
CVAT_USERNAME = os.environ.get("CVAT_USERNAME", "admin")
CVAT_PASSWORD = os.environ.get("CVAT_PASSWORD", "Admin1234!")


def _client() -> Client:
    c = Client(url=CVAT_HOST, check_server_version=False)
    # Django's USE_X_FORWARDED_HOST=True requires these headers when bypassing traefik
    c.api_client.set_default_header("X-Forwarded-Host", "localhost")
    c.api_client.set_default_header("X-Forwarded-Proto", "http")
    c.login((CVAT_USERNAME, CVAT_PASSWORD))
    return c


def list_models() -> list[dict]:
    """Return all Nuclio functions registered in CVAT."""
    import json
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
    """
    Create a CVAT task, upload images, trigger auto-annotation.
    Returns task_id and job_id for dashboard link.
    """
    client = _client()
    task = client.tasks.create(
        TaskWriteRequest(name=task_name, labels=[{"name": "object"}])
    )

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

    return {
        "task_id": task.id,
        "job_id": job_id,
        "cvat_url": f"http://localhost:8080/tasks/{task.id}/jobs/{job_id}",
    }
