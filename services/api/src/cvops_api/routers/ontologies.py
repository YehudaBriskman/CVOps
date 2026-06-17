from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from cvops_api.core.auth import get_current_user
from cvops_api.db.session import get_session
from cvops_api.db.models.auth import User
from cvops_api.db.models.projects import Project
from cvops_api.db.models.ontologies import Ontology, LabelClass
from cvops_api.schemas.ontologies import (
    OntologyCreate,
    OntologyOut,
    LabelClassCreate,
    LabelClassUpdate,
    LabelClassOut,
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


@router.get("/projects/{project_id}/ontologies", response_model=list[OntologyOut])
async def list_ontologies(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[OntologyOut]:
    await _check_project(project_id, current_user, session)
    r = await session.execute(
        select(Ontology).where(
            Ontology.project_id == project_id,
            Ontology.deleted_at == None,  # noqa: E711
        )
    )
    return [OntologyOut.model_validate(o) for o in r.scalars().all()]


@router.post(
    "/projects/{project_id}/ontologies",
    response_model=OntologyOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_ontology(
    project_id: uuid.UUID,
    body: OntologyCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OntologyOut:
    await _check_project(project_id, current_user, session)
    ontology = Ontology(project_id=project_id, name=body.name)
    session.add(ontology)
    await session.commit()
    return OntologyOut.model_validate(ontology)


@router.get("/ontologies/{id}", response_model=OntologyOut)
async def get_ontology(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OntologyOut:
    r = await session.execute(select(Ontology).where(Ontology.id == id))
    ontology = r.scalar_one_or_none()
    if ontology is None:
        raise HTTPException(status_code=404, detail="Ontology not found")
    await _check_project(ontology.project_id, current_user, session)
    return OntologyOut.model_validate(ontology)


@router.get("/ontologies/{id}/classes", response_model=list[LabelClassOut])
async def list_label_classes(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[LabelClassOut]:
    r = await session.execute(select(Ontology).where(Ontology.id == id))
    ontology = r.scalar_one_or_none()
    if ontology is None:
        raise HTTPException(status_code=404, detail="Ontology not found")
    await _check_project(ontology.project_id, current_user, session)

    rows = await session.execute(
        select(LabelClass)
        .where(LabelClass.ontology_id == id)
        .order_by(LabelClass.sort_order)
    )
    return [LabelClassOut.model_validate(lc) for lc in rows.scalars().all()]


@router.post(
    "/ontologies/{id}/classes",
    response_model=LabelClassOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_label_class(
    id: uuid.UUID,
    body: LabelClassCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LabelClassOut:
    r = await session.execute(select(Ontology).where(Ontology.id == id))
    ontology = r.scalar_one_or_none()
    if ontology is None:
        raise HTTPException(status_code=404, detail="Ontology not found")
    await _check_project(ontology.project_id, current_user, session)

    lc = LabelClass(
        ontology_id=ontology.id,
        class_key=body.class_key,
        display_name=body.display_name,
        color=body.color,
        sort_order=body.sort_order,
    )
    session.add(lc)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate class_key or sort_order",
        )
    return LabelClassOut.model_validate(lc)


@router.patch("/ontologies/{id}/classes/{class_id}", response_model=LabelClassOut)
async def update_label_class(
    id: uuid.UUID,
    class_id: uuid.UUID,
    body: LabelClassUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LabelClassOut:
    r = await session.execute(select(Ontology).where(Ontology.id == id))
    ontology = r.scalar_one_or_none()
    if ontology is None:
        raise HTTPException(status_code=404, detail="Ontology not found")
    await _check_project(ontology.project_id, current_user, session)

    r2 = await session.execute(select(LabelClass).where(LabelClass.id == class_id))
    lc = r2.scalar_one_or_none()
    if lc is None or lc.ontology_id != ontology.id:
        raise HTTPException(status_code=404, detail="LabelClass not found")

    if body.display_name is not None:
        lc.display_name = body.display_name
    if body.color is not None:
        lc.color = body.color
    if body.sort_order is not None:
        lc.sort_order = body.sort_order

    await session.commit()
    return LabelClassOut.model_validate(lc)


@router.delete(
    "/ontologies/{id}/classes/{class_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_label_class(
    id: uuid.UUID,
    class_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    r = await session.execute(select(Ontology).where(Ontology.id == id))
    ontology = r.scalar_one_or_none()
    if ontology is None:
        raise HTTPException(status_code=404, detail="Ontology not found")
    await _check_project(ontology.project_id, current_user, session)

    r2 = await session.execute(select(LabelClass).where(LabelClass.id == class_id))
    lc = r2.scalar_one_or_none()
    if lc is None or lc.ontology_id != ontology.id:
        raise HTTPException(status_code=404, detail="LabelClass not found")

    await session.delete(lc)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
