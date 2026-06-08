from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel


class WorkflowCreate(BaseModel):
    name: str
    definition: dict


class WorkflowUpdate(BaseModel):
    name: str | None = None
    definition: dict | None = None


class WorkflowOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    definition: dict
    version: int
    created_at: datetime
