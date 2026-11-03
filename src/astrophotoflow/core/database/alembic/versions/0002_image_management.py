"""Explicit image facts, provenance, and immutable calibration configurations."""
import sqlalchemy as sa
from alembic import op

revision = "0002_image_management"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("asset", sa.Column("readout_mode", sa.String(128), nullable=True))
    op.add_column("asset_task", sa.Column("request_id", sa.String(36), nullable=True))
    op.add_column("asset_task", sa.Column("request_fingerprint", sa.String(64), nullable=True))
    op.add_column("asset_task", sa.Column("image_import_plan", sa.JSON(), nullable=True))
    op.create_index("uq_asset_task_request_id", "asset_task", ["request_id"], unique=True)
    for name in ("dataset_calibration", "member_calibration"):
        op.add_column(name, sa.Column("state", sa.String(16), nullable=True))

    op.create_table("image_metadata_state",
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("asset.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("target_name", sa.String(), nullable=True),
        sa.Column("capture_start_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("capture_end_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("master_created_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("equipment_context", sa.JSON(), nullable=True))
    for index, column in (("target", "target_name"), ("capture_start", "capture_start_utc"), ("master_created", "master_created_utc")):
        op.create_index(f"ix_image_metadata_{index}", "image_metadata_state", [column])

    op.create_table("master_provenance_revision",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("asset_version_id", sa.String(36), sa.ForeignKey("asset_version.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("asset_revision", sa.Integer(), nullable=False),
        sa.Column("source_kind", sa.String(24), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("source_time_range", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("asset_version_id", "revision", name="uq_master_provenance_revision"),
        sa.CheckConstraint("revision > 0", name="ck_master_provenance_revision"),
        sa.CheckConstraint("asset_revision > 0", name="ck_master_provenance_asset_revision"),
        sa.CheckConstraint("source_kind = 'user_declared'", name="ck_master_provenance_source_kind"))
    op.create_index("ix_master_provenance_asset_version", "master_provenance_revision", ["asset_version_id"])
    op.create_table("master_provenance_reference",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provenance_id", sa.String(36), sa.ForeignKey("master_provenance_revision.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_version_id", sa.String(36), sa.ForeignKey("asset_version.id"), nullable=True),
        sa.Column("dataset_version_id", sa.String(36), sa.ForeignKey("dataset_version.id"), nullable=True),
        sa.CheckConstraint("(asset_version_id IS NULL) != (dataset_version_id IS NULL)", name="ck_master_provenance_reference_target"))
    op.create_index("ix_master_provenance_reference_asset", "master_provenance_reference", ["asset_version_id"])
    op.create_index("ix_master_provenance_reference_dataset", "master_provenance_reference", ["dataset_version_id"])

    op.create_table("image_calibration_configuration",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("asset_version_id", sa.String(36), sa.ForeignKey("asset_version.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("bindings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("asset_version_id", "version_number", name="uq_image_calibration_version"),
        sa.CheckConstraint("version_number >= 1", name="ck_image_calibration_version"))
    op.create_table("image_calibration_operation",
        sa.Column("request_id", sa.String(36), primary_key=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()))


def downgrade() -> None:
    raise RuntimeError("Image-management downgrade would discard scientific relationships; restore the pre-upgrade backup instead.")
