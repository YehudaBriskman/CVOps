"""
cvat_autolabel.py
-----------------
Upload a folder of frames to CVAT and auto-label them with YOLO12n.
Every run creates a NEW task — nothing is ever overwritten.

Usage:
    python cvat_autolabel.py <frames_folder> [--threshold 0.3]

Examples:
    python cvat_autolabel.py frames/yyyy
    python cvat_autolabel.py frames/yyyy --threshold 0.2
    python cvat_autolabel.py /absolute/path/to/frames

Environment variables (optional — overrides defaults):
    CVAT_HOST      default: http://localhost
    CVAT_PORT      default: 8080
    CVAT_USERNAME  default: admin
    CVAT_PASSWORD  default: Admin1234!
"""

import argparse
import os
import sys
import time
from pathlib import Path

from cvat_sdk import make_client
from cvat_sdk.models import TaskWriteRequest
from cvat_sdk.api_client.apis import LambdaApi
from cvat_sdk.api_client.models import FunctionCallRequest


CVAT_HOST     = os.environ.get("CVAT_HOST",     "http://localhost")
CVAT_PORT     = int(os.environ.get("CVAT_PORT", "8080"))
CVAT_USERNAME = os.environ.get("CVAT_USERNAME", "admin")
CVAT_PASSWORD = os.environ.get("CVAT_PASSWORD", "Admin1234!")
FUNC_ID       = "pth-ultralytics-yolo12n"

COCO_LABELS = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
    "truck", "boat", "traffic light", "fire hydrant", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag",
    "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite",
    "baseball bat", "baseball glove", "skateboard", "surfboard",
    "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon",
    "bowl", "banana", "apple", "sandwich", "orange", "broccoli", "carrot",
    "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant",
    "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote",
    "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
]


def main():
    parser = argparse.ArgumentParser(description="Upload frames to CVAT and auto-label with YOLO12n")
    parser.add_argument("folder", help="Path to folder containing frame images")
    parser.add_argument("--threshold", type=float, default=0.3,
                        help="Confidence threshold (default: 0.3)")
    args = parser.parse_args()

    frames_dir = Path(args.folder)
    if not frames_dir.exists():
        print(f"[!] Folder not found: {frames_dir}")
        sys.exit(1)

    images = sorted(
        list(frames_dir.glob("*.jpg")) +
        list(frames_dir.glob("*.jpeg")) +
        list(frames_dir.glob("*.png"))
    )
    if not images:
        print(f"[!] No images found in: {frames_dir}")
        sys.exit(1)

    task_name = frames_dir.name
    print(f"[*] Folder     : {frames_dir}")
    print(f"[*] Images     : {len(images)}")
    print(f"[*] Task name  : {task_name}")
    print(f"[*] Threshold  : {args.threshold}")
    print(f"[*] CVAT       : {CVAT_HOST}:{CVAT_PORT}")

    with make_client(host=CVAT_HOST, port=CVAT_PORT,
                     credentials=(CVAT_USERNAME, CVAT_PASSWORD)) as client:

        print(f"\n[*] Creating task...")
        task = client.tasks.create(
            TaskWriteRequest(
                name=task_name,
                labels=[{"name": label} for label in COCO_LABELS],
            )
        )
        print(f"[✓] Task '{task.name}' created (ID={task.id})")

        print(f"[*] Uploading {len(images)} images...")
        task.upload_data(resources=images, params={"image_quality": 95})
        print(f"[✓] Upload complete")

        print(f"[*] Starting auto-annotation with YOLO12n...")
        lambda_api = LambdaApi(client.api_client)
        result, _ = lambda_api.create_requests(
            FunctionCallRequest(
                function=FUNC_ID,
                task=task.id,
                cleanup=True,
                threshold=args.threshold,
            )
        )
        request_id = str(result.id)

        print(f"[*] Waiting for results", end="", flush=True)
        for _ in range(120):
            time.sleep(5)
            res, _ = lambda_api.retrieve_requests(id=request_id)
            status = getattr(res, "status", "").lower()
            print(".", end="", flush=True)
            if status == "finished":
                print(" done ✓")
                break
            if status in ("failed", "error"):
                print(f" FAILED (status={status})")
                sys.exit(1)
        else:
            print(" timed out — check CVAT manually")

        jobs_resp = client.api_client.jobs_api.list(task_id=task.id)
        job_id = jobs_resp[0].results[0].id

        print(f"\n{'=' * 45}")
        print(f"  Task      : {task.name}  (ID={task.id})")
        print(f"  Threshold : {args.threshold}")
        print(f"  Open at   : {CVAT_HOST}:{CVAT_PORT}/tasks/{task.id}/jobs/{job_id}")
        print(f"{'=' * 45}")


if __name__ == "__main__":
    main()
