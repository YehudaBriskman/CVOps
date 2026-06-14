"""Authentication router — register, token, refresh, revoke, me."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from cvops_api.core.auth import (
    blacklist_token,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    oauth2_scheme as _oauth2_scheme,
    verify_password,
)
from cvops_api.db.models.auth import Membership, Org, User
from cvops_api.db.session import get_session
from cvops_api.schemas.auth import (
    RefreshRequest,
    RegisterRequest,
    RevocationRequest,
    TokenResponse,
    UserOut,
)

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    org_name = body.org_name or body.email.split("@")[0]
    org = Org(name=org_name)
    session.add(org)

    # Unique violations (orgs.name, users.email) surface at flush, not just
    # commit — so the whole write must be guarded to return 409 rather than 500.
    try:
        await session.flush()  # org.id; may violate uq_orgs_name

        user = User(
            org_id=org.id,
            email=body.email,
            password_hash=hash_password(body.password),
            is_active=True,
        )
        session.add(user)
        await session.flush()  # may violate the unique email constraint

        session.add(Membership(org_id=org.id, user_id=user.id, role="owner"))
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email or organization name already registered",
        )

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/token", response_model=TokenResponse)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    result = await session.execute(select(User).where(User.email == form.username))
    user = result.scalar_one_or_none()

    if (
        user is None
        or not user.password_hash
        or not verify_password(form.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    payload = decode_token(body.refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Rotate: blacklist the consumed refresh token
    jti = payload.get("jti")
    exp = payload.get("exp")
    if jti and exp:
        await blacklist_token(jti, int(exp))

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/revoke", status_code=status.HTTP_204_NO_CONTENT)
async def revoke(
    body: RevocationRequest,
    current_user: User = Depends(get_current_user),
    token: str = Depends(_oauth2_scheme),
) -> None:
    access_payload = decode_token(token)
    jti = access_payload.get("jti")
    exp = access_payload.get("exp")
    if jti and exp:
        await blacklist_token(jti, int(exp))

    if body.refresh_token:
        try:
            refresh_payload = decode_token(body.refresh_token)
            r_jti = refresh_payload.get("jti")
            r_exp = refresh_payload.get("exp")
            if r_jti and r_exp:
                await blacklist_token(r_jti, int(r_exp))
        except Exception:
            pass


@router.get("/me", response_model=UserOut)
async def me(
    current_user: User = Depends(get_current_user),
) -> UserOut:
    return UserOut.model_validate(current_user)
