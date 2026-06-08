from __future__ import annotations
import uuid
from datetime import datetime
from pydantic import BaseModel


class ModelVersionOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    project_id: uuid.UUID
    blob_hash: str
    trained_on_commit_id: uuid.UUID | None = None
    base_model: str | None = None
    hyperparams: dict | None = None
    metrics: dict | None = None
    code_version: str | None = None
    created_at: datetime
