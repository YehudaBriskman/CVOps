import uuid
from typing import Any, Optional

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from cvops_api.db.base import Base, EntityBase


class Project(Base, EntityBase):
    __tablename__ = "projects"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orgs.id"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)

    task_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="detection",
        server_default="detection",
    )

    default_ontology_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey(
            "ontologies.id",
            use_alter=True,
            name="fk_projects_default_ontology",
        ),
        nullable=True,
    )

    settings: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<Project id={self.id!r} name={self.name!r} "
            f"org_id={self.org_id!r} task_type={self.task_type!r}>"
        )
