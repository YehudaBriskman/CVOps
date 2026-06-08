from __future__ import annotations

import uuid
from datetime import datetime, UTC

import jsonschema
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cvops_api.core.auth import get_current_user
from cvops_api.db.session import get_session
from cvops_api.db.models.auth import User
from cvops_api.db.models.projects import Project
from cvops_api.db.models.models import TrainingContainer
from cvops_api.schemas.training_containers import (
    TrainingContainerCreate,
    TrainingContainerUpdate,
    TrainingContainerOut,
    ValidateRequest,
    ValidateResponse,
)

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


async def _get_tc(
    tc_id: uuid.UUID,
    current_user: User,
    session: AsyncSession,
) -> TrainingContainer:
    r = await session.execute(
        select(TrainingContainer).where(
            TrainingContainer.id == tc_id,
            TrainingContainer.deleted_at == None,  # noqa: E711
        )
    )
    tc = r.scalar_one_or_none()
    if tc is None:
        raise HTTPException(status_code=404, detail="Not found")
    proj = await session.get(Project, tc.project_id)
    if proj is None or proj.org_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Not found")
    return tc


@router.get(
    "/projects/{project_id}/training-containers",
    response_model=list[TrainingContainerOut],
)
async def list_training_containers(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[TrainingContainerOut]:
    await _get_project(project_id, current_user, session)
    r = await session.execute(
        select(TrainingContainer).where(
            TrainingContainer.project_id == project_id,
            TrainingContainer.deleted_at == None,  # noqa: E711
        )
    )
    return [TrainingContainerOut.model_validate(tc) for tc in r.scalars().all()]


@router.post(
    "/projects/{project_id}/training-containers",
    response_model=TrainingContainerOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_training_container(
    project_id: uuid.UUID,
    body: TrainingContainerCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TrainingContainerOut:
    await _get_project(project_id, current_user, session)
    tc = TrainingContainer(
        project_id=project_id,
        name=body.name,
        description=body.description,
        image=body.image,
        icd_config=body.icd_config,
        icd_schema_version=body.icd_schema_version,
    )
    session.add(tc)
    await session.flush()
    await session.commit()
    return TrainingContainerOut.model_validate(tc)


@router.get("/training-containers/{id}", response_model=TrainingContainerOut)
async def get_training_container(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TrainingContainerOut:
    return TrainingContainerOut.model_validate(await _get_tc(id, current_user, session))


@router.patch("/training-containers/{id}", response_model=TrainingContainerOut)
async def update_training_container(
    id: uuid.UUID,
    body: TrainingContainerUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TrainingContainerOut:
    tc = await _get_tc(id, current_user, session)
    if body.name is not None:
        tc.name = body.name
    if body.description is not None:
        tc.description = body.description
    if body.image is not None:
        tc.image = body.image
    if body.icd_config is not None:
        tc.icd_config = body.icd_config
    if body.icd_schema_version is not None:
        tc.icd_schema_version = body.icd_schema_version
    await session.flush()
    await session.commit()
    return TrainingContainerOut.model_validate(tc)


@router.delete("/training-containers/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_training_container(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    tc = await _get_tc(id, current_user, session)
    tc.deleted_at = datetime.now(UTC)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/training-containers/{id}/validate", response_model=ValidateResponse)
async def validate_training_container(
    id: uuid.UUID,
    body: ValidateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ValidateResponse:
    tc = await _get_tc(id, current_user, session)
    try:
        jsonschema.validate(instance=body.icd_config, schema=tc.icd_config)
        return ValidateResponse(valid=True)
    except jsonschema.ValidationError as e:
        return ValidateResponse(valid=False, errors=[str(e)])
