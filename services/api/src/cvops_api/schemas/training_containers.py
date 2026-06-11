from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel


class TrainingContainerCreate(BaseModel):
    name: str
    description: str | None = None
    image: str
    icd_config: dict[str, Any]
    icd_schema_version: str | None = None


class TrainingContainerUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    image: str | None = None
    icd_config: dict[str, Any] | None = None
    icd_schema_version: str | None = None


class TrainingContainerOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str | None = None
    image: str
    icd_config: dict[str, Any] | None = None
    icd_schema_version: str | None = None
    created_at: datetime


class ValidateRequest(BaseModel):
    icd_config: dict[str, Any]


class ValidateResponse(BaseModel):
    valid: bool
    errors: list[str] = []
