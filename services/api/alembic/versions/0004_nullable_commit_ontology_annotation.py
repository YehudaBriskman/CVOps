"""allow raw (unannotated) image datasets

Make commits.ontology_id / ontology_version and commit_samples.annotation_
revision_id nullable so a dataset can hold raw images that have no ontology
or annotations. Annotated commits are unaffected.

Revision ID: 0004
Revises: 0003
"""

from __future__ import annotations

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("commits", "ontology_id", nullable=True)
    op.alter_column("commits", "ontology_version", nullable=True)
    op.alter_column("commit_samples", "annotation_revision_id", nullable=True)


def downgrade() -> None:
    op.alter_column("commit_samples", "annotation_revision_id", nullable=False)
    op.alter_column("commits", "ontology_version", nullable=False)
    op.alter_column("commits", "ontology_id", nullable=False)
