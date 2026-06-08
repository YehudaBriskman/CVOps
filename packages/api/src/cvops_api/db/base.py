"""
G1 — Base entity mixin.
Every domain table inherits EntityBase to get the standard spine.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy declarative base — all models inherit from this."""


class EntityBase:
    """
    G1 spine: id, timestamps, soft-delete, actor.
    Mix into every domain table class alongside Base.
    Tables that are not project-scoped (e.g. orgs, blobs) omit project_id.
    """

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
