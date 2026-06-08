from __future__ import annotations
from pydantic import BaseModel


class TypeSchemaOut(BaseModel):
    type_key: str
    category: str
    json_schema: dict
    ui_hints: dict
