"""
upload_to_cvat.py
-----------------
Step 3 in the YOLO workflow: upload extracted frames to CVAT and trigger
auto-annotation using a model deployed inside CVAT (via Nuclio/Lambda).

What this script does:
    1. Connects to the local CVAT instance
    2. Creates a new Task with the session name
    3. Uploads all images from the session folder
    4. Lists available auto-annotation models deployed in CVAT
    5. Asks the user to choose a model and triggers auto-annotation

Usage:
    python upload_to_cvat.py
"""

import os
import getpass
import time
from pathlib import Path
from cvat_sdk import make_client
from cvat_sdk.models import TaskWriteRequest
from cvat_sdk.api_client.apis import LambdaApi
from cvat_sdk.api_client.models import FunctionCallRequest


# CVAT connection settings — override via environment variables
CVAT_HOST = os.environ.get("CVAT_HOST", "http://localhost")
CVAT_PORT = int(os.environ.get("CVAT_PORT", "8080"))


def ask_session() -> tuple:
    """
    Ask the user which session to upload.
    Returns (frames_dir, session_name)
    """
    frames_base = Path("./frames")

    if not frames_base.exists():
        print("[!] No 'frames' folder found. Run extract_frames.py first.")
        exit(1)

    sessions = [f for f in frames_base.iterdir() if f.is_dir()]

    if not sessions:
        print("[!] No session folders found inside 'frames/'.")
        exit(1)

    print("\n========================================")
    print("  Upload to CVAT - Select Session       ")
    print("========================================")
    print("Available sessions:")

    for i, session in enumerate(sessions):
        images = len(list(session.glob("*.jpg")) + list(session.glob("*.jpeg")) + list(session.glob("*.png")))
        print(f"  {i + 1}. {session.name} ({images} images)")

    print("========================================")

    while True:
        try:
            choice = int(input(f"Enter number (1-{len(sessions)}): ").strip())
            if 1 <= choice <= len(sessions):
                session = sessions[choice - 1]
                return session, session.name
            print(f"  [!] Please enter a number between 1 and {len(sessions)}.")
        except ValueError:
            print("  [!] Please enter a valid number.")


def ask_model(lambda_api: LambdaApi) -> str | None:
    """
    List all auto-annotation models deployed in CVAT and ask the user to choose one.
    Returns the selected function ID, or None to skip auto-annotation.
    """
    print("\n[*] Fetching available auto-annotation models from CVAT...")

    try:
        functions, _ = lambda_api.list_functions()
    except Exception as e:
        print(f"[!] Could not fetch models: {e}")
        print("    Make sure Nuclio is running and models are deployed in CVAT.")
        return None

    if not functions:
        print("[!] No auto-annotation models found in CVAT.")
        print("    Deploy a model via Nuclio first (see CVAT serverless docs).")
        return None

    print("\n========================================")
    print("  Auto-Annotation - Select Model        ")
    print("========================================")
    print("Available models:")

    for i, fn in enumerate(functions):
        name = getattr(fn, "name", fn.id)
        kind = getattr(fn, "kind", "")
        description = getattr(fn, "description", "")
        label = f"{name}"
        if kind:
            label += f" [{kind}]"
        if description:
            label += f" — {description}"
        print(f"  {i + 1}. {label}")

    print(f"  {len(functions) + 1}. Skip auto-annotation")
    print("========================================")

    while True:
        try:
            choice = int(input(f"Enter number (1-{len(functions) + 1}): ").strip())
            if choice == len(functions) + 1:
                return None
            if 1 <= choice <= len(functions):
                return functions[choice - 1].id
            print(f"  [!] Please enter a number between 1 and {len(functions) + 1}.")
        except ValueError:
            print("  [!] Please enter a valid number.")


def wait_for_annotation_job(lambda_api: LambdaApi, request_id: str, timeout: int = 300):
    """
    Poll until the auto-annotation job finishes or times out.
    """
    print("[*] Waiting for auto-annotation to complete", end="", flush=True)
    start = time.time()

    while time.time() - start < timeout:
        try:
            result, _ = lambda_api.retrieve_requests(id=request_id)
            status = getattr(result, "status", "").lower()
            if status == "finished":
                print(" done.")
                return True
            if status in ("failed", "error"):
                print(f" failed (status: {status}).")
                return False
        except Exception:
            pass

        print(".", end="", flush=True)
        time.sleep(5)

    print(" timed out.")
    return False


def upload_to_cvat(frames_dir: Path, session_name: str, username: str, password: str):
    """
    Upload frames to CVAT, then trigger auto-annotation with a user-selected model.
    """
    print(f"\n[*] Connecting to CVAT at {CVAT_HOST}:{CVAT_PORT}...")

    with make_client(
        host=CVAT_HOST,
        port=CVAT_PORT,
        credentials=(username, password)
    ) as client:

        print("[✓] Connected to CVAT")

        print(f"[*] Creating task: {session_name}...")

        task = client.tasks.create(
            TaskWriteRequest(
                name=session_name,
                labels=[{"name": "object"}]
            )
        )

        print(f"[✓] Task created with ID: {task.id}")

        image_files = sorted(
            list(frames_dir.glob("*.jpg")) +
            list(frames_dir.glob("*.jpeg")) +
            list(frames_dir.glob("*.png"))
        )

        if not image_files:
            print(f"[!] No images found in: {frames_dir}")
            return

        print(f"[*] Uploading {len(image_files)} images...")

        task.upload_data(
            resources=image_files,
            params={"image_quality": 95}
        )

        print("[✓] Images uploaded successfully")

        lambda_api = LambdaApi(client.api_client)
        model_id = ask_model(lambda_api)

        if model_id is None:
            print("[!] Skipping auto-annotation.")
        else:
            print(f"[*] Triggering auto-annotation with model: {model_id}...")

            try:
                result, _ = lambda_api.create_requests(
                    FunctionCallRequest(function=model_id, task=task.id, cleanup=True)
                )
                request_id = getattr(result, "id", None)

                if request_id:
                    success = wait_for_annotation_job(lambda_api, str(request_id))
                    if success:
                        print("[✓] Auto-annotation complete")
                    else:
                        print("[!] Auto-annotation did not finish successfully — check CVAT logs")
                else:
                    print("[✓] Auto-annotation request sent (async — check CVAT for progress)")

            except Exception as e:
                print(f"[!] Failed to trigger auto-annotation: {e}")

        print(f"\n{'=' * 40}")
        print(f"Task name  : {session_name}")
        print(f"Task ID    : {task.id}")
        print(f"Open CVAT  : {CVAT_HOST}:{CVAT_PORT}/tasks/{task.id}/jobs")
        print(f"{'=' * 40}\n")


def main():
    frames_dir, session_name = ask_session()

    username = os.environ.get("CVAT_USERNAME", "").strip() or input("Enter your CVAT username: ").strip()
    password = getpass.getpass("Enter your CVAT password: ")

    print(f"\n[✓] Session : {session_name}")

    upload_to_cvat(frames_dir, session_name, username, password)


if __name__ == "__main__":
    main()


