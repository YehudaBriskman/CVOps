import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from cvops_api.db.base import Base, EntityBase


class Tag(Base, EntityBase):
    """A project-scoped, named label that can be applied to many samples."""

    __tablename__ = "tags"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    color: Mapped[str] = mapped_column(
        Text, nullable=False, default="#888888", server_default="#888888"
    )

    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_tags_project_name"),)

    def __repr__(self) -> str:
        return f"<Tag id={self.id!r} project_id={self.project_id!r} name={self.name!r}>"


class SampleTag(Base):
    """Many-to-many join between samples and tags. Plain join (no spine)."""

    __tablename__ = "sample_tags"

    sample_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("samples.id"), primary_key=True)
    tag_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tags.id"), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    added_by: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)

    __table_args__ = (Index("ix_sample_tags_tag_id", "tag_id"),)

    def __repr__(self) -> str:
        return f"<SampleTag sample_id={self.sample_id!r} tag_id={self.tag_id!r}>"
