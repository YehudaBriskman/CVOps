import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from cvops_api.db.base import Base, EntityBase


class Dataset(Base, EntityBase):
    __tablename__ = "datasets"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_datasets_project_name"),)

    def __repr__(self) -> str:
        return f"<Dataset id={self.id!r} project_id={self.project_id!r} name={self.name!r}>"


class Commit(Base):
    __tablename__ = "commits"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("datasets.id"), nullable=False, index=True
    )
    parent_commit_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("commits.id"), nullable=True
    )
    second_parent_commit_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("commits.id"), nullable=True
    )
    ontology_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ontologies.id"), nullable=False)
    ontology_version: Mapped[int] = mapped_column(Integer, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    stats: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"<Commit id={self.id!r} dataset_id={self.dataset_id!r} message={self.message!r}>"


class CommitSample(Base):
    __tablename__ = "commit_samples"

    commit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("commits.id"), primary_key=True)
    sample_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("samples.id"), primary_key=True)
    annotation_revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("annotation_revisions.id"), nullable=False
    )
    split: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (Index("ix_commit_samples_commit_id", "commit_id"),)

    def __repr__(self) -> str:
        return (
            f"<CommitSample commit_id={self.commit_id!r}"
            f" sample_id={self.sample_id!r} split={self.split!r}>"
        )


class Ref(Base, EntityBase):
    __tablename__ = "refs"

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("datasets.id"), nullable=False, index=True
    )
    ref_type: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    target_commit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("commits.id"), nullable=False)
    is_mutable: Mapped[bool] = mapped_column(Boolean, nullable=False)

    __table_args__ = (
        UniqueConstraint("dataset_id", "ref_type", "name", name="uq_refs_dataset_type_name"),
    )

    def __repr__(self) -> str:
        return (
            f"<Ref id={self.id!r} dataset_id={self.dataset_id!r}"
            f" ref_type={self.ref_type!r} name={self.name!r}>"
        )


class ProjectDatasetLink(Base, EntityBase):
    __tablename__ = "project_dataset_links"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id"), nullable=False, index=True
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("datasets.id"), nullable=False, index=True
    )
    pinned_commit_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("commits.id"), nullable=True
    )
    ref_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("refs.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "dataset_id",
            name="uq_project_dataset_links_project_dataset",
        ),
        CheckConstraint(
            "(pinned_commit_id IS NOT NULL AND ref_id IS NULL)"
            " OR (pinned_commit_id IS NULL AND ref_id IS NOT NULL)",
            name="ck_project_dataset_links_one_target",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ProjectDatasetLink id={self.id!r}"
            f" project_id={self.project_id!r} dataset_id={self.dataset_id!r}>"
        )
