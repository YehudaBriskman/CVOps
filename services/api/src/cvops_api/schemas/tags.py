from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel


class TagCreate(BaseModel):
    name: str
    color: str = "#888888"


class TagUpdate(BaseModel):
    name: str | None = None
    color: str | None = None


class TagOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    color: str
    created_at: datetime
