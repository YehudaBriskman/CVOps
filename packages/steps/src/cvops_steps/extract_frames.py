"""extract_frames — decode a source video into frame samples using OpenCV.

Reads the source video blob, samples one frame every `interval_seconds` with
OpenCV, uploads each frame as a content-addressed JPEG blob, and registers a
`samples` row per frame. The source's lifecycle status is committed up front
(`ingesting`) and on any failure (`failed`) so a source never gets stuck in a
non-terminal state; the declared upload hash is verified lazily here.
"""

import hashlib
import json
import tempfile
from pathlib import Path

from cvops_api.engine.step import Step, StepContext

with open(Path(__file__).parent / "schemas" / "extract_frames.json") as f:
    _SCHEMA = json.load(f)


def _extract_frames_sync(
    video_bytes: bytes,
    interval_seconds: float,
    max_frames: int | None,
) -> list[dict]:
    """Blocking OpenCV decode. Returns extracted frames in order."""
    import cv2  # noqa: PLC0415

    frames: list[dict] = []

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(video_bytes)
        tmp_path = tmp.name

    cap = cv2.VideoCapture(tmp_path)
    try:
        if not cap.isOpened():
            raise ValueError("Could not open video")

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 1.0
        interval = max(1, int(fps * interval_seconds))

        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % interval == 0:
                height_px, width_px = frame.shape[:2]

                ok, buf = cv2.imencode(".jpg", frame)
                if not ok:
                    frame_idx += 1
                    continue
                data = buf.tobytes()

                # thumbnail: maintain aspect ratio, max 256px on longest side
                scale = 256 / max(height_px, width_px)
                thumb = cv2.resize(frame, (int(width_px * scale), int(height_px * scale)))
                ok2, tbuf = cv2.imencode(".jpg", thumb)
                thumb_data = tbuf.tobytes() if ok2 else data

                frames.append({
                    "data": data,
                    "thumb": thumb_data,
                    "width": width_px,
                    "height": height_px,
                    "frame_index": len(frames),
                })

                if max_frames and len(frames) >= max_frames:
                    break

            frame_idx += 1
    finally:
        cap.release()
        Path(tmp_path).unlink(missing_ok=True)

    return frames


class ExtractFramesStep(Step):
    type_key = "step.extract_frames"
    config_schema = _SCHEMA

    async def run(self, ctx: StepContext, config: dict, inputs: dict) -> dict:
        from sqlalchemy import text  # noqa: PLC0415

        source_id = inputs["source_id"]
        interval_seconds = float(config["interval_seconds"])
        max_frames = config.get("max_frames")

        async def _set_source_status(status: str) -> None:
            await ctx.session.execute(
                text(
                    "UPDATE data_sources SET status=:st, updated_at=now() "
                    "WHERE id = CAST(:sid AS uuid)"
                ),
                {"st": status, "sid": source_id},
            )

        try:
            return await self._ingest(
                ctx, config, source_id, interval_seconds, max_frames, _set_source_status
            )
        except Exception:
            # The coordinator rolls the shared session back on a raised step, which
            # would discard the in-flight 'ingesting' marker and leave the source
            # non-terminal forever. Commit a terminal 'failed' on a clean session
            # ourselves, then re-raise so the run is failed too.
            await ctx.session.rollback()
            await _set_source_status("failed")
            await ctx.session.commit()
            raise

    async def _ingest(
        self,
        ctx: StepContext,
        config: dict,
        source_id: str,
        interval_seconds: float,
        max_frames: int | None,
        set_status,
    ) -> dict:
        import asyncio  # noqa: PLC0415
        import uuid  # noqa: PLC0415

        from sqlalchemy import text  # noqa: PLC0415

        from cvops_api.config import settings  # noqa: PLC0415
        from cvops_api.core.storage import StorageBackend  # noqa: PLC0415

        row = (
            await ctx.session.execute(
                text("SELECT blob_hash FROM data_sources WHERE id = CAST(:sid AS uuid)"),
                {"sid": source_id},
            )
        ).first()
        if row is None or row[0] is None:
            raise ValueError(f"data source {source_id!r} has no uploaded blob")
        blob_hash = row[0]

        # Commit 'ingesting' immediately so the dashboard reflects the in-progress
        # state (the rest of this step commits atomically with the samples at the
        # end via the coordinator).
        await set_status("ingesting")
        await ctx.session.commit()

        video_bytes = await ctx.storage.get_bytes(blob_hash)
        # Lazy hash verification deferred from confirm-upload: we read the bytes
        # here anyway, so this is the natural place to catch a bad client hash.
        actual = "sha256:" + hashlib.sha256(video_bytes).hexdigest()
        if actual != blob_hash:
            raise ValueError(
                f"source blob hash mismatch: declared {blob_hash}, got {actual}"
            )

        frames = await asyncio.to_thread(
            _extract_frames_sync, video_bytes, interval_seconds, max_frames
        )

        async def _register_blob(blob_hash: str, data: bytes) -> None:
            await ctx.session.execute(
                text(
                    "INSERT INTO blobs (hash, storage_backend, storage_key, "
                    "size_bytes, media_type) VALUES (:h, :sb, :sk, :sz, :mt) "
                    "ON CONFLICT (hash) DO NOTHING"
                ),
                {
                    "h": blob_hash,
                    "sb": settings.S3_BACKEND,
                    "sk": StorageBackend._bucket_key(blob_hash),
                    "sz": len(data),
                    "mt": "image/jpeg",
                },
            )

        sample_ids: list[str] = []
        for fr in frames:
            frame_hash = await ctx.storage.save_bytes(fr["data"], "image/jpeg")
            thumb_hash = await ctx.storage.save_bytes(fr["thumb"], "image/jpeg")
            await _register_blob(frame_hash, fr["data"])
            await _register_blob(thumb_hash, fr["thumb"])
            # Generate the id rather than relying on a DB-side default: the ORM
            # model's id default is Python-side, so a schema built from models
            # (e.g. tests) has no server default for it.
            res = await ctx.session.execute(
                text(
                    "INSERT INTO samples (id, project_id, blob_hash, source_id, width, "
                    "height, frame_index, thumbnail_hash) VALUES "
                    "(CAST(:id AS uuid), CAST(:pid AS uuid), :bh, CAST(:sid AS uuid), "
                    ":w, :h, :fi, :th) "
                    "ON CONFLICT (project_id, blob_hash) DO NOTHING RETURNING id"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "pid": ctx.project_id,
                    "bh": frame_hash,
                    "sid": source_id,
                    "w": fr["width"],
                    "h": fr["height"],
                    "fi": fr["frame_index"],
                    "th": thumb_hash,
                },
            )
            new = res.first()
            if new is not None:
                sample_ids.append(str(new[0]))
            else:
                # Identical frame already a sample in this project — reuse its id.
                existing = (
                    await ctx.session.execute(
                        text(
                            "SELECT id FROM samples WHERE project_id = CAST(:pid AS uuid) "
                            "AND blob_hash = :bh"
                        ),
                        {"pid": ctx.project_id, "bh": frame_hash},
                    )
                ).first()
                if existing is not None:
                    sample_ids.append(str(existing[0]))

        # Terminal success — committed atomically with the samples above by the
        # coordinator after run() returns. Reached even when zero frames were
        # kept, so a video that yields nothing still lands in a terminal state.
        await set_status("ingested")

        return {"sample_ids": sample_ids, "frame_count": len(sample_ids)}
