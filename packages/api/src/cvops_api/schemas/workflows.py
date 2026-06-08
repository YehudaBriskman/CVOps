from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel


class WorkflowCreate(BaseModel):
    name: str
    definition: dict[str, Any]


class WorkflowUpdate(BaseModel):
    name: str | None = None
    definition: dict[str, Any] | None = None


class WorkflowOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    definition: dict[str, Any]
    version: int
    created_at: datetime
