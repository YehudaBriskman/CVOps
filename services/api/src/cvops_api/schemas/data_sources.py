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
    metadata: dict[str, Any] | None = Field(None, alias="metadata_")
    created_at: datetime


class UploadResponse(BaseModel):
    data_source: DataSourceOut
    presigned_put_url: str | None = None


class ConfirmResponse(BaseModel):
    data_source: DataSourceOut
    # Set when the project has a default_ingest_workflow_id and the backend
    # auto-dispatched a run; None otherwise. Lets the client jump straight to
    # GET /runs/{id}/events/stream.
    run_id: uuid.UUID | None = None
