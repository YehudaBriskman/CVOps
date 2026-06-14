"""
extract_frames.py
-----------------
Step 1 in the YOLO workflow: extract frames from videos, upload to MinIO,
and register blobs + samples in PostgreSQL.

Required env vars (or a .env file in this directory):
    PROJECT_ID          UUID of an existing project in the database
    DATABASE_URL        postgresql://user:pass@host:5432/db
    MINIO_ENDPOINT      default: http://localhost:9000
    MINIO_ACCESS_KEY    default: minioadmin
    MINIO_SECRET_KEY    default: minioadmin
    MINIO_BUCKET        default: cvops-blobs

Usage:
    python extract_frames.py
"""

import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

import boto3
import cv2
import psycopg2
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

MINIO_ENDPOINT   = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET     = os.getenv("MINIO_BUCKET", "cvops-blobs")
PROJECT_ID       = os.getenv("PROJECT_ID", "")

# Strip async driver prefix so psycopg2 can use the same DATABASE_URL
_raw_db_url = os.getenv("DATABASE_URL", "postgresql://cvops:cvops@localhost:5432/cvops")
DATABASE_URL = _raw_db_url.replace("postgresql+asyncpg://", "postgresql://")

SUPPORTED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm"}
STORAGE_BACKEND = "minio"


# ── MinIO helpers ────────────────────────────────────────────────────────────

def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _bucket_key(blob_hash: str) -> str:
    """blobs/{first2}/{rest} — avoids hot-spotting in MinIO at scale."""
    hex_part = blob_hash.removeprefix("sha256:")
    return f"blobs/{hex_part[:2]}/{hex_part[2:]}"


def build_minio_client():
    client = boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
    )
    try:
        client.head_bucket(Bucket=MINIO_BUCKET)
    except Exception:
        client.create_bucket(Bucket=MINIO_BUCKET)
    return client


def upload_blob(minio_client, data: bytes, media_type: str) -> tuple[str, str]:
    """Upload bytes to MinIO (dedup by hash). Returns (blob_hash, storage_key)."""
    blob_hash = _sha256(data)
    key = _bucket_key(blob_hash)
    try:
        minio_client.head_object(Bucket=MINIO_BUCKET, Key=key)
    except Exception:
        minio_client.put_object(
            Bucket=MINIO_BUCKET, Key=key, Body=data, ContentType=media_type
        )
    return blob_hash, key


# ── Postgres helpers ─────────────────────────────────────────────────────────

def pg_register_blob(cur, blob_hash: str, storage_key: str, size_bytes: int, media_type: str) -> None:
    cur.execute(
        """
        INSERT INTO blobs (hash, storage_backend, storage_key, size_bytes, media_type)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (hash) DO NOTHING
        """,
        (blob_hash, STORAGE_BACKEND, storage_key, size_bytes, media_type),
    )


def pg_create_data_source(cur, project_id: str, video_name: str) -> str:
    source_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO data_sources (id, project_id, type, status, metadata)
        VALUES (%s::uuid, %s::uuid, 'video', 'processing', %s::jsonb)
        """,
        (source_id, project_id, json.dumps({"filename": video_name})),
    )
    return source_id


def pg_register_sample(
    cur,
    project_id: str,
    blob_hash: str,
    source_id: str,
    width: int,
    height: int,
    frame_index: int,
) -> None:
    cur.execute(
        """
        INSERT INTO samples (id, project_id, blob_hash, source_id, width, height, frame_index)
        VALUES (%s::uuid, %s::uuid, %s, %s::uuid, %s, %s, %s)
        ON CONFLICT (project_id, blob_hash) DO NOTHING
        """,
        (str(uuid.uuid4()), project_id, blob_hash, source_id, width, height, frame_index),
    )


def pg_set_source_processed(cur, source_id: str) -> None:
    cur.execute(
        "UPDATE data_sources SET status = 'processed', updated_at = now() WHERE id = %s::uuid",
        (source_id,),
    )


# ── Interactive prompts ───────────────────────────────────────────────────────

def ask_output_name() -> str:
    print("\n========================================")
    print("  Frame Extraction - Session Name       ")
    print("========================================")
    while True:
        name = input("Enter a name for this session (e.g. test, script, run1): ").strip()
        if not name:
            print("  [!] Name cannot be empty. Please try again.")
            continue
        return name.replace(" ", "_")


def ask_interval_mode() -> tuple:
    print("\n========================================")
    print("  Frame Extraction - Interval Settings  ")
    print("========================================")
    print("Choose interval mode:")
    print("  1. Time-based  (extract one frame every N seconds)")
    print("  2. FPS-based   (extract one frame every N frames)")
    print("========================================")
    while True:
        choice = input("Enter 1 or 2: ").strip()
        if choice == "1":
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


# ── Core extraction ───────────────────────────────────────────────────────────

def extract_and_ingest(
    video_path: Path,
    project_id: str,
    minio_client,
    pg_conn,
    mode: str,
    interval_value: float,
    frame_counter_start: int = 0,
) -> int:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"  [!] Could not open video: {video_path.name}")
        return 0

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        print(f"  [!] Warning: could not read FPS for {video_path.name}, defaulting to 1 fps")
        fps = 1.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    interval = max(1, int(fps * interval_value)) if mode == "time" else max(1, int(interval_value))
    print(f"  -> {video_path.name} | {fps:.1f} fps | {total_frames} frames | interval: every {interval} frames")

    with pg_conn.cursor() as cur:
        source_id = pg_create_data_source(cur, project_id, video_path.name)
        pg_conn.commit()

    saved = 0
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % interval == 0:
            height_px, width_px = frame.shape[:2]
            global_idx = frame_counter_start + saved + 1

            ok, buf = cv2.imencode(".jpg", frame)
            if not ok:
                print(f"  [!] Warning: failed to encode frame {global_idx}")
                frame_idx += 1
                continue

            data = buf.tobytes()
            blob_hash, storage_key = upload_blob(minio_client, data, "image/jpeg")

            with pg_conn.cursor() as cur:
                pg_register_blob(cur, blob_hash, storage_key, len(data), "image/jpeg")
                pg_register_sample(cur, project_id, blob_hash, source_id, width_px, height_px, global_idx)
                pg_conn.commit()

            saved += 1

        frame_idx += 1

    cap.release()

    with pg_conn.cursor() as cur:
        pg_set_source_processed(cur, source_id)
        pg_conn.commit()

    print(f"     Uploaded {saved} frames")
    return saved


def run(input_dir: Path, project_id: str, session_name: str, mode: str, interval_value: float):
    print("\n[*] Connecting to MinIO and PostgreSQL...")
    minio_client = build_minio_client()
    pg_conn = psycopg2.connect(DATABASE_URL)

    video_files = sorted([
        f for f in input_dir.iterdir()
        if f.suffix.lower() in SUPPORTED_EXTENSIONS
    ])

    if not video_files:
        pg_conn.close()
        print(f"\n[!] No videos found in: {input_dir}")
        return

    print(f"\n[✓] Found {len(video_files)} video(s)")
    print(f"[✓] Project ID  : {project_id}")
    print(f"[✓] MinIO bucket: {MINIO_BUCKET}\n")

    total_saved = 0
    for video_path in video_files:
        saved = extract_and_ingest(
            video_path=video_path,
            project_id=project_id,
            minio_client=minio_client,
            pg_conn=pg_conn,
            mode=mode,
            interval_value=interval_value,
            frame_counter_start=total_saved,
        )
        total_saved += saved

    pg_conn.close()

    print(f"\n{'=' * 40}")
    print(f"Session name   : {session_name}")
    print(f"Total frames   : {total_saved}")
    print(f"Stored in      : MinIO bucket '{MINIO_BUCKET}'")
    print(f"{'=' * 40}\n")


def main():
    if not PROJECT_ID:
        print("[!] PROJECT_ID env var is required.")
        print("    Set it in tools/frame-extractor/.env or export it before running.")
        sys.exit(1)

    input_dir = Path("./videos")
    if not input_dir.exists():
        print(f"[!] Input folder not found: {input_dir}")
        sys.exit(1)

    session_name = ask_output_name()
    mode, interval_value = ask_interval_mode()

    print(f"\n[✓] Session  : {session_name}")
    print(f"[✓] Mode     : {'Time-based' if mode == 'time' else 'FPS-based'} | Value: {interval_value}")

    run(input_dir, PROJECT_ID, session_name, mode, interval_value)


if __name__ == "__main__":
    main()