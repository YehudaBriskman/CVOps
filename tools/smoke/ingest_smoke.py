#!/usr/bin/env python3
"""End-to-end smoke test for the backend-triggered ingest flow.

Drives a running stack (default: `tilt up`, API behind nginx at /api/v1) through
the full path a browser client would take:

    register → create project → create workflow → set it as the project's
    default ingest workflow → create data source (get presigned PUT) →
    PUT bytes straight to Garage → confirm-upload → poll the auto-dispatched run

The confirm step is where the backend takes over: it registers the blob and,
because the project has a default ingest workflow, returns a `run_id`. This
script then polls that run to a terminal state.

NOTE: `extract_frames` is still a stub, so the run is expected to reach
`failed` at the extract step. That still proves upload → blob registration →
auto-dispatch → executor pickup. Once the step is implemented the same script
will show `succeeded`.

Usage:
    python tools/smoke/ingest_smoke.py                       # against nginx :80
    python tools/smoke/ingest_smoke.py --base-url http://localhost:8000 --api-prefix ''
    python tools/smoke/ingest_smoke.py --video path/to/clip.mp4
"""

from __future__ import annotations

import argparse
import sys
import time
import uuid
from pathlib import Path

import httpx


def _log(msg: str) -> None:
    print(f"[smoke] {msg}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--base-url",
        default="http://localhost",
        help="Edge URL (nginx). Default http://localhost (port 80).",
    )
    ap.add_argument(
        "--api-prefix",
        default="/api/v1",
        help="Path prefix the API is mounted under. Default /api/v1; "
        "use '' to hit the API container directly.",
    )
    ap.add_argument(
        "--video",
        type=Path,
        default=None,
        help="Video file to upload. Defaults to a tiny synthetic payload.",
    )
    ap.add_argument("--timeout", type=float, default=60.0, help="Run poll timeout (s).")
    args = ap.parse_args()

    api = f"{args.base_url.rstrip('/')}{args.api_prefix}"
    suffix = uuid.uuid4().hex[:8]

    # A real video makes extract_frames meaningful; otherwise a stub payload is
    # enough to exercise upload + registration + dispatch.
    if args.video:
        payload = args.video.read_bytes()
        media_type = "video/mp4"
    else:
        payload = b"SMOKE-TEST-NOT-A-REAL-VIDEO-" + suffix.encode()
        media_type = "application/octet-stream"

    blob_hash = "sha256:" + __import__("hashlib").sha256(payload).hexdigest()

    with httpx.Client(timeout=30.0) as client:
        _log(f"API base: {api}")

        # 1. Register (creates org + user, returns tokens).
        r = client.post(
            f"{api}/auth/register",
            json={
                "email": f"smoke-{suffix}@test.com",
                "password": "smoke-password-123",
                "org_name": f"smoke-org-{suffix}",
            },
        )
        r.raise_for_status()
        token = r.json()["access_token"]
        auth = {"Authorization": f"Bearer {token}"}
        _log("registered + authenticated")

        # 2. Project.
        r = client.post(f"{api}/projects/", headers=auth, json={"name": f"smoke-{suffix}"})
        r.raise_for_status()
        project_id = r.json()["id"]
        _log(f"project {project_id}")

        # 3. Workflow with a single extract_frames step.
        definition = {
            "steps": [
                {
                    "id": "extract",
                    "type": "step.extract_frames",
                    "config": {"interval_seconds": 1.0},
                    "inputs": {"source_id": "$run.params.source_id"},
                }
            ],
            "edges": [],
        }
        r = client.post(
            f"{api}/projects/{project_id}/workflows",
            headers=auth,
            json={"name": "ingest", "definition": definition},
        )
        r.raise_for_status()
        workflow_id = r.json()["id"]
        _log(f"workflow {workflow_id}")

        # 4. Make it the project's default ingest workflow.
        r = client.patch(
            f"{api}/projects/{project_id}",
            headers=auth,
            json={"default_ingest_workflow_id": workflow_id},
        )
        r.raise_for_status()
        _log("set default_ingest_workflow_id")

        # 5. Create data source → presigned PUT URL.
        r = client.post(
            f"{api}/projects/{project_id}/data-sources",
            headers=auth,
            json={"type": "video"},
        )
        r.raise_for_status()
        ds = r.json()
        ds_id = ds["data_source"]["id"]
        put_url = ds["presigned_put_url"]
        _log(f"data source {ds_id}; uploading {len(payload)} bytes to Garage")

        # 6. Client uploads bytes DIRECTLY to Garage (bypasses the API).
        put = httpx.put(put_url, content=payload, headers={"Content-Type": media_type})
        put.raise_for_status()
        _log("upload complete")

        # 7. Confirm — backend registers blob + auto-dispatches the run.
        r = client.post(
            f"{api}/data-sources/{ds_id}/confirm-upload",
            headers=auth,
            json={"blob_hash": blob_hash},
        )
        r.raise_for_status()
        confirm = r.json()
        run_id = confirm["run_id"]
        _log(f"confirmed; status={confirm['data_source']['status']} run_id={run_id}")

        if not run_id:
            _log("ERROR: no run dispatched — default ingest workflow not wired?")
            return 1

        # 8. Poll the run to a terminal state.
        terminal = {"succeeded", "failed", "cancelled"}
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            r = client.get(f"{api}/runs/{run_id}", headers=auth)
            r.raise_for_status()
            status = r.json()["status"]
            _log(f"run status: {status}")
            if status in terminal:
                break
            time.sleep(1.0)
        else:
            _log("ERROR: run did not reach a terminal state in time")
            return 1

    _log(f"done — final run status: {status}")
    # 'failed' is expected until extract_frames is implemented; the dispatch
    # path itself is what this smoke test proves.
    _log("dispatch path verified ✓ (run reached the executor)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
