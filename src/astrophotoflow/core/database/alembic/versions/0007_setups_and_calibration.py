"""Shared equipment setup, capture preset and versioned calibration foundation."""
from alembic import op
import sqlalchemy as sa


revision = "0007_setups_and_calibration"
down_revision = "0006_library_trash_cleanup_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Only replace the CHECK. Rebuilding this heavily referenced table with
    # SQLite foreign_keys enabled would cascade-delete its dependants.
    connection = op.get_bind()
    context = op.get_context()
    with context.autocommit_block():
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
    with op.batch_alter_table("equipment") as batch:
        batch.drop_constraint("ck_equipment_kind", type_="check")
        batch.create_check_constraint("ck_equipment_kind", "kind IN ('camera', 'optical_system', 'filter', 'telescope', 'mount', 'accessory')")
    with context.autocommit_block():
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    op.create_table(
        "equipment_setup",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("components", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_equipment_setup_status"),
        sa.CheckConstraint("revision >= 1", name="ck_equipment_setup_revision"),
    )
    op.create_table(
        "capture_preset",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("equipment_setup_id", sa.String(36), sa.ForeignKey("equipment_setup.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("classification", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("parameters", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.current_timestamp()),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_capture_preset_status"),
        sa.CheckConstraint("revision >= 1", name="ck_capture_preset_revision"),
    )
    op.add_column("asset_task", sa.Column("import_defaults_snapshot", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("dataset_version", sa.Column("calibration_defaults", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("dataset_member", sa.Column("calibration_overrides", sa.JSON(), nullable=False, server_default="{}"))


def downgrade() -> None:
    raise RuntimeError("0007 downgrade is unsupported; restore the pre-upgrade SQLite backup.")
