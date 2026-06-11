from __future__ import annotations
from typing import Any
from pydantic import BaseModel


class TypeSchemaOut(BaseModel):
    type_key: str
    category: str
    json_schema: dict[str, Any]
    ui_hints: dict[str, Any]
