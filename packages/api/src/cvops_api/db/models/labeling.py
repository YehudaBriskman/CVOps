import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from cvops_api.db.base import Base, EntityBase


class LabelingJob(Base, EntityBase):
    __tablename__ = "labeling_jobs"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id"),
        nullable=False,
        index=True,
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("runs.id"),
        nullable=False,
        index=True,
    )

    step_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    cvat_project_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    cvat_task_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    cvat_job_ids: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
    )

    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="pushed",
        server_default="pushed",
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    sync_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    sample_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    annotation_revision_ids_in: Mapped[Optional[Any]] = mapped_column(
        JSONB,
        nullable=True,
    )

    annotation_revision_ids_out: Mapped[Optional[Any]] = mapped_column(
        JSONB,
        nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"<LabelingJob id={self.id!r} "
            f"run_id={self.run_id!r} "
            f"step_id={self.step_id!r} "
            f"cvat_task_id={self.cvat_task_id!r} "
            f"status={self.status!r}>"
        )
