from __future__ import annotations

import base64
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any, cast

from cvops_api.core.auth import get_current_user
from cvops_api.db.session import get_session
from cvops_api.db.models.auth import User
from cvops_api.db.models.projects import Project
from cvops_api.db.models.versioning import (
    Dataset,
    Commit,
    CommitSample,
    Ref,
    ProjectDatasetLink,
)
from cvops_api.db.models.ontologies import Ontology
from cvops_api.schemas.datasets import (
    DatasetCreate,
    DatasetOut,
    CommitCreate,
    CommitOut,
    RefCreate,
    RefOut,
    DatasetLinkCreate,
    DatasetLinkUpdate,
    DiffOut,
)
from cvops_api.schemas.samples import CursorPage

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


# ── Datasets ─────────────────────────────────────────────────────────────────


@router.get("/projects/{project_id}/datasets", response_model=list[DatasetOut])
async def list_datasets(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[DatasetOut]:
    await _check_project(project_id, current_user, session)
    r = await session.execute(select(Dataset).where(Dataset.project_id == project_id))
    return [DatasetOut.model_validate(d) for d in r.scalars().all()]


@router.post(
    "/projects/{project_id}/datasets",
    response_model=DatasetOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_dataset(
    project_id: uuid.UUID,
    body: DatasetCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DatasetOut:
    await _check_project(project_id, current_user, session)
    dataset = Dataset(project_id=project_id, name=body.name)
    session.add(dataset)
    await session.commit()
    return DatasetOut.model_validate(dataset)


@router.get("/datasets/{id}", response_model=DatasetOut)
async def get_dataset(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DatasetOut:
    r = await session.execute(select(Dataset).where(Dataset.id == id))
    dataset = r.scalar_one_or_none()
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    await _check_project(dataset.project_id, current_user, session)
    return DatasetOut.model_validate(dataset)


# ── Commits ───────────────────────────────────────────────────────────────────


@router.get(
    "/datasets/{id}/commits",
    response_model=CursorPage[CommitOut],
)
async def list_commits(
    id: uuid.UUID,
    cursor: str | None = Query(None),
    limit: int = Query(50, le=200),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CursorPage[CommitOut]:
    r = await session.execute(select(Dataset).where(Dataset.id == id))
    dataset = r.scalar_one_or_none()
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    await _check_project(dataset.project_id, current_user, session)

    q = select(Commit).where(Commit.dataset_id == id)
    if cursor is not None:
        cursor_uuid = uuid.UUID(base64.b64decode(cursor).decode())
        q = q.where(Commit.id > cursor_uuid)
    q = q.order_by(Commit.id).limit(limit + 1)

    result = await session.execute(q)
    items = list(result.scalars().all())

    next_cursor: str | None = None
    if len(items) == limit + 1:
        next_cursor = base64.b64encode(str(items[-1].id).encode()).decode()
        items = items[:limit]

    return CursorPage(
        items=[CommitOut.model_validate(c) for c in items],
        next_cursor=next_cursor,
    )


@router.get("/datasets/{id}/commits/{commit_id}")
async def get_commit(
    id: uuid.UUID,
    commit_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    r = await session.execute(select(Dataset).where(Dataset.id == id))
    dataset = r.scalar_one_or_none()
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    await _check_project(dataset.project_id, current_user, session)

    rc = await session.execute(
        select(Commit).where(Commit.id == commit_id, Commit.dataset_id == dataset.id)
    )
    commit = rc.scalar_one_or_none()
    if commit is None:
        raise HTTPException(status_code=404, detail="Commit not found")

    return Response(
        content=CommitOut.model_validate(commit).model_dump_json(),
        media_type="application/json",
        headers={"Cache-Control": "immutable, max-age=31536000"},
    )


@router.post(
    "/datasets/{id}/commits",
    response_model=CommitOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_commit(
    id: uuid.UUID,
    body: CommitCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CommitOut:
    r = await session.execute(select(Dataset).where(Dataset.id == id))
    dataset = r.scalar_one_or_none()
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    await _check_project(dataset.project_id, current_user, session)

    # Resolve ontology version
    r_ont = await session.execute(select(Ontology.version).where(Ontology.id == body.ontology_id))
    ont_version = r_ont.scalar_one_or_none()
    if ont_version is None:
        raise HTTPException(status_code=404, detail="Ontology not found")

    # Find parent commit via branch ref
    r_ref = await session.execute(
        select(Ref).where(
            Ref.dataset_id == dataset.id,
            Ref.name == body.branch_name,
        )
    )
    ref = r_ref.scalar_one_or_none()
    parent_commit_id = ref.target_commit_id if ref is not None else None

    # Create commit
    commit = Commit(
        dataset_id=dataset.id,
        project_id=dataset.project_id,
        ontology_id=body.ontology_id,
        ontology_version=ont_version,
        message=body.message,
        stats={"sample_count": len(body.sample_ids)},
        parent_commit_id=parent_commit_id,
    )
    session.add(commit)
    await session.flush()

    # Assign splits
    total = len(body.sample_ids)
    train_ratio = body.split_strategy.get("train_ratio", 0.7)
    val_ratio = body.split_strategy.get("val_ratio", 0.15)
    train_count = int(total * train_ratio)
    val_count = int(total * val_ratio)

    for idx, (sid, arid) in enumerate(zip(body.sample_ids, body.annotation_revision_ids)):
        if idx < train_count:
            split = "train"
        elif idx < train_count + val_count:
            split = "val"
        else:
            split = "test"
        session.add(
            CommitSample(
                commit_id=commit.id,
                sample_id=sid,
                annotation_revision_id=arid,
                split=split,
            )
        )

    # Advance or create branch ref via CAS
    if ref:
        result = cast(
            CursorResult[Any],
            await session.execute(
                update(Ref)
                .where(Ref.id == ref.id, Ref.target_commit_id == parent_commit_id)
                .values(target_commit_id=commit.id)
            ),
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=409, detail="Concurrent branch update — retry")
    else:
        session.add(
            Ref(
                dataset_id=dataset.id,
                ref_type="branch",
                name=body.branch_name,
                target_commit_id=commit.id,
                is_mutable=True,
            )
        )

    await session.commit()
    return CommitOut.model_validate(commit)


# ── Refs ──────────────────────────────────────────────────────────────────────


@router.get("/datasets/{id}/refs", response_model=list[RefOut])
async def list_refs(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[RefOut]:
    r = await session.execute(select(Dataset).where(Dataset.id == id))
    dataset = r.scalar_one_or_none()
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    await _check_project(dataset.project_id, current_user, session)

    r_refs = await session.execute(select(Ref).where(Ref.dataset_id == id))
    return [RefOut.model_validate(ref) for ref in r_refs.scalars().all()]


@router.post(
    "/datasets/{id}/refs",
    response_model=RefOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_ref(
    id: uuid.UUID,
    body: RefCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RefOut:
    r = await session.execute(select(Dataset).where(Dataset.id == id))
    dataset = r.scalar_one_or_none()
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    await _check_project(dataset.project_id, current_user, session)

    ref = Ref(
        dataset_id=dataset.id,
        ref_type=body.ref_type,
        name=body.name,
        target_commit_id=body.target_commit_id,
        is_mutable=body.is_mutable,
    )
    session.add(ref)
    await session.commit()
    return RefOut.model_validate(ref)


@router.delete(
    "/datasets/{id}/refs/{ref_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_ref(
    id: uuid.UUID,
    ref_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    r = await session.execute(select(Dataset).where(Dataset.id == id))
    dataset = r.scalar_one_or_none()
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    await _check_project(dataset.project_id, current_user, session)

    r_ref = await session.execute(select(Ref).where(Ref.id == ref_id, Ref.dataset_id == id))
    ref = r_ref.scalar_one_or_none()
    if ref is None:
        raise HTTPException(status_code=404, detail="Ref not found")

    await session.delete(ref)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Diff ──────────────────────────────────────────────────────────────────────


@router.get("/datasets/{id}/diff", response_model=DiffOut)
async def diff_commits(
    id: uuid.UUID,
    from_commit: uuid.UUID = Query(...),
    to_commit: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DiffOut:
    r = await session.execute(select(Dataset).where(Dataset.id == id))
    dataset = r.scalar_one_or_none()
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    await _check_project(dataset.project_id, current_user, session)

    # Verify both commits belong to this dataset
    r_from = await session.execute(
        select(Commit).where(Commit.id == from_commit, Commit.dataset_id == id)
    )
    commit_from = r_from.scalar_one_or_none()
    if commit_from is None:
        raise HTTPException(status_code=404, detail="from_commit not found in dataset")

    r_to = await session.execute(
        select(Commit).where(Commit.id == to_commit, Commit.dataset_id == id)
    )
    commit_to = r_to.scalar_one_or_none()
    if commit_to is None:
        raise HTTPException(status_code=404, detail="to_commit not found in dataset")

    r_from_samples = await session.execute(
        select(CommitSample.sample_id).where(CommitSample.commit_id == from_commit)
    )
    from_samples = set(r_from_samples.scalars().all())

    r_to_samples = await session.execute(
        select(CommitSample.sample_id).where(CommitSample.commit_id == to_commit)
    )
    to_samples = set(r_to_samples.scalars().all())

    return DiffOut(
        added=list(to_samples - from_samples),
        removed=list(from_samples - to_samples),
        changed=[],
    )


# ── Dataset Links ─────────────────────────────────────────────────────────────


@router.post(
    "/projects/{project_id}/dataset-links",
    status_code=status.HTTP_201_CREATED,
)
async def create_dataset_link(
    project_id: uuid.UUID,
    body: DatasetLinkCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await _check_project(project_id, current_user, session)

    # Exactly one of pinned_commit_id / ref_id must be non-null
    has_pin = body.pinned_commit_id is not None
    has_ref = body.ref_id is not None
    if has_pin == has_ref:
        raise HTTPException(
            status_code=422,
            detail="Exactly one of pinned_commit_id or ref_id must be provided",
        )

    link = ProjectDatasetLink(
        project_id=project_id,
        dataset_id=body.dataset_id,
        pinned_commit_id=body.pinned_commit_id,
        ref_id=body.ref_id,
    )
    session.add(link)
    await session.commit()
    return {
        "id": str(link.id),
        "project_id": str(link.project_id),
        "dataset_id": str(link.dataset_id),
        "pinned_commit_id": str(link.pinned_commit_id) if link.pinned_commit_id else None,
        "ref_id": str(link.ref_id) if link.ref_id else None,
    }


@router.patch("/dataset-links/{id}")
async def update_dataset_link(
    id: uuid.UUID,
    body: DatasetLinkUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    r = await session.execute(select(ProjectDatasetLink).where(ProjectDatasetLink.id == id))
    link = r.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="Dataset link not found")
    await _check_project(link.project_id, current_user, session)

    if body.pinned_commit_id is not None:
        link.pinned_commit_id = body.pinned_commit_id
        link.ref_id = None
    if body.ref_id is not None:
        link.ref_id = body.ref_id
        link.pinned_commit_id = None

    await session.commit()
    return {
        "id": str(link.id),
        "project_id": str(link.project_id),
        "dataset_id": str(link.dataset_id),
        "pinned_commit_id": str(link.pinned_commit_id) if link.pinned_commit_id else None,
        "ref_id": str(link.ref_id) if link.ref_id else None,
    }


@router.delete(
    "/dataset-links/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_dataset_link(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    r = await session.execute(select(ProjectDatasetLink).where(ProjectDatasetLink.id == id))
    link = r.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="Dataset link not found")
    await _check_project(link.project_id, current_user, session)

    await session.delete(link)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
