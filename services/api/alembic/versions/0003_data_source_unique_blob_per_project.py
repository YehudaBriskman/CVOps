"""enforce one data source per (project, blob) for live, hashed rows

Re-uploading the same video into a project previously created a second data
source silently. A partial unique index makes that a constraint violation while
still allowing: soft-deleted rows (re-add after delete), still-`pending` sources
that haven't been hashed yet (null blob_hash), and the same video in a different
project.

Revision ID: 0003
Revises: 0002
"""

from __future__ import annotations

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_data_sources_project_blob",
        "data_sources",
        ["project_id", "blob_hash"],
        unique=True,
        postgresql_where="deleted_at IS NULL AND blob_hash IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_index("uq_data_sources_project_blob", table_name="data_sources")
