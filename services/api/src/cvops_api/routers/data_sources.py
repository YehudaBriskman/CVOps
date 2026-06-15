from __future__ import annotations

import uuid

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from cvops_api.config import settings
from cvops_api.core.auth import get_current_user
from cvops_api.core.storage import get_storage, public_s3_endpoint
from cvops_api.db.session import get_session
from cvops_api.db.models.auth import User
from cvops_api.db.models.blobs import Blob
from cvops_api.db.models.projects import Project
from cvops_api.db.models.runs import Run
from cvops_api.db.models.samples import DataSource, Sample
from cvops_api.db.models.workflows import Workflow
from cvops_api.engine.coordinator import advance_workflow
from cvops_api.engine.dispatch import create_workflow_run
from cvops_api.schemas.data_sources import (
    ConfirmResponse,
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
        select(DataSource)
        .where(DataSource.project_id == project_id)
        .order_by(DataSource.created_at.desc())
    )
    sources = list(r.scalars().all())

    # One grouped count instead of a per-source query, so the UI can show how
    # many frames each source has produced (and detect "still processing").
    counts_r = await session.execute(
        select(Sample.source_id, func.count())
        .where(Sample.project_id == project_id)
        .group_by(Sample.source_id)
    )
    counts = {row[0]: row[1] for row in counts_r.all()}

    # Latest workflow run per source (DISTINCT ON the source_id stashed in
    # input_refs), so each card can link to its ingest run. One query for the
    # whole page, same as the counts above.
    source_id_expr = Run.input_refs["params"]["source_id"].astext
    runs_r = await session.execute(
        select(source_id_expr, Run.id)
        .where(Run.project_id == project_id, Run.kind == "workflow")
        .order_by(source_id_expr, Run.created_at.desc())
        .distinct(source_id_expr)
    )
    latest_run = {row[0]: row[1] for row in runs_r.all()}

    out: list[DataSourceOut] = []
    for ds in sources:
        item = DataSourceOut.model_validate(ds)
        item.sample_count = counts.get(ds.id, 0)
        item.latest_run_id = latest_run.get(str(ds.id))
        out.append(item)
    return out


@router.post(
    "/projects/{project_id}/data-sources",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_data_source(
    project_id: uuid.UUID,
    body: DataSourceCreate,
    request: Request,
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
        # Sign against the host the browser used so the direct upload is reachable.
        endpoint = public_s3_endpoint(request.url.hostname)
        put_url = await get_storage().get_presigned_put_for_upload(
            str(ds.id), endpoint=endpoint
        )

    await session.commit()
    return UploadResponse(
        data_source=DataSourceOut.model_validate(ds),
        presigned_put_url=put_url,
    )


@router.post("/data-sources/{id}/confirm-upload", response_model=ConfirmResponse)
async def confirm_upload(
    id: uuid.UUID,
    body: DataSourceConfirm,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConfirmResponse:
    r = await session.execute(select(DataSource).where(DataSource.id == id))
    ds = r.scalar_one_or_none()
    if ds is None:
        raise HTTPException(status_code=404, detail="DataSource not found")
    proj = await _check_project(ds.project_id, current_user, session)

    # Idempotent: a re-sent confirm must not register the blob twice or dispatch
    # a duplicate run.
    if ds.status != "pending":
        return ConfirmResponse(data_source=DataSourceOut.model_validate(ds))

    # Promote the finished upload to its content-addressed location (server-side
    # copy — no bytes through the API) and register the blob row. ON CONFLICT
    # DO NOTHING because identical content may already be registered.
    size_bytes, media_type, storage_key = await get_storage().promote_upload(
        str(ds.id), body.blob_hash
    )
    await session.execute(
        pg_insert(Blob)
        .values(
            hash=body.blob_hash,
            storage_backend=settings.S3_BACKEND,
            storage_key=storage_key,
            size_bytes=size_bytes,
            media_type=media_type,
        )
        .on_conflict_do_nothing(index_elements=["hash"])
    )

    ds.blob_hash = body.blob_hash
    ds.status = "uploaded"
    await session.commit()

    # Backend-owned trigger: pick the workflow to run on this upload. A
    # client-supplied workflow_id takes precedence (chosen at upload time);
    # otherwise fall back to the project's configured default. None of either
    # means "just store, no processing".
    target_wf_id = body.workflow_id or proj.default_ingest_workflow_id
    run_id: uuid.UUID | None = None
    if target_wf_id is not None:
        wf_r = await session.execute(
            select(Workflow).where(
                Workflow.id == target_wf_id,
                Workflow.project_id == ds.project_id,
                Workflow.deleted_at == None,  # noqa: E711
            )
        )
        wf = wf_r.scalar_one_or_none()
        # An explicit, client-chosen workflow that doesn't resolve is a bad
        # request; a stale project default is silently skipped (don't fail the
        # upload over a misconfigured setting).
        if wf is None and body.workflow_id is not None:
            raise HTTPException(status_code=404, detail="Workflow not found")
        if wf is not None:
            run = await create_workflow_run(
                session, wf, {"source_id": str(ds.id)}, current_user.id
            )
            run_id = run.id
            # Synchronous, fast: creates the first child step runs and rings
            # their Redis queues. A worker picks them up out-of-process.
            await advance_workflow(session, run.id, current_user.id)

    return ConfirmResponse(
        data_source=DataSourceOut.model_validate(ds), run_id=run_id
    )


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


@router.get("/data-sources/{id}/url")
async def get_data_source_url(
    id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Presigned GET URL for the source's raw blob so the browser can preview
    the original video/image directly from object storage (no bytes via API)."""
    r = await session.execute(select(DataSource).where(DataSource.id == id))
    ds = r.scalar_one_or_none()
    if ds is None:
        raise HTTPException(status_code=404, detail="DataSource not found")
    await _check_project(ds.project_id, current_user, session)
    if ds.blob_hash is None:
        raise HTTPException(status_code=404, detail="Data source has no uploaded blob")
    url = await get_storage().get_presigned_get(
        ds.blob_hash, endpoint=public_s3_endpoint(request.url.hostname)
    )
    return {"url": url}


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
