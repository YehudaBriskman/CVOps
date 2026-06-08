from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class CursorPage(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None


class SampleOut(BaseModel):
    model_config = {"from_attributes": True, "populate_by_name": True}
    id: uuid.UUID
    project_id: uuid.UUID
    blob_hash: str
    source_id: uuid.UUID
    width: int
    height: int
    frame_index: int | None = None
    perceptual_hash: str | None = None
    metadata: dict[str, Any] | None = Field(None, alias="metadata_")
    created_at: datetime


class AnnotationRevisionOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    sample_id: uuid.UUID
    ontology_id: uuid.UUID
    ontology_version: int
    revision_no: int
    payload: dict[str, Any]
    provenance: dict[str, Any] | None = None
    created_at: datetime


class AnnotationCreate(BaseModel):
    ontology_id: uuid.UUID
    payload: dict[str, Any]
    provenance: dict[str, Any] | None = None
