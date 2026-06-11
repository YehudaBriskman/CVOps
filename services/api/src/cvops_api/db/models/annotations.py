import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from cvops_api.db.base import Base


class AnnotationRevision(Base):
    """Append-only record of every annotation revision for a sample.

    Each row is immutable once written.  The revision_no is application-managed
    and increases monotonically (1-based) within the scope of a single sample.
    The parent_revision_id points to the immediately preceding revision so the
    full edit history can be reconstructed as a linked list.
    """

    __tablename__ = "annotation_revisions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        nullable=True,
    )

    # --- foreign keys ---
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id"),
        nullable=False,
        index=True,
    )
    sample_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("samples.id"),
        nullable=False,
        index=True,
    )
    ontology_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ontologies.id"),
        nullable=False,
    )

    # --- revision metadata ---
    ontology_version: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)

    # self-referential: points to the immediately preceding revision
    parent_revision_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("annotation_revisions.id"),
        nullable=True,
    )

    # --- payload ---
    # list of annotation objects: [{class_key, geometry, confidence, track_id}]
    payload: Mapped[Any] = mapped_column(JSONB, nullable=False)

    # dict: {source, model_version_id, author_user_id, confidence_threshold, review_status}
    provenance: Mapped[Any] = mapped_column(JSONB, nullable=False)

    __table_args__ = (Index("ix_annotation_revisions_sample_revision", "sample_id", "revision_no"),)

    def __repr__(self) -> str:
        return (
            f"<AnnotationRevision "
            f"id={self.id} "
            f"sample_id={self.sample_id} "
            f"revision_no={self.revision_no} "
            f"ontology_id={self.ontology_id} "
            f"ontology_version={self.ontology_version}"
            f">"
        )
