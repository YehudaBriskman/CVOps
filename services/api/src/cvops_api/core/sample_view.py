"""
Shared SampleOut enrichment. Used by the samples list/get/patch endpoints and
the collection "list samples" endpoint so they all return tags + annotation
summary without N+1 queries: two batch queries per page, independent of page size.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cvops_api.db.models.annotations import AnnotationRevision
from cvops_api.db.models.samples import Sample
from cvops_api.db.models.tags import SampleTag, Tag
from cvops_api.schemas.samples import SampleOut, TagBrief


async def build_sample_outs(session: AsyncSession, samples: Sequence[Sample]) -> list[SampleOut]:
    """Build enriched SampleOut objects for a page of Sample ORM rows."""
    if not samples:
        return []

    ids = [s.id for s in samples]

    # Tags for the whole page in one query (skip soft-deleted tags).
    tag_rows = await session.execute(
        select(SampleTag.sample_id, Tag.id, Tag.name, Tag.color)
        .join(Tag, Tag.id == SampleTag.tag_id)
        .where(SampleTag.sample_id.in_(ids), Tag.deleted_at.is_(None))
    )
    tags_by_sample: dict[uuid.UUID, list[TagBrief]] = defaultdict(list)
    for sid, tid, name, color in tag_rows:
        tags_by_sample[sid].append(TagBrief(id=tid, name=name, color=color))

    # Latest annotation revision id per sample via DISTINCT ON.
    rev_rows = await session.execute(
        select(AnnotationRevision.sample_id, AnnotationRevision.id)
        .where(AnnotationRevision.sample_id.in_(ids))
        .distinct(AnnotationRevision.sample_id)
        .order_by(AnnotationRevision.sample_id, AnnotationRevision.revision_no.desc())
    )
    latest_by_sample: dict[uuid.UUID, uuid.UUID] = {sid: rid for sid, rid in rev_rows}

    out: list[SampleOut] = []
    for s in samples:
        view = SampleOut.model_validate(s)
        view.tags = tags_by_sample.get(s.id, [])
        view.latest_revision_id = latest_by_sample.get(s.id)
        view.has_annotations = s.id in latest_by_sample
        out.append(view)
    return out
