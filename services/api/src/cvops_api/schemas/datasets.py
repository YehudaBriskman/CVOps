from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel


class DatasetCreate(BaseModel):
    name: str


class DatasetOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    created_at: datetime


class CommitCreate(BaseModel):
    message: str
    sample_ids: list[uuid.UUID]
    annotation_revision_ids: list[uuid.UUID]
    split_strategy: dict[str, Any] = {}
    ontology_id: uuid.UUID
    branch_name: str = "main"


class CommitOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    dataset_id: uuid.UUID
    message: str | None = None
    stats: dict[str, Any] | None = None
    ontology_id: uuid.UUID | None = None
    ontology_version: int | None = None
    created_at: datetime


class CommitFromSamples(BaseModel):
    message: str = ""
    sample_ids: list[uuid.UUID]
    branch_name: str = "main"
    split_strategy: dict[str, Any] = {}
    ontology_id: uuid.UUID | None = None


class CommitFromSamplesOut(BaseModel):
    commit_id: uuid.UUID
    committed_count: int
    skipped_count: int


class RefCreate(BaseModel):
    ref_type: str = "branch"
    name: str
    target_commit_id: uuid.UUID
    is_mutable: bool = True


class RefOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    dataset_id: uuid.UUID
    ref_type: str
    name: str
    target_commit_id: uuid.UUID
    is_mutable: bool


class DatasetLinkCreate(BaseModel):
    dataset_id: uuid.UUID
    pinned_commit_id: uuid.UUID | None = None
    ref_id: uuid.UUID | None = None


class DatasetLinkUpdate(BaseModel):
    pinned_commit_id: uuid.UUID | None = None
    ref_id: uuid.UUID | None = None


class DiffOut(BaseModel):
    added: list[uuid.UUID]
    removed: list[uuid.UUID]
    changed: list[uuid.UUID]
