"""samples curation: review_status, collections, tags

Adds the operational review_status flag to samples, plus collections and tags
(both project-scoped, soft-deletable) with their sample join tables. Mirrors the
0001 style: explicit postgresql.UUID, gen_random_uuid()/now() server defaults,
named constraints so downgrade drops cleanly. TEXT + CHECK for the status enum
(matches data_sources.status / runs.status — no native PG enum).

Revision ID: 0005
Revises: 0004
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _spine() -> list[sa.Column]:
    """The EntityBase spine columns, matching db/base.py."""
    return [
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    # ── samples.review_status ────────────────────────────────────────────────
    op.add_column(
        "samples",
        sa.Column(
            "review_status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'unreviewed'"),
        ),
    )
    op.create_check_constraint(
        "ck_samples_review_status",
        "samples",
        "review_status IN ('unreviewed','accepted','rejected')",
    )
    op.create_index("ix_samples_project_review_status", "samples", ["project_id", "review_status"])

    # ── collections ──────────────────────────────────────────────────────────
    op.create_table(
        "collections",
        *_spine(),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name="fk_collections_project_id"),
        sa.UniqueConstraint("project_id", "name", name="uq_collections_project_name"),
    )
    op.create_index("ix_collections_id", "collections", ["id"])
    op.create_index("ix_collections_deleted_at", "collections", ["deleted_at"])
    op.create_index("ix_collections_project_id", "collections", ["project_id"])

    op.create_table(
        "collection_samples",
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sample_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("added_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["collection_id"], ["collections.id"], name="fk_collection_samples_collection_id"
        ),
        sa.ForeignKeyConstraint(
            ["sample_id"], ["samples.id"], name="fk_collection_samples_sample_id"
        ),
        sa.PrimaryKeyConstraint("collection_id", "sample_id", name="pk_collection_samples"),
    )
    op.create_index("ix_collection_samples_sample_id", "collection_samples", ["sample_id"])

    # ── tags ──────────────────────────────────────────────────────────────────
    op.create_table(
        "tags",
        *_spine(),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("color", sa.Text(), nullable=False, server_default=sa.text("'#888888'")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name="fk_tags_project_id"),
        sa.UniqueConstraint("project_id", "name", name="uq_tags_project_name"),
    )
    op.create_index("ix_tags_id", "tags", ["id"])
    op.create_index("ix_tags_deleted_at", "tags", ["deleted_at"])
    op.create_index("ix_tags_project_id", "tags", ["project_id"])

    op.create_table(
        "sample_tags",
        sa.Column("sample_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("added_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["sample_id"], ["samples.id"], name="fk_sample_tags_sample_id"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], name="fk_sample_tags_tag_id"),
        sa.PrimaryKeyConstraint("sample_id", "tag_id", name="pk_sample_tags"),
    )
    op.create_index("ix_sample_tags_tag_id", "sample_tags", ["tag_id"])


def downgrade() -> None:
    op.drop_table("sample_tags")
    op.drop_index("ix_tags_project_id", table_name="tags")
    op.drop_index("ix_tags_deleted_at", table_name="tags")
    op.drop_index("ix_tags_id", table_name="tags")
    op.drop_table("tags")

    op.drop_index("ix_collection_samples_sample_id", table_name="collection_samples")
    op.drop_table("collection_samples")
    op.drop_index("ix_collections_project_id", table_name="collections")
    op.drop_index("ix_collections_deleted_at", table_name="collections")
    op.drop_index("ix_collections_id", table_name="collections")
    op.drop_table("collections")

    op.drop_index("ix_samples_project_review_status", table_name="samples")
    op.drop_constraint("ck_samples_review_status", "samples", type_="check")
    op.drop_column("samples", "review_status")
