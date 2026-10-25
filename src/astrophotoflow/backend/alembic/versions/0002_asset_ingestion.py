"""Stage-two asset ingestion, editable facts, datasets, tasks and FITS previews."""
from alembic import op
import sqlalchemy as sa

revision = "0002_asset_ingestion"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("asset", sa.Column("classification", sa.JSON(), nullable=True))
    op.add_column("asset", sa.Column("parameters", sa.JSON(), server_default=sa.text("'{}'"), nullable=False))
    op.add_column("asset", sa.Column("value_sources", sa.JSON(), server_default=sa.text("'{}'"), nullable=False))
    op.add_column("asset", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("asset", sa.Column("status", sa.String(16), server_default="active", nullable=False))
    op.add_column("asset", sa.Column("revision", sa.Integer(), server_default="1", nullable=False))
    op.create_index("ix_asset_status_created", "asset", ["status", "created_at"])

    op.create_table(
        "dataset",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("current_version_id", sa.String(36), sa.ForeignKey("dataset_version.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_dataset_status"),
        sa.CheckConstraint("revision >= 1", name="ck_dataset_revision"),
    )
    op.create_index("ix_dataset_status_created", "dataset", ["status", "created_at"])
    op.create_table(
        "dataset_version",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dataset_id", sa.String(36), sa.ForeignKey("dataset.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.UniqueConstraint("dataset_id", "version_number", name="uq_dataset_version_number"),
        sa.CheckConstraint("version_number > 0", name="ck_dataset_version_number"),
    )
    op.create_index("ix_dataset_version_dataset_created", "dataset_version", ["dataset_id", "created_at"])
    op.create_table(
        "dataset_member",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dataset_version_id", sa.String(36), sa.ForeignKey("dataset_version.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_version_id", sa.String(36), sa.ForeignKey("asset_version.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("relative_path", sa.Text()),
        sa.UniqueConstraint("dataset_version_id", "asset_version_id", name="uq_dataset_member_asset_version"),
        sa.UniqueConstraint("dataset_version_id", "position", name="uq_dataset_member_position"),
        sa.CheckConstraint("position >= 0", name="ck_dataset_member_position"),
    )
    op.create_index("ix_dataset_member_version_position", "dataset_member", ["dataset_version_id", "position"])
    op.create_table(
        "project_dataset_reference",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("project.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_id", sa.String(36), sa.ForeignKey("dataset.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dataset_version_id", sa.String(36), sa.ForeignKey("dataset_version.id"), nullable=False),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.UniqueConstraint("project_id", "dataset_version_id", name="uq_project_dataset_version"),
    )
    op.create_index("ix_project_dataset_reference_project", "project_dataset_reference", ["project_id", "added_at"])
    op.create_table(
        "asset_task",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("storage_mode", sa.String(16), nullable=False),
        sa.Column("classification", sa.JSON(), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("dataset_name", sa.String()),
        sa.Column("target_dataset_id", sa.String(36)),
        sa.Column("dataset_base_revision", sa.Integer()),
        sa.Column("dataset_id", sa.String(36), sa.ForeignKey("dataset.id")),
        sa.Column("enumeration_completed", sa.Boolean(), nullable=False),
        sa.Column("retry_of_task_id", sa.String(36), sa.ForeignKey("asset_task.id")),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("error", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued','running','cancelling','completed','completed_with_errors','failed','cancelled','interrupted')",
            name="ck_asset_task_status",
        ),
        sa.CheckConstraint("storage_mode IN ('reference','managed')", name="ck_asset_task_storage_mode"),
    )
    op.create_index("ix_asset_task_created", "asset_task", ["created_at"])
    op.create_table(
        "asset_task_item",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("asset_task.id", ondelete="CASCADE"), nullable=False),
        sa.Column("root_item_id", sa.String(36), nullable=False),
        sa.Column("retry_of_item_id", sa.String(36)),
        sa.Column("root_id", sa.String(128), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("source_identity", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("content_status", sa.String(16), nullable=False),
        sa.Column("metadata_status", sa.String(16), nullable=False),
        sa.Column("preview_status", sa.String(16), nullable=False),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("asset.id")),
        sa.Column("asset_version_id", sa.String(36), sa.ForeignKey("asset_version.id")),
        sa.Column("error", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.UniqueConstraint("task_id", "id", name="uq_asset_task_item_task_id_id"),
        sa.UniqueConstraint("task_id", "position", name="uq_asset_task_item_position"),
    )
    op.create_index("ix_asset_task_item_task_created", "asset_task_item", ["task_id", "created_at"])
    op.create_index("ix_asset_task_item_root", "asset_task_item", ["root_item_id"])
    op.create_table(
        "fits_hdu_metadata",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("asset_version_id", sa.String(36), sa.ForeignKey("asset_version.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hdu_index", sa.Integer(), nullable=False),
        sa.Column("name", sa.String()),
        sa.Column("hdu_type", sa.String(32), nullable=False),
        sa.Column("shape", sa.JSON()),
        sa.Column("bitpix", sa.Integer()),
        sa.Column("pixel_type", sa.String(64)),
        sa.Column("bscale", sa.Float()),
        sa.Column("bzero", sa.Float()),
        sa.Column("bunit", sa.String(128)),
        sa.Column("header_cards", sa.JSON(), nullable=False),
        sa.Column("parser_version", sa.String(64), nullable=False),
        sa.Column("supported_kind", sa.String(16)),
        sa.Column("is_selected", sa.Boolean(), nullable=False),
        sa.Column("parse_error", sa.Text()),
        sa.UniqueConstraint("asset_version_id", "hdu_index", name="uq_fits_hdu_version_index"),
    )
    op.create_index("ix_fits_hdu_version", "fits_hdu_metadata", ["asset_version_id"])
    op.create_table(
        "preview",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("asset_version_id", sa.String(36), sa.ForeignKey("asset_version.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hdu_index", sa.Integer(), nullable=False),
        sa.Column("size", sa.String(16), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.String(64), nullable=False),
        sa.Column("display_parameters", sa.JSON(), nullable=False),
        sa.Column("algorithm_version", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.UniqueConstraint("asset_version_id", "hdu_index", "size", "algorithm_version", name="uq_preview_identity"),
    )
    op.create_index("ix_preview_version", "preview", ["asset_version_id"])


def downgrade() -> None:
    op.drop_index("ix_preview_version", table_name="preview")
    op.drop_table("preview")
    op.drop_index("ix_fits_hdu_version", table_name="fits_hdu_metadata")
    op.drop_table("fits_hdu_metadata")
    op.drop_index("ix_asset_task_item_root", table_name="asset_task_item")
    op.drop_index("ix_asset_task_item_task_created", table_name="asset_task_item")
    op.drop_table("asset_task_item")
    op.drop_index("ix_asset_task_created", table_name="asset_task")
    op.drop_table("asset_task")
    op.drop_index("ix_project_dataset_reference_project", table_name="project_dataset_reference")
    op.drop_table("project_dataset_reference")
    op.drop_index("ix_dataset_member_version_position", table_name="dataset_member")
    op.drop_table("dataset_member")
    op.drop_index("ix_dataset_version_dataset_created", table_name="dataset_version")
    op.drop_table("dataset_version")
    op.drop_index("ix_dataset_status_created", table_name="dataset")
    op.drop_table("dataset")
    op.drop_index("ix_asset_status_created", table_name="asset")
    op.drop_column("asset", "revision")
    op.drop_column("asset", "status")
    op.drop_column("asset", "notes")
    op.drop_column("asset", "value_sources")
    op.drop_column("asset", "parameters")
    op.drop_column("asset", "classification")
