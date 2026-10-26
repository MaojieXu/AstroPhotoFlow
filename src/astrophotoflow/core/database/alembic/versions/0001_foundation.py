"""Initial foundation schema.

Revision ID: 0001_foundation
Revises:
Create Date: 2026-10-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("target_name", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_project_status"),
        sa.CheckConstraint("revision >= 1", name="ck_project_revision"),
    )
    op.create_table(
        "equipment",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("serial_number", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("specs", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.CheckConstraint("kind IN ('camera', 'optical_system', 'filter')", name="ck_equipment_kind"),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_equipment_status"),
        sa.CheckConstraint("revision >= 1", name="ck_equipment_revision"),
    )
    op.create_table(
        "capture_profile",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("camera_id", sa.String(36), sa.ForeignKey("equipment.id"), nullable=False),
        sa.Column("optical_system_id", sa.String(36), sa.ForeignKey("equipment.id"), nullable=True),
        sa.Column("filter_id", sa.String(36), sa.ForeignKey("equipment.id"), nullable=True),
        sa.Column("frame_type", sa.String(16), nullable=False),
        sa.Column("exposure_seconds", sa.Float(), nullable=True),
        sa.Column("gain", sa.Float(), nullable=True),
        sa.Column("offset", sa.Float(), nullable=True),
        sa.Column("sensor_temperature_c", sa.Float(), nullable=True),
        sa.Column("binning_x", sa.Integer(), nullable=True),
        sa.Column("binning_y", sa.Integer(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.CheckConstraint("frame_type IN ('light', 'bias', 'dark', 'flat', 'dark_flat')", name="ck_capture_profile_frame_type"),
        sa.CheckConstraint("exposure_seconds IS NULL OR exposure_seconds >= 0", name="ck_capture_profile_exposure"),
        sa.CheckConstraint("binning_x IS NULL OR binning_x > 0", name="ck_capture_profile_binning_x"),
        sa.CheckConstraint("binning_y IS NULL OR binning_y > 0", name="ck_capture_profile_binning_y"),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_capture_profile_status"),
        sa.CheckConstraint("revision >= 1", name="ck_capture_profile_revision"),
    )
    op.create_table(
        "project_capture_profile",
        sa.Column("project_id", sa.String(36), sa.ForeignKey("project.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("capture_profile_id", sa.String(36), sa.ForeignKey("capture_profile.id", ondelete="CASCADE"), primary_key=True),
        sa.UniqueConstraint("project_id", "capture_profile_id", name="uq_project_capture_profile"),
    )
    op.create_table(
        "asset",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("owner_project_id", sa.String(36), sa.ForeignKey("project.id"), nullable=True),
        sa.Column("role", sa.String(24), nullable=False),
        sa.Column("current_version_id", sa.String(36), sa.ForeignKey("asset_version.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.CheckConstraint("scope IN ('shared', 'project')", name="ck_asset_scope"),
        sa.CheckConstraint("scope = 'shared' OR (scope = 'project' AND owner_project_id IS NOT NULL)", name="ck_asset_owner_scope"),
        sa.CheckConstraint("role IN ('raw', 'calibration', 'intermediate', 'final')", name="ck_asset_role"),
    )
    op.create_table(
        "asset_version",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("asset.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("storage_mode", sa.String(16), nullable=False),
        sa.Column("storage_location", sa.String(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.String(71), nullable=True),
        sa.Column("availability", sa.String(16), nullable=False),
        sa.Column("camera_id", sa.String(36), sa.ForeignKey("equipment.id"), nullable=True),
        sa.Column("optical_system_id", sa.String(36), sa.ForeignKey("equipment.id"), nullable=True),
        sa.Column("filter_id", sa.String(36), sa.ForeignKey("equipment.id"), nullable=True),
        sa.Column("capture_profile_id", sa.String(36), sa.ForeignKey("capture_profile.id"), nullable=True),
        sa.Column("frame_type", sa.String(16), nullable=True),
        sa.Column("calibration_level", sa.String(16), nullable=True),
        sa.Column("capture_snapshot", sa.JSON(), nullable=True),
        sa.Column("scientific_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.UniqueConstraint("asset_id", "version_number", name="uq_asset_version_number"),
        sa.CheckConstraint("version_number > 0", name="ck_asset_version_number"),
        sa.CheckConstraint("storage_mode IN ('reference', 'managed')", name="ck_asset_version_storage_mode"),
        sa.CheckConstraint("byte_size IS NULL OR byte_size >= 0", name="ck_asset_version_byte_size"),
        sa.CheckConstraint("availability IN ('unknown', 'available', 'changed', 'missing')", name="ck_asset_version_availability"),
        sa.CheckConstraint("frame_type IS NULL OR frame_type IN ('light', 'bias', 'dark', 'flat', 'dark_flat')", name="ck_asset_version_frame_type"),
        sa.CheckConstraint("calibration_level IS NULL OR calibration_level IN ('individual', 'master')", name="ck_asset_version_calibration_level"),
    )
    op.create_table(
        "project_asset_reference",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("project.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_version_id", sa.String(36), sa.ForeignKey("asset_version.id"), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.UniqueConstraint("project_id", "asset_version_id", name="uq_project_asset_version"),
    )
    op.create_index("ix_project_name", "project", ["name"])
    op.create_index("ix_equipment_kind_status", "equipment", ["kind", "status"])
    op.create_index("ix_capture_profile_camera_status", "capture_profile", ["camera_id", "status"])
    op.create_index("ix_asset_scope_created", "asset", ["scope", "created_at"])
    op.create_index("ix_asset_owner_project", "asset", ["owner_project_id"])
    op.create_index("ix_asset_version_asset_created", "asset_version", ["asset_id", "created_at"])
    op.create_index("ix_project_asset_reference_project", "project_asset_reference", ["project_id", "added_at"])


def downgrade() -> None:
    op.drop_index("ix_project_asset_reference_project", table_name="project_asset_reference")
    op.drop_index("ix_asset_version_asset_created", table_name="asset_version")
    op.drop_index("ix_asset_owner_project", table_name="asset")
    op.drop_index("ix_asset_scope_created", table_name="asset")
    op.drop_index("ix_capture_profile_camera_status", table_name="capture_profile")
    op.drop_index("ix_equipment_kind_status", table_name="equipment")
    op.drop_index("ix_project_name", table_name="project")
    op.drop_table("project_asset_reference")
    op.drop_table("asset_version")
    op.drop_table("asset")
    op.drop_table("project_capture_profile")
    op.drop_table("capture_profile")
    op.drop_table("equipment")
    op.drop_table("project")
