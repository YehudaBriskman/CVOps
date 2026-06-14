"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-08
"""
from __future__ import annotations
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. orgs
    op.create_table(
        "orgs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("settings", postgresql.JSONB(), nullable=True),
        sa.UniqueConstraint("name", name="uq_orgs_name"),
    )

    # 2. blobs
    op.create_table(
        "blobs",
        sa.Column("hash", sa.Text(), primary_key=True),
        sa.Column("storage_backend", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("media_type", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # 3. type_schemas
    op.create_table(
        "type_schemas",
        sa.Column("type_key", sa.Text(), primary_key=True),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("json_schema", postgresql.JSONB(), nullable=False),
        sa.Column(
            "schema_version",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'1'"),
        ),
        sa.Column("ui_hints", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # 4. events
    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_type", sa.Text(), nullable=True),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
    )

    # 5. users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.ForeignKeyConstraint(["org_id"], ["orgs.id"], name="fk_users_org_id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    # 6. memberships
    op.create_table(
        "memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"], ["orgs.id"], name="fk_memberships_org_id"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_memberships_user_id"
        ),
        sa.UniqueConstraint(
            "org_id", "user_id", name="uq_memberships_org_user"
        ),
    )

    # 7. projects (without default_ontology_id — circular dep added later)
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "task_type",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'detection'"),
        ),
        sa.Column("settings", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(
            ["org_id"], ["orgs.id"], name="fk_projects_org_id"
        ),
    )

    # 8. ontologies
    op.create_table(
        "ontologies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_ontologies_project_id"
        ),
        sa.UniqueConstraint(
            "project_id", "name", name="uq_ontologies_project_name"
        ),
    )

    # 9. label_classes
    op.create_table(
        "label_classes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("ontology_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("class_key", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column(
            "color",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'#FF0000'"),
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["ontology_id"],
            ["ontologies.id"],
            name="fk_label_classes_ontology_id",
        ),
        sa.UniqueConstraint(
            "ontology_id",
            "class_key",
            name="uq_label_classes_ontology_key",
        ),
        sa.UniqueConstraint(
            "ontology_id",
            "sort_order",
            name="uq_label_classes_ontology_order",
        ),
    )

    # 10. data_sources
    op.create_table(
        "data_sources",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("blob_hash", sa.Text(), nullable=True),
        sa.Column("external_uri", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_data_sources_project_id",
        ),
        sa.ForeignKeyConstraint(
            ["blob_hash"], ["blobs.hash"], name="fk_data_sources_blob_hash"
        ),
    )

    # 11. samples
    op.create_table(
        "samples",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("blob_hash", sa.Text(), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("frame_index", sa.Integer(), nullable=True),
        sa.Column("perceptual_hash", sa.Text(), nullable=True),
        sa.Column("thumbnail_hash", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_samples_project_id"
        ),
        sa.ForeignKeyConstraint(
            ["blob_hash"], ["blobs.hash"], name="fk_samples_blob_hash"
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["data_sources.id"], name="fk_samples_source_id"
        ),
        sa.ForeignKeyConstraint(
            ["thumbnail_hash"],
            ["blobs.hash"],
            name="fk_samples_thumbnail_hash",
        ),
        sa.UniqueConstraint(
            "project_id", "blob_hash", name="uq_samples_project_blob"
        ),
    )

    # 12. annotation_revisions
    op.create_table(
        "annotation_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sample_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ontology_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ontology_version", sa.Integer(), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column(
            "parent_revision_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("provenance", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_annotation_revisions_project_id",
        ),
        sa.ForeignKeyConstraint(
            ["sample_id"],
            ["samples.id"],
            name="fk_annotation_revisions_sample_id",
        ),
        sa.ForeignKeyConstraint(
            ["ontology_id"],
            ["ontologies.id"],
            name="fk_annotation_revisions_ontology_id",
        ),
        sa.ForeignKeyConstraint(
            ["parent_revision_id"],
            ["annotation_revisions.id"],
            name="fk_annotation_revisions_parent_revision_id",
        ),
    )

    # 13. datasets
    op.create_table(
        "datasets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_datasets_project_id"
        ),
        sa.UniqueConstraint(
            "project_id", "name", name="uq_datasets_project_name"
        ),
    )

    # 14. commits
    op.create_table(
        "commits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "parent_commit_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "second_parent_commit_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("ontology_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ontology_version", sa.Integer(), nullable=False),
        sa.Column(
            "message",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column("stats", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_commits_project_id"
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"], ["datasets.id"], name="fk_commits_dataset_id"
        ),
        sa.ForeignKeyConstraint(
            ["parent_commit_id"],
            ["commits.id"],
            name="fk_commits_parent_commit_id",
        ),
        sa.ForeignKeyConstraint(
            ["second_parent_commit_id"],
            ["commits.id"],
            name="fk_commits_second_parent_commit_id",
        ),
        sa.ForeignKeyConstraint(
            ["ontology_id"], ["ontologies.id"], name="fk_commits_ontology_id"
        ),
    )

    # 15. commit_samples
    op.create_table(
        "commit_samples",
        sa.Column("commit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sample_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "annotation_revision_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("split", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("commit_id", "sample_id", name="pk_commit_samples"),
        sa.ForeignKeyConstraint(
            ["commit_id"], ["commits.id"], name="fk_commit_samples_commit_id"
        ),
        sa.ForeignKeyConstraint(
            ["sample_id"], ["samples.id"], name="fk_commit_samples_sample_id"
        ),
        sa.ForeignKeyConstraint(
            ["annotation_revision_id"],
            ["annotation_revisions.id"],
            name="fk_commit_samples_annotation_revision_id",
        ),
    )

    # 16. refs
    op.create_table(
        "refs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ref_type", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "target_commit_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("is_mutable", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id"], ["datasets.id"], name="fk_refs_dataset_id"
        ),
        sa.ForeignKeyConstraint(
            ["target_commit_id"],
            ["commits.id"],
            name="fk_refs_target_commit_id",
        ),
        sa.UniqueConstraint(
            "dataset_id",
            "ref_type",
            "name",
            name="uq_refs_dataset_type_name",
        ),
    )

    # 17. project_dataset_links
    op.create_table(
        "project_dataset_links",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "pinned_commit_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("ref_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_dataset_links_project_id",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
            name="fk_project_dataset_links_dataset_id",
        ),
        sa.ForeignKeyConstraint(
            ["pinned_commit_id"],
            ["commits.id"],
            name="fk_project_dataset_links_pinned_commit_id",
        ),
        sa.ForeignKeyConstraint(
            ["ref_id"], ["refs.id"], name="fk_project_dataset_links_ref_id"
        ),
        sa.UniqueConstraint(
            "project_id",
            "dataset_id",
            name="uq_project_dataset_links_project_dataset",
        ),
        sa.CheckConstraint(
            "(pinned_commit_id IS NOT NULL AND ref_id IS NULL) OR (pinned_commit_id IS NULL AND ref_id IS NOT NULL)",
            name="ck_project_dataset_links_one_target",
        ),
    )

    # 18. workflows
    op.create_table(
        "workflows",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("definition", postgresql.JSONB(), nullable=False),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_workflows_project_id"
        ),
        sa.UniqueConstraint(
            "project_id", "name", name="uq_workflows_project_name"
        ),
    )

    # 19. runs
    op.create_table(
        "runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("parent_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("workflow_version", sa.Integer(), nullable=True),
        sa.Column("step_id", sa.Text(), nullable=True),
        sa.Column("step_type", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "input_refs",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "output_refs",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "config",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("metrics", postgresql.JSONB(), nullable=True),
        sa.Column("logs_blob_hash", sa.Text(), nullable=True),
        sa.Column(
            "attempt",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name="fk_runs_project_id"
        ),
        sa.ForeignKeyConstraint(
            ["parent_run_id"], ["runs.id"], name="fk_runs_parent_run_id"
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"], ["workflows.id"], name="fk_runs_workflow_id"
        ),
        sa.ForeignKeyConstraint(
            ["logs_blob_hash"], ["blobs.hash"], name="fk_runs_logs_blob_hash"
        ),
    )

    # 20. training_containers
    op.create_table(
        "training_containers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("image", sa.Text(), nullable=False),
        sa.Column("icd_config", postgresql.JSONB(), nullable=False),
        sa.Column(
            "icd_schema_version",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'1.0'"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_training_containers_project_id",
        ),
        sa.UniqueConstraint(
            "project_id",
            "name",
            name="uq_training_containers_project_name",
        ),
    )

    # 21. model_versions
    op.create_table(
        "model_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("blob_hash", sa.Text(), nullable=False),
        sa.Column(
            "trained_on_commit_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "training_container_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("base_model", sa.Text(), nullable=True),
        sa.Column("hyperparams", postgresql.JSONB(), nullable=True),
        sa.Column("metrics", postgresql.JSONB(), nullable=True),
        sa.Column("code_version", sa.Text(), nullable=True),
        sa.Column("env_hash", sa.Text(), nullable=True),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("mlflow_run_id", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_model_versions_project_id",
        ),
        sa.ForeignKeyConstraint(
            ["blob_hash"], ["blobs.hash"], name="fk_model_versions_blob_hash"
        ),
        sa.ForeignKeyConstraint(
            ["trained_on_commit_id"],
            ["commits.id"],
            name="fk_model_versions_trained_on_commit_id",
        ),
        sa.ForeignKeyConstraint(
            ["training_container_id"],
            ["training_containers.id"],
            name="fk_model_versions_training_container_id",
        ),
    )

    # 22. labeling_jobs
    op.create_table(
        "labeling_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_id", sa.Text(), nullable=False),
        sa.Column("cvat_project_id", sa.Integer(), nullable=True),
        sa.Column("cvat_task_id", sa.Integer(), nullable=False),
        sa.Column(
            "cvat_job_ids",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pushed'"),
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("sync_error", sa.Text(), nullable=True),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("annotation_revision_ids_in", postgresql.JSONB(), nullable=True),
        sa.Column(
            "annotation_revision_ids_out", postgresql.JSONB(), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_labeling_jobs_project_id",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name="fk_labeling_jobs_run_id"
        ),
    )

    # Deferred circular FK: projects.default_ontology_id → ontologies.id
    op.add_column(
        "projects",
        sa.Column(
            "default_ontology_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
    )
    op.create_foreign_key(
        "fk_projects_default_ontology",
        "projects",
        "ontologies",
        ["default_ontology_id"],
        ["id"],
    )

    # Indexes
    op.create_index(
        "ix_events_entity",
        "events",
        ["entity_type", "entity_id", "created_at"],
    )
    op.create_index(
        "ix_annotation_revisions_sample_revision",
        "annotation_revisions",
        ["sample_id", "revision_no"],
    )
    op.create_index(
        "ix_data_sources_project_status",
        "data_sources",
        ["project_id", "status"],
    )
    op.create_index(
        "ix_commit_samples_commit_id",
        "commit_samples",
        ["commit_id"],
    )


def downgrade() -> None:
    # Drop indexes first
    op.drop_index("ix_commit_samples_commit_id", table_name="commit_samples")
    op.drop_index(
        "ix_data_sources_project_status", table_name="data_sources"
    )
    op.drop_index(
        "ix_annotation_revisions_sample_revision",
        table_name="annotation_revisions",
    )
    op.drop_index("ix_events_entity", table_name="events")

    # Drop deferred circular FK and column before dropping ontologies
    op.drop_constraint(
        "fk_projects_default_ontology", "projects", type_="foreignkey"
    )
    op.drop_column("projects", "default_ontology_id")

    # Drop tables in reverse creation order
    op.drop_table("labeling_jobs")
    op.drop_table("model_versions")
    op.drop_table("training_containers")
    op.drop_table("runs")
    op.drop_table("workflows")
    op.drop_table("project_dataset_links")
    op.drop_table("refs")
    op.drop_table("commit_samples")
    op.drop_table("commits")
    op.drop_table("datasets")
    op.drop_table("annotation_revisions")
    op.drop_table("samples")
    op.drop_table("data_sources")
    op.drop_table("label_classes")
    op.drop_table("ontologies")
    op.drop_table("projects")
    op.drop_table("memberships")
    op.drop_table("users")
    op.drop_table("events")
    op.drop_table("type_schemas")
    op.drop_table("blobs")
    op.drop_table("orgs")
