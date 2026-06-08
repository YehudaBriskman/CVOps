"""
extract_frames.py
-----------------
Step 1 in the YOLO workflow: extract frames from videos into a named output folder.

Usage:
    python extract_frames.py
    (the script will prompt you interactively for all settings)
"""

import cv2
from pathlib import Path


# Supported video file extensions
SUPPORTED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm"}


def ask_output_name() -> str:
    """
    Ask the user for a session name.
    This name will be used as the output folder name and as the prefix for all saved frames.
    Example: user types "test" -> folder: ./frames/test -> files: test_1.jpg, test_2.jpg ...
    """
    print("\n========================================")
    print("  Frame Extraction - Session Name       ")
    print("========================================")

    while True:
        name = input("Enter a name for this session (e.g. test, script, run1): ").strip()

        # Make sure the name is not empty
        if not name:
            print("  [!] Name cannot be empty. Please try again.")
            continue

        # Replace spaces with underscores to keep filenames clean
        name = name.replace(" ", "_")
        return name


def ask_interval_mode() -> tuple:
    """
    Prompt the user to choose between time-based or fps-based interval mode.
    Returns a tuple: (mode, value)
        mode  -> "time" or "fps"
        value -> seconds (float) or frame interval (int)
    """
    print("\n========================================")
    print("  Frame Extraction - Interval Settings  ")
    print("========================================")
    print("Choose interval mode:")
    print("  1. Time-based  (extract one frame every N seconds)")
    print("  2. FPS-based   (extract one frame every N frames)")
    print("========================================")

    # Keep asking until user gives a valid choice
    while True:
        choice = input("Enter 1 or 2: ").strip()

        if choice == "1":
            # Time-based mode: ask for seconds
            while True:
                try:
                    seconds = float(input("Extract one frame every how many seconds? (e.g. 1.0): ").strip())
                    if seconds <= 0:
                        print("  [!] Value must be greater than 0.")
                        continue
                    return ("time", seconds)
                except ValueError:
                    print("  [!] Please enter a valid number (e.g. 1.0 or 2.5).")

        elif choice == "2":
            # FPS-based mode: ask for frame interval
            while True:
                try:
                    n_frames = int(input("Extract one frame every how many frames? (e.g. 10): ").strip())
                    if n_frames <= 0:
                        print("  [!] Value must be greater than 0.")
                        continue
                    return ("fps", n_frames)
                except ValueError:
                    print("  [!] Please enter a valid integer (e.g. 10 or 30).")

        else:
            print("  [!] Invalid choice. Please enter 1 or 2.")


def extract_frames(
    video_path: Path,
    output_dir: Path,
    session_name: str,
    mode: str,
    interval_value: float,
    frame_counter_start: int = 0,
) -> int:
    """
    Extract frames from a single video and save them to the output directory.

    Args:
        video_path          -> path to the video file
        output_dir          -> folder where frames will be saved
        session_name        -> prefix used for all saved frame filenames
        mode                -> "time" or "fps"
        interval_value      -> seconds (if time mode) or frame count (if fps mode)
        frame_counter_start -> global frame index offset (for multi-video runs)

    Returns:
        Number of frames saved from this video
    """
    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        print(f"  [!] Could not open video: {video_path.name}")
        return 0

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Calculate the frame interval based on the chosen mode
    if mode == "time":
        # Convert seconds to number of frames using the video's FPS
        interval = max(1, int(fps * interval_value))
    else:
        # FPS mode: use the value directly as a frame interval
        interval = max(1, int(interval_value))

    print(f"  -> {video_path.name} | {fps:.1f} fps | {total_frames} frames | interval: every {interval} frames")

    saved = 0
    frame_idx = 0

    while True:
        ret, frame = cap.read()

        # Stop when the video ends or cannot be read
        if not ret:
            break

        # Save the frame if it falls on the interval boundary
        if frame_idx % interval == 0:
            # File name format: sessionname_1.jpg, sessionname_2.jpg ...
            # Index starts at 1 (not 0) for readability
            global_idx = frame_counter_start + saved + 1
            filename = f"{session_name}_{global_idx}.jpg"
            out_path = output_dir / filename
            cv2.imwrite(str(out_path), frame)
            saved += 1

        frame_idx += 1

    cap.release()
    print(f"     Saved {saved} frames")
    return saved


def run(input_dir: Path, output_dir: Path, session_name: str, mode: str, interval_value: float):
    """
    Main runner: finds all videos in input_dir and extracts frames from each one.
    """
    # Create the session output folder: ./frames/<session_name>/
    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect all supported video files, sorted alphabetically
    video_files = sorted([
        f for f in input_dir.iterdir()
        if f.suffix.lower() in SUPPORTED_EXTENSIONS
    ])

    if not video_files:
        print(f"\n[!] No videos found in: {input_dir}")
        return

    print(f"\n[✓] Found {len(video_files)} video(s)")
    print(f"[✓] Output folder: {output_dir}")
    print(f"[✓] Files will be named: {session_name}_1.jpg, {session_name}_2.jpg ...\n")

    total_saved = 0

    # Process each video one by one
    for video_path in video_files:
        saved = extract_frames(
            video_path=video_path,
            output_dir=output_dir,
            session_name=session_name,
            mode=mode,
            interval_value=interval_value,
            frame_counter_start=total_saved,
        )
        total_saved += saved

    # Print final summary
    print(f"\n{'=' * 40}")
    print(f"Session name   : {session_name}")
    print(f"Total frames   : {total_saved}")
    print(f"Saved to       : {output_dir}")
    print(f"{'=' * 40}\n")


def main():
    # --- Base paths ---
    input_dir = Path("./videos")
    base_output_dir = Path("./frames")

    # Validate that the input folder exists before doing anything
    if not input_dir.exists():
        print(f"[!] Input folder not found: {input_dir}")
        return

    # Step 1: Ask user for a session name
    session_name = ask_output_name()

    # Build the final output path: ./frames/<session_name>/
    output_dir = base_output_dir / session_name

    # Step 2: Ask user to choose interval mode
    mode, interval_value = ask_interval_mode()

    print(f"\n[✓] Session  : {session_name}")
    print(f"[✓] Mode     : {'Time-based' if mode == 'time' else 'FPS-based'} | Value: {interval_value}")

    # Step 3: Start the extraction process
    run(input_dir, output_dir, session_name, mode, interval_value)


if __name__ == "__main__":
    main()