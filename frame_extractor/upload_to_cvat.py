"""
upload_to_cvat.py
-----------------
Step 3 in the YOLO workflow: upload extracted frames and auto-generated labels to CVAT.

What this script does:
    1. Connects to the local CVAT instance
    2. Creates a new Task with the session name
    3. Uploads all images from the session folder
    4. Uploads YOLO labels as pre-annotations

Usage:
    python upload_to_cvat.py
"""

import os
import getpass
import zipfile
import tempfile
from pathlib import Path
from cvat_sdk import make_client
from cvat_sdk.models import TaskWriteRequest


# CVAT connection settings
CVAT_HOST = "http://localhost"
CVAT_PORT = 8080
CVAT_USERNAME = "Nati"

# COCO class names used by YOLO12n (80 classes)
COCO_NAMES = {
    0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 4: "airplane",
    5: "bus", 6: "train", 7: "truck", 8: "boat", 9: "traffic light",
    10: "fire hydrant", 11: "stop sign", 12: "parking meter", 13: "bench",
    14: "bird", 15: "cat", 16: "dog", 17: "horse", 18: "sheep", 19: "cow",
    20: "elephant", 21: "bear", 22: "zebra", 23: "giraffe", 24: "backpack",
    25: "umbrella", 26: "handbag", 27: "tie", 28: "suitcase", 29: "frisbee",
    30: "skis", 31: "snowboard", 32: "sports ball", 33: "kite", 34: "baseball bat",
    35: "baseball glove", 36: "skateboard", 37: "surfboard", 38: "tennis racket",
    39: "bottle", 40: "wine glass", 41: "cup", 42: "fork", 43: "knife",
    44: "spoon", 45: "bowl", 46: "banana", 47: "apple", 48: "sandwich",
    49: "orange", 50: "broccoli", 51: "carrot", 52: "hot dog", 53: "pizza",
    54: "donut", 55: "cake", 56: "chair", 57: "couch", 58: "potted plant",
    59: "bed", 60: "dining table", 61: "toilet", 62: "tv", 63: "laptop",
    64: "mouse", 65: "remote", 66: "keyboard", 67: "cell phone", 68: "microwave",
    69: "oven", 70: "toaster", 71: "sink", 72: "refrigerator", 73: "book",
    74: "clock", 75: "vase", 76: "scissors", 77: "teddy bear", 78: "hair drier",
    79: "toothbrush",
}


def ask_session() -> tuple:
    """
    Ask the user which session to upload.
    Returns (frames_dir, labels_dir, session_name)
    """
    frames_base = Path("./frames")
    labels_base = Path("./labels")

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
        images = len(list(session.glob("*.jpg")) + list(session.glob("*.png")))
        labels_dir = labels_base / session.name
        labels = len(list(labels_dir.glob("*.txt"))) if labels_dir.exists() else 0
        print(f"  {i + 1}. {session.name} ({images} images, {labels} labels)")

    print("========================================")

    while True:
        try:
            choice = int(input(f"Enter number (1-{len(sessions)}): ").strip())
            if 1 <= choice <= len(sessions):
                session = sessions[choice - 1]
                return session, labels_base / session.name, session.name
            print(f"  [!] Please enter a number between 1 and {len(sessions)}.")
        except ValueError:
            print("  [!] Please enter a valid number.")


def get_classes_from_labels(labels_dir: Path) -> dict[int, str]:
    """
    Read all label files and return a mapping of {class_id: class_name}
    using COCO class names. Falls back to 'class_N' for unknown IDs.
    """
    class_ids = set()
    for label_file in labels_dir.glob("*.txt"):
        for line in label_file.read_text().splitlines():
            parts = line.strip().split()
            if parts:
                class_ids.add(int(parts[0]))

    return {cid: COCO_NAMES.get(cid, f"class_{cid}") for cid in sorted(class_ids)}


def upload_to_cvat(frames_dir: Path, labels_dir: Path, session_name: str, password: str):
    """
    Upload frames and labels to CVAT.

    Args:
        frames_dir   -> folder containing the extracted frame images
        labels_dir   -> folder containing the YOLO .txt label files
        session_name -> name used for the CVAT task
        password     -> CVAT password
    """
    print(f"\n[*] Connecting to CVAT at {CVAT_HOST}:{CVAT_PORT}...")

    with make_client(
        host=CVAT_HOST,
        port=CVAT_PORT,
        credentials=(CVAT_USERNAME, password)
    ) as client:

        print("[✓] Connected to CVAT")

        # Detect which classes appear in the label files
        class_map = {}
        if labels_dir.exists():
            class_map = get_classes_from_labels(labels_dir)

        if class_map:
            print(f"[✓] Detected classes: {class_map}")
        else:
            print("[!] No annotations found — task will have no pre-defined labels")

        print(f"[*] Creating task: {session_name}...")

        task = client.tasks.create(
            TaskWriteRequest(
                name=session_name,
                labels=[{"name": name} for name in class_map.values()] or [{"name": "object"}]
            )
        )

        print(f"[✓] Task created with ID: {task.id}")

        # Collect all image files from the session folder
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

        # Upload labels if they exist
        if labels_dir.exists():
            label_files = list(labels_dir.glob("*.txt"))

            if label_files and class_map:
                print(f"[*] Uploading {len(label_files)} label files as pre-annotations...")

                with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                    tmp_path = tmp.name

                labeled_stems = {lf.stem for lf in label_files}

                with zipfile.ZipFile(tmp_path, "w") as zf:
                    for label_file in label_files:
                        zf.write(label_file, f"train/labels/{label_file.name}")

                    # datumaro requires images in the zip to map labels to frames
                    for img_file in sorted(
                        list(frames_dir.glob("*.jpg")) +
                        list(frames_dir.glob("*.jpeg")) +
                        list(frames_dir.glob("*.png"))
                    ):
                        if img_file.stem in labeled_stems:
                            zf.write(img_file, f"train/images/{img_file.name}")

                    # data.yaml must map the exact class IDs used in the .txt files
                    names_block = "\n".join(
                        f"  {cid}: {name}" for cid, name in class_map.items()
                    )
                    yaml_content = (
                        f"path: .\n"
                        f"train: train/images\n"
                        f"val: train/images\n"
                        f"names:\n"
                        f"{names_block}\n"
                    )
                    zf.writestr("data.yaml", yaml_content)

                task.import_annotations(
                    format_name="Ultralytics YOLO Detection 1.0",
                    filename=tmp_path
                )

                os.unlink(tmp_path)
                print("[✓] Labels uploaded as pre-annotations")
            else:
                print("[!] No label files found — uploading images only")
        else:
            print("[!] No labels folder found — uploading images only")

        print(f"\n{'=' * 40}")
        print(f"Task name  : {session_name}")
        print(f"Task ID    : {task.id}")
        print(f"Open CVAT  : http://localhost:8080/tasks/{task.id}/jobs")
        print(f"{'=' * 40}\n")


def main():
    # Step 1: Ask which session to upload
    frames_dir, labels_dir, session_name = ask_session()

    # Step 2: Ask for CVAT password
    password = getpass.getpass("Enter your CVAT password: ")

    print(f"\n[✓] Session : {session_name}")

    # Step 3: Upload to CVAT
    upload_to_cvat(frames_dir, labels_dir, session_name, password)


if __name__ == "__main__":
    main()