"""
auto_label.py
-------------
Step 2 in the YOLO workflow: run YOLO12 nano on extracted frames
and generate label files in YOLO format (.txt) for each image.

Output structure:
    labels/
        <session_name>/
            image_1.txt
            image_2.txt
            ...

Each .txt file contains one line per detected object:
    <class_id> <x_center> <y_center> <width> <height>
    (all values normalized between 0 and 1)

Usage:
    python auto_label.py
    (the script will prompt you interactively for all settings)
"""

import os
from pathlib import Path
from ultralytics import YOLO


# Minimum confidence score to accept a detection (0.0 - 1.0)
DEFAULT_CONFIDENCE = 0.25


def ask_frames_folder() -> Path:
    """
    Ask the user which session folder to label.
    Looks inside the ./frames directory for available sessions.
    """
    frames_base = Path("./frames")

    # Check if frames folder exists
    if not frames_base.exists():
        print("[!] No 'frames' folder found. Run extract_frames.py first.")
        exit(1)

    # List all available session folders
    sessions = [f for f in frames_base.iterdir() if f.is_dir()]

    if not sessions:
        print("[!] No session folders found inside 'frames/'. Run extract_frames.py first.")
        exit(1)

    print("\n========================================")
    print("  Auto Labeling - Select Session        ")
    print("========================================")
    print("Available sessions:")

    for i, session in enumerate(sessions):
        count = len(list(session.glob("*.jpg")) + list(session.glob("*.png")))
        print(f"  {i + 1}. {session.name} ({count} images)")

    print("========================================")

    # Keep asking until user gives a valid choice
    while True:
        try:
            choice = int(input(f"Enter number (1-{len(sessions)}): ").strip())
            if 1 <= choice <= len(sessions):
                return sessions[choice - 1]
            print(f"  [!] Please enter a number between 1 and {len(sessions)}.")
        except ValueError:
            print("  [!] Please enter a valid number.")


def ask_confidence() -> float:
    """
    Ask the user for a confidence threshold.
    Higher = fewer but more certain detections.
    Lower = more detections but possibly noisy.
    """
    print(f"\nConfidence threshold (default: {DEFAULT_CONFIDENCE})")
    print("  Higher value = fewer but more certain detections")
    print("  Lower value  = more detections but possibly noisy")

    while True:
        raw = input(f"Enter confidence (0.0 - 1.0) or press Enter for default: ").strip()

        # Use default if user pressed Enter
        if raw == "":
            return DEFAULT_CONFIDENCE

        try:
            value = float(raw)
            if 0.0 <= value <= 1.0:
                return value
            print("  [!] Value must be between 0.0 and 1.0.")
        except ValueError:
            print("  [!] Please enter a valid number like 0.25 or 0.5.")


def run_auto_label(frames_dir: Path, output_dir: Path, confidence: float):
    """
    Run YOLO12 nano on all images in frames_dir and save .txt label files to output_dir.

    Args:
        frames_dir  -> folder containing the extracted frame images
        output_dir  -> folder where label .txt files will be saved
        confidence  -> minimum confidence threshold for detections
    """
    # Load the YOLO12 nano model (auto-downloaded by ultralytics if not present)
    print("\n[*] Loading YOLO12 nano model...")
    try:
        model = YOLO("yolo12n.pt")
    except Exception as e:
        print(f"[!] Failed to load YOLO model: {e}")
        return

    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect all image files from the session folder
    image_files = sorted(
        list(frames_dir.glob("*.jpg")) +
        list(frames_dir.glob("*.jpeg")) +
        list(frames_dir.glob("*.png"))
    )

    if not image_files:
        print(f"[!] No images found in: {frames_dir}")
        return

    print(f"[✓] Found {len(image_files)} images in session: {frames_dir.name}")
    print(f"[✓] Confidence threshold: {confidence}")
    print(f"[✓] Labels will be saved to: {output_dir}\n")

    total_detections = 0

    for image_path in image_files:
        # Run inference on the image (verbose=False suppresses per-image logs)
        results = model(image_path, conf=confidence, verbose=False)

        # Build the output .txt file path (same name as image, different extension)
        label_path = output_dir / (image_path.stem + ".txt")

        detections_in_image = 0

        with open(label_path, "w") as f:
            for result in results:
                # Each result contains boxes with normalized coordinates
                boxes = result.boxes

                for box in boxes:
                    # Get class id and normalized bounding box values
                    class_id = int(box.cls[0])
                    x_center = float(box.xywhn[0][0])   # normalized x center
                    y_center = float(box.xywhn[0][1])   # normalized y center
                    width    = float(box.xywhn[0][2])   # normalized width
                    height   = float(box.xywhn[0][3])   # normalized height

                    # Write one detection per line in YOLO format
                    f.write(f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")
                    detections_in_image += 1

        total_detections += detections_in_image
        print(f"  -> {image_path.name} | {detections_in_image} detections")

    # Print final summary
    print(f"\n{'=' * 40}")
    print(f"Session        : {frames_dir.name}")
    print(f"Images labeled : {len(image_files)}")
    print(f"Total detections: {total_detections}")
    print(f"Labels saved to : {output_dir}")
    print(f"{'=' * 40}\n")


def main():
    # Base labels output directory
    labels_base = Path("./labels")

    # Step 1: Ask user which session to label
    frames_dir = ask_frames_folder()

    # Step 2: Ask for confidence threshold
    confidence = ask_confidence()

    # Build output path: ./labels/<session_name>/
    output_dir = labels_base / frames_dir.name

    print(f"\n[✓] Session  : {frames_dir.name}")
    print(f"[✓] Confidence: {confidence}")

    # Step 3: Run auto labeling
    run_auto_label(frames_dir, output_dir, confidence)


if __name__ == "__main__":
    main()