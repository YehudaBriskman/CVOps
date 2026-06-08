import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from cvops_api.db.base import Base, EntityBase


class DataSource(Base, EntityBase):
    __tablename__ = "data_sources"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)
    blob_hash: Mapped[Optional[str]] = mapped_column(ForeignKey("blobs.hash"), nullable=True)
    external_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="pending", server_default="pending"
    )
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)

    __table_args__ = (Index("ix_data_sources_project_status", "project_id", "status"),)

    def __repr__(self) -> str:
        return (
            f"<DataSource id={self.id!r} project_id={self.project_id!r}"
            f" type={self.type!r} status={self.status!r}>"
        )


class Sample(Base, EntityBase):
    __tablename__ = "samples"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    blob_hash: Mapped[str] = mapped_column(ForeignKey("blobs.hash"), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("data_sources.id"), nullable=False, index=True
    )
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    frame_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    perceptual_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    thumbnail_hash: Mapped[Optional[str]] = mapped_column(ForeignKey("blobs.hash"), nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)

    __table_args__ = (UniqueConstraint("project_id", "blob_hash", name="uq_samples_project_blob"),)

    def __repr__(self) -> str:
        return (
            f"<Sample id={self.id!r} project_id={self.project_id!r}"
            f" blob_hash={self.blob_hash!r} source_id={self.source_id!r}"
            f" frame_index={self.frame_index!r}>"
        )
