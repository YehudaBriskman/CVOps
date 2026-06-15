import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from cvops_api.db.base import Base, EntityBase


class Collection(Base, EntityBase):
    """A named, project-scoped manual set of samples (a curation bucket)."""

    __tablename__ = "collections"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_collections_project_name"),)

    def __repr__(self) -> str:
        return f"<Collection id={self.id!r} project_id={self.project_id!r} name={self.name!r}>"


class CollectionSample(Base):
    """Membership join — which samples belong to a collection. Plain join (no spine)."""

    __tablename__ = "collection_samples"

    collection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("collections.id"), primary_key=True)
    sample_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("samples.id"), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    added_by: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)

    __table_args__ = (Index("ix_collection_samples_sample_id", "sample_id"),)

    def __repr__(self) -> str:
        return (
            f"<CollectionSample collection_id={self.collection_id!r} sample_id={self.sample_id!r}>"
        )
