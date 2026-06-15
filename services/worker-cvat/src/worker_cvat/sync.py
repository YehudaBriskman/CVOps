"""CVAT pull flow — reconcile a completed CVAT task back into CVOps.

Triggered by a ``{kind: "cvat_sync", cvat_task_id}`` doorbell that the API's
webhook bridge XADDs onto the cvat stream (see routers/internal.py). Handles the
"human finished reviewing" half of the gate:

  1. Load the labeling_job by cvat_task_id; short-circuit if already completed
     (idempotent against duplicate webhook / future poll events).
  2. Read the ordered sample_ids the push flow stored in the gate_data, and each
     sample's dimensions — this is the frame → sample mapping.
  3. Pull reviewed annotations from CVAT, converting pixel rects to canonical
     normalized boxes (done in cvops_cvat_client).
  4. Append a 'human'/'accepted' annotation_revision per sample (inheriting the
     ontology from the sample's latest prior revision).
  5. Mark the labeling_job completed and the waiting gate run succeeded, then
     advance the workflow in-process so the next step (e.g. commit_dataset) is
     enqueued — mirroring the resolve_gate endpoint.

Chaining is in-process (advance_workflow) rather than via HTTP, because this
worker links cvops_api directly and the POST /internal/runs/{id}/advance
endpoint does not exist.
"""

from __future__ import annotations

import json
import logging
import uuid

from sqlalchemy import text

from cvops_api.engine.coordinator import advance_workflow
from cvops_worker_common.session import async_session_factory

logger = logging.getLogger(__name__)

# Worker-driven actions with no explicit user are attributed to this system id
# (matches worker-preprocessing's SYSTEM_ACTOR_ID).
SYSTEM_ACTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")


async def handle_cvat_sync(fields: dict[str, str]) -> None:
    from cvops_cvat_client import pull_review_task  # lazy: pulls cvat_sdk

    cvat_task_id = int(fields["cvat_task_id"])

    async with async_session_factory() as session:
        lj = (
            await session.execute(
                text(
                    "SELECT id, run_id, status FROM labeling_jobs "
                    "WHERE cvat_task_id = :t"
                ),
                {"t": cvat_task_id},
            )
        ).first()
        if lj is None:
            logger.warning("cvat_sync: no labeling_job for cvat_task_id=%s", cvat_task_id)
            return
        labeling_job_id, run_id, status = str(lj[0]), str(lj[1]), lj[2]
        if status == "completed":
            return  # already reconciled — duplicate event

        run = (
            await session.execute(
                text(
                    "SELECT parent_run_id, project_id, output_refs "
                    "FROM runs WHERE id = CAST(:r AS uuid)"
                ),
                {"r": run_id},
            )
        ).first()
        if run is None:
            logger.error("cvat_sync: gate run %s missing for job %s", run_id, labeling_job_id)
            return
        parent_run_id = str(run[0]) if run[0] else None
        project_id = str(run[1])
        gate_data = (run[2] or {}).get("gate_data", {})
        sample_ids = [str(s) for s in gate_data.get("sample_ids", [])]
        if not sample_ids:
            logger.error("cvat_sync: job %s gate_data has no sample_ids", labeling_job_id)
            return

        # frame index → sample dims, in push/upload order.
        dim_rows = (
            await session.execute(
                text("SELECT id, width, height FROM samples WHERE id = ANY(CAST(:ids AS uuid[]))"),
                {"ids": sample_ids},
            )
        ).all()
        dims = {str(sid): (w, h) for sid, w, h in dim_rows}
        frame_dims = [dims[s] for s in sample_ids]

        by_frame = pull_review_task(cvat_task_id, frame_dims)  # {frame: [canonical ann]}

        out_rev_ids: list[str] = []
        for frame, anns in by_frame.items():
            if frame >= len(sample_ids):
                continue
            sid = sample_ids[frame]
            prev = (
                await session.execute(
                    text(
                        "SELECT revision_no, ontology_id, ontology_version, id "
                        "FROM annotation_revisions WHERE sample_id = CAST(:s AS uuid) "
                        "ORDER BY revision_no DESC LIMIT 1"
                    ),
                    {"s": sid},
                )
            ).first()
            if prev is None:
                # No prior revision → no ontology to inherit. The working-set
                # flow always auto_labels first, so this is rare; skip + log
                # rather than guess an ontology.
                logger.warning("cvat_sync: sample %s has no prior revision; skipping", sid)
                continue
            prev_no, ont_id, ont_ver, parent_id = prev[0], str(prev[1]), prev[2], str(prev[3])
            new_id = str(uuid.uuid4())
            await session.execute(
                text(
                    "INSERT INTO annotation_revisions (id, project_id, sample_id, "
                    "ontology_id, ontology_version, revision_no, parent_revision_id, "
                    "payload, provenance) VALUES "
                    "(CAST(:id AS uuid), CAST(:pid AS uuid), CAST(:sid AS uuid), "
                    "CAST(:oid AS uuid), :ov, :rev, CAST(:parent AS uuid), "
                    "CAST(:payload AS jsonb), CAST(:prov AS jsonb))"
                ),
                {
                    "id": new_id,
                    "pid": project_id,
                    "sid": sid,
                    "oid": ont_id,
                    "ov": ont_ver,
                    "rev": prev_no + 1,
                    "parent": parent_id,
                    "payload": json.dumps(anns),
                    "prov": json.dumps(
                        {"source": "human", "review_status": "accepted", "author_user_id": None}
                    ),
                },
            )
            out_rev_ids.append(new_id)

        await session.execute(
            text(
                "UPDATE labeling_jobs SET status='completed', completed_at=now(), "
                "annotation_revision_ids_out = CAST(:out AS jsonb) "
                "WHERE id = CAST(:id AS uuid)"
            ),
            {"out": json.dumps(out_rev_ids), "id": labeling_job_id},
        )

        # Resume the gate: the waiting child run is the labeling_job's run_id.
        await session.execute(
            text(
                "UPDATE runs SET status='succeeded', finished_at=now(), "
                "output_refs = CAST(:o AS jsonb) WHERE id = CAST(:r AS uuid)"
            ),
            {
                "o": json.dumps(
                    {"resolution": "approved", "annotation_revision_ids": out_rev_ids}
                ),
                "r": run_id,
            },
        )
        await session.commit()
        logger.info(
            "cvat_sync: job %s completed (%d revisions); resuming run %s",
            labeling_job_id,
            len(out_rev_ids),
            run_id,
        )

        # Enqueue whatever became ready downstream (e.g. step.commit_dataset).
        if parent_run_id:
            await advance_workflow(session, parent_run_id, SYSTEM_ACTOR_ID)
            await session.commit()
