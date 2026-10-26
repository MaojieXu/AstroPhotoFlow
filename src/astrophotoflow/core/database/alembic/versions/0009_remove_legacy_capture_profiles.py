"""Remove the replaced capture profile model and its live references."""
from alembic import op


revision = "0009_remove_legacy_capture_profiles"
down_revision = "0008_asset_equipment_snapshot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    context = op.get_context()
    # Asset versions have incoming references from assets, groups and projects.
    # Rebuilding with FK enforcement enabled would cascade-delete those rows.
    with context.autocommit_block():
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
    with op.batch_alter_table(
        "asset_version", naming_convention={"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"},
    ) as batch:
        batch.drop_constraint("fk_asset_version_capture_profile_id_capture_profile", type_="foreignkey")
        batch.drop_column("capture_profile_id")
    op.drop_table("project_capture_profile")
    op.drop_table("capture_profile")
    with context.autocommit_block():
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    if connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall():
        raise RuntimeError("0009 migration left invalid foreign key references.")


def downgrade() -> None:
    raise RuntimeError("0009 downgrade is unsupported; restore the pre-upgrade SQLite backup.")
