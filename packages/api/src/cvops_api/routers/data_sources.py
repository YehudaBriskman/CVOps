from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cvops_api.core.auth import get_current_user
from cvops_api.core.storage import get_storage
from cvops_api.db.session import get_session
from cvops_api.db.models.auth import User
from cvops_api.db.models.projects import Project
from cvops_api.db.models.samples import DataSource
from cvops_api.schemas.data_sources import (
    DataSourceCreate,
    DataSourceConfirm,
    DataSourceOut,
    UploadResponse,
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


@router.get("/projects/{project_id}/data-sources", response_model=list[DataSourceOut])
async def list_data_sources(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[DataSourceOut]:
    await _check_project(project_id, current_user, session)
    r = await session.execute(
        select(DataSource).where(DataSource.project_id == project_id)
    )
    return [DataSourceOut.model_validate(ds) for ds in r.scalars().all()]


@router.post(
    "/projects/{project_id}/data-sources",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_data_source(
    project_id: uuid.UUID,
    body: DataSourceCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UploadResponse:
    await _check_project(project_id, current_user, session)

    ds = DataSource(
        project_id=project_id,
        type=body.type,
        external_uri=body.external_uri,
        metadata_=body.metadata,
        status="pending",
    )
    session.add(ds)
    await session.flush()  # get ds.id

    put_url: str | None = None
    if body.type != "external_uri":
        storage = get_storage()
        put_url = storage._client.generate_presigned_url(
            "put_object",
            Params={"Bucket": storage._bucket, "Key": f"uploads/{ds.id}"},
            ExpiresIn=3600,
        )

    await session.commit()
    return UploadResponse(
        data_source=DataSourceOut.model_validate(ds),
        presigned_put_url=put_url,
    )


@router.post("/data-sources/{id}/confirm-upload", response_model=DataSourceOut)
async def confirm_upload(
    id: uuid.UUID,
    body: DataSourceConfirm,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DataSourceOut:
    r = await session.execute(select(DataSource).where(DataSource.id == id))
    ds = r.scalar_one_or_none()
    if ds is None:
        raise HTTPException(status_code=404, detail="DataSource not found")
    await _check_project(ds.project_id, current_user, session)

    ds.blob_hash = body.blob_hash
    ds.status = "confirmed"
    await session.commit()
    return DataSourceOut.model_validate(ds)


@router.get("/data-sources/{id}", response_model=DataSourceOut)
async def get_data_source(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DataSourceOut:
    r = await session.execute(select(DataSource).where(DataSource.id == id))
    ds = r.scalar_one_or_none()
    if ds is None:
        raise HTTPException(status_code=404, detail="DataSource not found")
    await _check_project(ds.project_id, current_user, session)
    return DataSourceOut.model_validate(ds)


@router.delete("/data-sources/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_data_source(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    r = await session.execute(select(DataSource).where(DataSource.id == id))
    ds = r.scalar_one_or_none()
    if ds is None:
        raise HTTPException(status_code=404, detail="DataSource not found")
    await _check_project(ds.project_id, current_user, session)
    await session.delete(ds)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
