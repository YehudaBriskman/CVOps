from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr


class OrgOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    name: str
    settings: dict | None = None
    created_at: datetime


class OrgUpdate(BaseModel):
    name: str | None = None
    settings: dict | None = None


class MemberOut(BaseModel):
    user_id: uuid.UUID
    email: str
    role: str


class MemberInvite(BaseModel):
    email: EmailStr
    role: str = "member"


class MemberUpdate(BaseModel):
    role: str
