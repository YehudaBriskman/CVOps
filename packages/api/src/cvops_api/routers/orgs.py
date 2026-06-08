"""Organisations router — current org, members CRUD."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from cvops_api.core.auth import get_current_user
from cvops_api.db.models.auth import Membership, Org, User
from cvops_api.db.session import get_session
from cvops_api.schemas.orgs import MemberInvite, MemberOut, MemberUpdate, OrgOut, OrgUpdate

router = APIRouter()


@router.get("/current", response_model=OrgOut)
async def get_current_org(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrgOut:
    result = await session.execute(select(Org).where(Org.id == current_user.org_id))
    org = result.scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Org not found")
    return OrgOut.model_validate(org)


@router.patch("/current", response_model=OrgOut)
async def update_current_org(
    body: OrgUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> OrgOut:
    result = await session.execute(select(Org).where(Org.id == current_user.org_id))
    org = result.scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Org not found")

    if body.name is not None:
        org.name = body.name
    if body.settings is not None:
        org.settings = body.settings

    await session.flush()
    await session.commit()
    return OrgOut.model_validate(org)


@router.get("/current/members", response_model=list[MemberOut])
async def list_members(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[MemberOut]:
    result = await session.execute(
        select(Membership, User)
        .join(User, Membership.user_id == User.id)
        .where(Membership.org_id == current_user.org_id)
    )
    rows = result.all()
    return [
        MemberOut(user_id=membership.user_id, email=user.email, role=membership.role)
        for membership, user in rows
    ]


@router.post("/current/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
async def invite_member(
    body: MemberInvite,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MemberOut:
    user_result = await session.execute(select(User).where(User.email == body.email))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    membership = Membership(org_id=current_user.org_id, user_id=user.id, role=body.role)
    session.add(membership)

    try:
        await session.flush()
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this org",
        )

    return MemberOut(user_id=user.id, email=user.email, role=membership.role)


@router.patch("/current/members/{user_id}", response_model=MemberOut)
async def update_member(
    user_id: uuid.UUID,
    body: MemberUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MemberOut:
    membership_result = await session.execute(
        select(Membership).where(
            Membership.org_id == current_user.org_id,
            Membership.user_id == user_id,
        )
    )
    membership = membership_result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")

    user_result = await session.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    membership.role = body.role
    await session.flush()
    await session.commit()

    return MemberOut(user_id=user.id, email=user.email, role=membership.role)


@router.delete("/current/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    membership_result = await session.execute(
        select(Membership).where(
            Membership.org_id == current_user.org_id,
            Membership.user_id == user_id,
        )
    )
    membership = membership_result.scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")

    await session.delete(membership)
    await session.commit()
    return None
