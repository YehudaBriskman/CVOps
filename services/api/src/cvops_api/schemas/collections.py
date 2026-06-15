from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel


class CollectionCreate(BaseModel):
    name: str
    description: str | None = None


class CollectionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class CollectionOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str | None = None
    created_at: datetime
    sample_count: int | None = None
