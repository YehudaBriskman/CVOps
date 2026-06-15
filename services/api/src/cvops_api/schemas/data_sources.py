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
    # Optional per-upload override: dispatch this workflow on the freshly
    # uploaded source instead of the project's default_ingest_workflow_id.
    # Lets the client choose at upload time when no default is configured (or
    # to pick a different one). Must belong to the same project.
    workflow_id: uuid.UUID | None = None


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
    # Populated only by the list endpoint (number of extracted frames for this
    # source); None elsewhere to avoid an extra query on single-item responses.
    sample_count: int | None = None
    # Latest workflow run dispatched for this source (its ingest run), so the UI
    # can link straight to it. List endpoint only; None elsewhere.
    latest_run_id: uuid.UUID | None = None


class UploadResponse(BaseModel):
    data_source: DataSourceOut
    presigned_put_url: str | None = None


class ConfirmResponse(BaseModel):
    data_source: DataSourceOut
    # Set when the backend auto-dispatched a run for this upload — either the
    # client-supplied workflow_id or the project's default_ingest_workflow_id;
    # None otherwise. Lets the client jump straight to
    # GET /runs/{id}/events/stream.
    run_id: uuid.UUID | None = None
