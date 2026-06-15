"""make model_versions.training_container_id nullable

Ad-hoc "Train this commit" runs bake git_url + entry_point into an ephemeral
export_yolo → train run scoped to a commit, with no pre-registered
TrainingContainer. The resulting ModelVersion therefore has no container, so the
FK becomes nullable (it stays an FK — set when a container is used).

Revision ID: 0003
Revises: 0002
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "model_versions",
        "training_container_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "model_versions",
        "training_container_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
