"""export_yolo — render an immutable commit into a YOLO-format dataset archive.

Reads a commit's pinned samples (image blob + annotation revision + split) and
the ontology's label classes (ordered by sort_order, which *is* the YOLO
class_id), then writes the standard YOLO layout::

    data.yaml
    images/{train,val,test}/<sample_id>.jpg
    labels/{train,val,test}/<sample_id>.txt   # "<class_id> cx cy w h" per box

The archive is a *deterministic* tar.gz: entries sorted, fixed mtime/uid/gid, so
the same commit + ontology always yields byte-identical bytes and therefore the
same content-addressed `export_blob_hash`. The coordinator's idempotency key
(type + config + inputs) already short-circuits re-runs; determinism here means
even a forced re-export dedupes to the same blob.

Layering: raw SQL via the engine session, blob bytes via ctx.storage.
"""

from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path

from cvops_api.engine.step import Step, StepContext

with open(Path(__file__).parent / "schemas" / "export_yolo.json") as f:
    _SCHEMA = json.load(f)

# Fixed tar metadata for reproducible archives.
_EPOCH = 0


class ExportYoloStep(Step):
    type_key = "step.export_yolo"
    config_schema = _SCHEMA

    async def run(self, ctx: StepContext, config: dict, inputs: dict) -> dict:
        from sqlalchemy import text  # noqa: PLC0415

        from cvops_api.config import settings  # noqa: PLC0415
        from cvops_api.core.storage import StorageBackend  # noqa: PLC0415

        commit_id = inputs["commit_id"]
        session = ctx.session

        commit = (
            await session.execute(
                text("SELECT ontology_id FROM commits WHERE id = CAST(:c AS uuid)"),
                {"c": commit_id},
            )
        ).first()
        if commit is None:
            raise ValueError(f"commit {commit_id!r} not found")
        ontology_id = config.get("ontology_id") or str(commit[0])

        # class_key → YOLO class_id, ordered by sort_order.
        class_rows = (
            await session.execute(
                text(
                    "SELECT class_key FROM label_classes "
                    "WHERE ontology_id = CAST(:o AS uuid) ORDER BY sort_order"
                ),
                {"o": ontology_id},
            )
        ).all()
        names = [r[0] for r in class_rows]
        class_index = {key: i for i, key in enumerate(names)}
        if not names:
            raise ValueError(f"ontology {ontology_id!r} has no label classes")

        # Pinned samples: blob bytes + annotation payload + split.
        rows = (
            await session.execute(
                text(
                    "SELECT cs.sample_id, cs.split, s.blob_hash, ar.payload "
                    "FROM commit_samples cs "
                    "JOIN samples s ON s.id = cs.sample_id "
                    "JOIN annotation_revisions ar ON ar.id = cs.annotation_revision_id "
                    "WHERE cs.commit_id = CAST(:c AS uuid) "
                    "ORDER BY cs.sample_id"
                ),
                {"c": commit_id},
            )
        ).all()

        data_yaml = self._data_yaml(names)
        # (arcname, bytes) entries; sorted before writing for determinism.
        entries: list[tuple[str, bytes]] = [("data.yaml", data_yaml.encode())]

        for sample_id, split, blob_hash, payload in rows:
            sid = str(sample_id)
            img_bytes = await ctx.storage.get_bytes(blob_hash)
            entries.append((f"images/{split}/{sid}.jpg", img_bytes))
            label_txt = self._label_lines(payload or [], class_index)
            entries.append((f"labels/{split}/{sid}.txt", label_txt.encode()))

        archive = self._make_tar_gz(entries)
        export_blob_hash = await ctx.storage.save_bytes(archive, "application/gzip")
        await session.execute(
            text(
                "INSERT INTO blobs (hash, storage_backend, storage_key, "
                "size_bytes, media_type) VALUES (:h, :sb, :sk, :sz, :mt) "
                "ON CONFLICT (hash) DO NOTHING"
            ),
            {
                "h": export_blob_hash,
                "sb": settings.S3_BACKEND,
                "sk": StorageBackend._bucket_key(export_blob_hash),
                "sz": len(archive),
                "mt": "application/gzip",
            },
        )

        return {
            "export_blob_hash": export_blob_hash,
            # Echo the source commit so downstream steps (e.g. train) can wire
            # $steps.<export>.outputs.commit_id without re-plumbing it through config.
            "commit_id": commit_id,
            "image_count": len(rows),
            "class_count": len(names),
        }

    @staticmethod
    def _data_yaml(names: list[str]) -> str:
        names_list = ", ".join(json.dumps(n) for n in names)
        return (
            f"nc: {len(names)}\n"
            f"names: [{names_list}]\n"
            "path: /data/dataset\n"
            "train: images/train\n"
            "val: images/val\n"
            "test: images/test\n"
        )

    @staticmethod
    def _label_lines(payload: list, class_index: dict[str, int]) -> str:
        """One YOLO line per box: `<class_id> cx cy w h` (normalized 0..1)."""
        lines: list[str] = []
        for ann in payload:
            key = ann.get("class_key")
            if key not in class_index:
                continue  # class not in this ontology version — skip, don't guess
            geom = ann.get("geometry") or {}
            coords = geom.get("coords")
            if not coords or len(coords) != 4:
                continue
            cx, cy, w, h = coords
            lines.append(f"{class_index[key]} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
        return "\n".join(lines) + ("\n" if lines else "")

    @staticmethod
    def _make_tar_gz(entries: list[tuple[str, bytes]]) -> bytes:
        """Deterministic tar.gz: sorted entries, fixed mtime/uid/gid, mtime=0 gzip."""
        raw = io.BytesIO()
        with tarfile.open(fileobj=raw, mode="w") as tar:
            for arcname, data in sorted(entries, key=lambda e: e[0]):
                info = tarfile.TarInfo(name=arcname)
                info.size = len(data)
                info.mtime = _EPOCH
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                tar.addfile(info, io.BytesIO(data))
        import gzip  # noqa: PLC0415

        out = io.BytesIO()
        # mtime=0 so the gzip header is reproducible too.
        with gzip.GzipFile(fileobj=out, mode="wb", mtime=_EPOCH) as gz:
            gz.write(raw.getvalue())
        return out.getvalue()
