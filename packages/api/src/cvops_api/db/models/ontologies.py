"""
D3 — Ontology and LabelClass models.

An Ontology belongs to a Project and defines the controlled vocabulary of
label classes used across that project's datasets and annotations.

A LabelClass is a single entry in that vocabulary.  The sort_order column
doubles as the YOLO class_id at export time and must therefore never be
reused or reordered once a class has been used in an annotation.
"""
import uuid

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from cvops_api.db.base import Base, EntityBase


class Ontology(Base, EntityBase):
    __tablename__ = "ontologies"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )

    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_ontologies_project_name"),
    )

    def __repr__(self) -> str:
        return (
            f"<Ontology id={self.id!r} project_id={self.project_id!r} "
            f"name={self.name!r} version={self.version!r}>"
        )


class LabelClass(Base, EntityBase):
    __tablename__ = "label_classes"

    ontology_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ontologies.id"),
        nullable=False,
        index=True,
    )
    class_key: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    color: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="#FF0000",
        server_default="#FF0000",
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "ontology_id", "class_key", name="uq_label_classes_ontology_key"
        ),
        UniqueConstraint(
            "ontology_id", "sort_order", name="uq_label_classes_ontology_order"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<LabelClass id={self.id!r} ontology_id={self.ontology_id!r} "
            f"class_key={self.class_key!r} sort_order={self.sort_order!r}>"
        )
