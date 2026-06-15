from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class DataSourceCreate(BaseModel):
    type: str
    external_uri: str | None = None
    metadata: dict[str, Any] | None = None


class DataSourceConfirm(BaseModel):
    blob_hash: str


class DataSourceOut(BaseModel):
    model_config = {"from_attributes": True, "populate_by_name": True}
    id: uuid.UUID
    project_id: uuid.UUID
    type: str
    blob_hash: str | None = None
    external_uri: str | None = None
    status: str
    metadata: dict[str, Any] | None = Field(
        None, validation_alias="metadata_", serialization_alias="metadata"
    )
    created_at: datetime
    # Populated only by the list endpoint (number of extracted frames for this
    # source); None elsewhere to avoid an extra query on single-item responses.
    sample_count: int | None = None


class UploadResponse(BaseModel):
    data_source: DataSourceOut
    presigned_put_url: str | None = None


class ConfirmResponse(BaseModel):
    data_source: DataSourceOut
    # Set when the project has a default_ingest_workflow_id and the backend
    # auto-dispatched a run; None otherwise. Lets the client jump straight to
    # GET /runs/{id}/events/stream.
    run_id: uuid.UUID | None = None


# ── Direct image upload (manual images → samples, no workflow) ───────────────


class ImagePresignItem(BaseModel):
    filename: str
    content_type: str
    sha256: str  # content hash "sha256:<hex>" (the content-addressed key)


class ImagePresignRequest(BaseModel):
    items: list[ImagePresignItem] = Field(..., max_length=1000)


class ImagePresignOut(BaseModel):
    filename: str
    blob_hash: str
    put_url: str


class ImagePresignResponse(BaseModel):
    items: list[ImagePresignOut]


class ImageConfirmItem(BaseModel):
    blob_hash: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    content_type: str | None = None
    size_bytes: int | None = None


class ImageConfirmRequest(BaseModel):
    items: list[ImageConfirmItem] = Field(..., max_length=1000)
    # Sub-group label (folder name); omitted → server stamps "Upload <time>".
    group: str | None = None


class ImageConfirmResponse(BaseModel):
    source_id: uuid.UUID
    created: int
    sample_ids: list[uuid.UUID]
