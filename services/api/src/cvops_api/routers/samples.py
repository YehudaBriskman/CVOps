from __future__ import annotations

import base64
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cvops_api.core.auth import get_current_user
from cvops_api.core.storage import get_storage
from cvops_api.db.session import get_session
from cvops_api.db.models.auth import User
from cvops_api.db.models.projects import Project
from cvops_api.db.models.samples import Sample
from cvops_api.db.models.annotations import AnnotationRevision
from cvops_api.db.models.ontologies import Ontology
from cvops_api.schemas.samples import (
    SampleOut,
    AnnotationRevisionOut,
    AnnotationCreate,
    CursorPage,
)

router = APIRouter()


async def _check_project(
    project_id: uuid.UUID,
    current_user: User,
    session: AsyncSession,
) -> Project:
    r = await session.execute(
        select(Project).where(
            Project.id == project_id,
            Project.org_id == current_user.org_id,
            Project.deleted_at == None,  # noqa: E711
        )
    )
    proj = r.scalar_one_or_none()
    if proj is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj


@router.get(
    "/projects/{project_id}/samples",
    response_model=CursorPage[SampleOut],
)
async def list_samples(
    project_id: uuid.UUID,
    cursor: str | None = Query(None),
    source_id: uuid.UUID | None = Query(None),
    limit: int = Query(50, le=200),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CursorPage[SampleOut]:
    await _check_project(project_id, current_user, session)

    q = select(Sample).where(Sample.project_id == project_id)

    if source_id is not None:
        q = q.where(Sample.source_id == source_id)

    if cursor is not None:
        cursor_uuid = uuid.UUID(base64.b64decode(cursor).decode())
        q = q.where(Sample.id > cursor_uuid)

    q = q.order_by(Sample.id).limit(limit + 1)

    r = await session.execute(q)
    items = list(r.scalars().all())

    next_cursor: str | None = None
    if len(items) == limit + 1:
        next_cursor = base64.b64encode(str(items[-1].id).encode()).decode()
        items = items[:limit]

    return CursorPage(
        items=[SampleOut.model_validate(s) for s in items],
        next_cursor=next_cursor,
    )


@router.get("/samples/{id}", response_model=SampleOut)
async def get_sample(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SampleOut:
    r = await session.execute(select(Sample).where(Sample.id == id))
    s = r.scalar_one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail="Sample not found")
    await _check_project(s.project_id, current_user, session)
    return SampleOut.model_validate(s)


@router.get("/samples/{id}/image-url")
async def get_image_url(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    r = await session.execute(select(Sample).where(Sample.id == id))
    s = r.scalar_one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail="Sample not found")
    await _check_project(s.project_id, current_user, session)
    url = await get_storage().get_presigned_get(s.blob_hash)
    return {"url": url}


@router.get("/samples/{id}/thumbnail-url")
async def get_thumbnail_url(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    r = await session.execute(select(Sample).where(Sample.id == id))
    s = r.scalar_one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail="Sample not found")
    await _check_project(s.project_id, current_user, session)
    if s.thumbnail_hash is None:
        raise HTTPException(status_code=404, detail="No thumbnail")
    url = await get_storage().get_presigned_get(s.thumbnail_hash)
    return {"url": url}


@router.get("/samples/{id}/annotations", response_model=list[AnnotationRevisionOut])
async def list_annotations(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[AnnotationRevisionOut]:
    r = await session.execute(select(Sample).where(Sample.id == id))
    sample = r.scalar_one_or_none()
    if sample is None:
        raise HTTPException(status_code=404, detail="Sample not found")
    await _check_project(sample.project_id, current_user, session)

    r2 = await session.execute(
        select(AnnotationRevision)
        .where(AnnotationRevision.sample_id == sample.id)
        .order_by(AnnotationRevision.revision_no)
    )
    return [AnnotationRevisionOut.model_validate(rev) for rev in r2.scalars().all()]


@router.post(
    "/samples/{id}/annotations",
    response_model=AnnotationRevisionOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_annotation(
    id: uuid.UUID,
    body: AnnotationCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AnnotationRevisionOut:
    r = await session.execute(select(Sample).where(Sample.id == id))
    sample = r.scalar_one_or_none()
    if sample is None:
        raise HTTPException(status_code=404, detail="Sample not found")
    await _check_project(sample.project_id, current_user, session)

    # Get current max revision_no (default 0 if no revisions yet)
    r_max = await session.execute(
        select(func.max(AnnotationRevision.revision_no)).where(
            AnnotationRevision.sample_id == sample.id
        )
    )
    max_no: int = r_max.scalar() or 0

    # Find ontology version
    r_ont = await session.execute(select(Ontology.version).where(Ontology.id == body.ontology_id))
    ontology_version = r_ont.scalar_one_or_none()
    if ontology_version is None:
        raise HTTPException(status_code=404, detail="Ontology not found")

    rev = AnnotationRevision(
        sample_id=sample.id,
        project_id=sample.project_id,
        ontology_id=body.ontology_id,
        ontology_version=ontology_version,
        revision_no=max_no + 1,
        payload=body.payload,
        provenance=body.provenance,
    )
    session.add(rev)
    await session.commit()
    return AnnotationRevisionOut.model_validate(rev)
