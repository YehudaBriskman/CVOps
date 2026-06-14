"""add projects.default_ingest_workflow_id

Backend auto-triggers this workflow when a data source finishes uploading.
Nullable FK to workflows.id; created with a named constraint so it can be
dropped cleanly on downgrade (mirrors fk_projects_default_ontology).

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "default_ingest_workflow_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_projects_default_ingest_workflow",
        "projects",
        "workflows",
        ["default_ingest_workflow_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_projects_default_ingest_workflow", "projects", type_="foreignkey"
    )
    op.drop_column("projects", "default_ingest_workflow_id")
