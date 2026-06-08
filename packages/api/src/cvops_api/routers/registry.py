from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from cvops_api.core.auth import get_current_user
from cvops_api.core.registry import registry
from cvops_api.db.models.auth import User
from cvops_api.schemas.registry import TypeSchemaOut

router = APIRouter(prefix="/registry")


@router.get("/types", response_model=list[TypeSchemaOut])
async def list_types(
    category: str | None = Query(None),
    current_user: User = Depends(get_current_user),
) -> list[TypeSchemaOut]:
    if category is not None:
        regs = registry.list_by_category(category)
    else:
        regs = list(registry._store.values())
    return [
        TypeSchemaOut(
            type_key=r.type_key,
            category=r.category,
            json_schema=r.json_schema,
            ui_hints=r.ui_hints,
        )
        for r in regs
    ]


@router.get("/types/{type_key}", response_model=TypeSchemaOut)
async def get_type(
    type_key: str,
    current_user: User = Depends(get_current_user),
) -> TypeSchemaOut:
    try:
        r = registry.resolve(type_key)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Type '{type_key}' not found")
    return TypeSchemaOut(
        type_key=r.type_key,
        category=r.category,
        json_schema=r.json_schema,
        ui_hints=r.ui_hints,
    )
