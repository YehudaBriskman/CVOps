"""extract_frames — decode a source video into deduplicated frame samples.

Consumes a data source's video blob, samples one frame every
`interval_seconds` via ffmpeg, suppresses near-duplicate frames by perceptual
hash, uploads each kept frame as a content-addressed JPEG blob, and registers a
`samples` row per frame.

Layering: steps may only touch cvops_api.core (storage) and the engine contract,
not cvops_api.db.models or routers. Sample/blob rows are therefore written with
parameterized raw SQL through the engine-provided session. Heavy deps
(ffmpeg/imagehash/PIL) are imported inside run() so importing this module for
registration stays cheap and never fails on a missing extra.
"""

import hashlib
import io
import json
import tempfile
from pathlib import Path

from cvops_api.engine.step import Step, StepContext

with open(Path(__file__).parent / "schemas" / "extract_frames.json") as f:
    _SCHEMA = json.load(f)

# average_hash default is an 8x8 grid → 64-bit hash. dedup_threshold (0..1) is
# scaled to a max Hamming distance against this width.
_HASH_BITS = 64


def _extract_frames_sync(
    video_bytes: bytes,
    fps: float,
    max_frames: int | None,
    max_distance: int,
) -> list[dict]:
    """Blocking ffmpeg decode + perceptual dedup. Returns kept frames in order."""
    import ffmpeg  # noqa: PLC0415 — heavy, imported lazily
    import imagehash  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415

    frames: list[dict] = []
    kept_hashes: list = []

    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        in_path = tdp / "input.bin"
        in_path.write_bytes(video_bytes)
        out_pattern = str(tdp / "f_%06d.jpg")

        stream = ffmpeg.input(str(in_path)).filter("fps", fps=fps)
        kwargs: dict = {}
        if max_frames:
            kwargs["vframes"] = int(max_frames)
        stream.output(out_pattern, **kwargs).run(quiet=True, overwrite_output=True)

        idx = 0
        for jpg in sorted(tdp.glob("f_*.jpg")):
            data = jpg.read_bytes()
            with Image.open(io.BytesIO(data)) as img:
                img = img.convert("RGB")
                width, height = img.size
                phash = imagehash.average_hash(img)

                if max_distance > 0 and any((phash - k) <= max_distance for k in kept_hashes):
                    continue

                # 256x256 thumbnail for the UI grid (samples.thumbnail_hash).
                thumb = img.copy()
                thumb.thumbnail((256, 256))
                tbuf = io.BytesIO()
                thumb.save(tbuf, format="JPEG")
                thumb_bytes = tbuf.getvalue()

            kept_hashes.append(phash)
            frames.append(
                {
                    "data": data,
                    "thumb": thumb_bytes,
                    "width": width,
                    "height": height,
                    "phash": str(phash),
                    "frame_index": idx,
                }
            )
            idx += 1

    return frames


class ExtractFramesStep(Step):
    type_key = "step.extract_frames"
    config_schema = _SCHEMA

    async def run(self, ctx: StepContext, config: dict, inputs: dict) -> dict:
        import asyncio  # noqa: PLC0415
        import uuid  # noqa: PLC0415

        from sqlalchemy import text  # noqa: PLC0415

        from cvops_api.config import settings  # noqa: PLC0415
        from cvops_api.core.storage import StorageBackend  # noqa: PLC0415

        source_id = inputs["source_id"]
        interval = float(config["interval_seconds"])
        max_frames = config.get("max_frames")
        max_distance = round(float(config.get("dedup_threshold", 0.0)) * _HASH_BITS)

        row = (
            await ctx.session.execute(
                text("SELECT blob_hash FROM data_sources WHERE id = CAST(:sid AS uuid)"),
                {"sid": source_id},
            )
        ).first()
        if row is None or row[0] is None:
            raise ValueError(f"data source {source_id!r} has no uploaded blob")
        blob_hash = row[0]

        await ctx.session.execute(
            text(
                "UPDATE data_sources SET status='ingesting', updated_at=now() "
                "WHERE id = CAST(:sid AS uuid)"
            ),
            {"sid": source_id},
        )

        video_bytes = await ctx.storage.get_bytes(blob_hash)
        # Lazy hash verification deferred from confirm-upload: we read the bytes
        # here anyway, so this is the natural place to catch a bad client hash.
        actual = "sha256:" + hashlib.sha256(video_bytes).hexdigest()
        if actual != blob_hash:
            raise ValueError(
                f"source blob hash mismatch: declared {blob_hash}, got {actual}"
            )

        frames = await asyncio.to_thread(
            _extract_frames_sync, video_bytes, 1.0 / interval, max_frames, max_distance
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
                    "height, frame_index, perceptual_hash, thumbnail_hash) VALUES "
                    "(CAST(:id AS uuid), CAST(:pid AS uuid), :bh, CAST(:sid AS uuid), "
                    ":w, :h, :fi, :ph, :th) "
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
                    "ph": fr["phash"],
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

        await ctx.session.execute(
            text(
                "UPDATE data_sources SET status='ingested', updated_at=now() "
                "WHERE id = CAST(:sid AS uuid)"
            ),
            {"sid": source_id},
        )

        return {"sample_ids": sample_ids, "frame_count": len(sample_ids)}
