from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cvops_api.core.auth import get_current_user
from cvops_api.core.storage import get_storage
from cvops_api.db.session import get_session
from cvops_api.db.models.auth import User
from cvops_api.db.models.projects import Project
from cvops_api.db.models.models import ModelVersion
from cvops_api.schemas.models import ModelVersionOut

router = APIRouter()


async def _get_project(
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


async def _get_model_version(
    mv_id: uuid.UUID,
    current_user: User,
    session: AsyncSession,
) -> ModelVersion:
    r = await session.execute(
        select(ModelVersion).where(ModelVersion.id == mv_id)
    )
    mv = r.scalar_one_or_none()
    if mv is None:
        raise HTTPException(status_code=404, detail="Not found")
    proj = await session.get(Project, mv.project_id)
    if proj is None or proj.org_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Not found")
    return mv


@router.get("/projects/{project_id}/models", response_model=list[ModelVersionOut])
async def list_models(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ModelVersionOut]:
    await _get_project(project_id, current_user, session)
    r = await session.execute(
        select(ModelVersion).where(ModelVersion.project_id == project_id)
    )
    return list(r.scalars().all())


@router.get("/models/{id}", response_model=ModelVersionOut)
async def get_model(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ModelVersionOut:
    return await _get_model_version(id, current_user, session)


@router.get("/models/{id}/weights-url")
async def get_weights_url(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    mv = await _get_model_version(id, current_user, session)
    url = await get_storage().get_presigned_get(mv.blob_hash)
    return {"url": url}
