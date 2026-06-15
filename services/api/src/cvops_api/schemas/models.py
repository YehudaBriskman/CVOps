from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel


class ModelVersionOut(BaseModel):
    model_config = {"from_attributes": True}
    id: uuid.UUID
    project_id: uuid.UUID
    blob_hash: str
    trained_on_commit_id: uuid.UUID | None = None
    base_model: str | None = None
    hyperparams: dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None
    code_version: str | None = None
    mlflow_run_id: str | None = None
    created_at: datetime
