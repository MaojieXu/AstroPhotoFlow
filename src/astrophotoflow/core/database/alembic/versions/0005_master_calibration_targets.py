"""Restrict calibration assignments to fixed Master asset versions."""
import sqlalchemy as sa
from alembic import op

revision = "0005_master_calibration_targets"
down_revision = "0004_remove_capture_presets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    for table in ("dataset_calibration", "member_calibration"):
        if connection.execute(sa.text(f"SELECT 1 FROM {table} WHERE target_dataset_version_id IS NOT NULL LIMIT 1")).first():
            raise RuntimeError("Remove raw calibration-group assignments before upgrading, or rebuild the disposable test workspace.")
    rows = connection.execute(sa.text("SELECT bindings FROM image_calibration_configuration")).scalars()
    import json
    for encoded in rows:
        bindings = json.loads(encoded) if isinstance(encoded, str) else encoded
        if any(value and value.get("kind") == "dataset_version" for value in bindings.values()):
            raise RuntimeError("Remove raw standalone calibration-group assignments before upgrading.")
    for table in ("dataset_calibration", "member_calibration"):
        with op.batch_alter_table(table, recreate="always") as batch:
            batch.drop_index(f"ix_{table}_dataset_target")
            batch.drop_constraint(f"ck_{table}_target", type_="check")
            batch.drop_column("target_dataset_version_id")
            batch.create_check_constraint(f"ck_{table}_target", "(disabled = 1 AND asset_version_id IS NULL) OR (disabled = 0 AND asset_version_id IS NOT NULL)")


def downgrade() -> None:
    raise RuntimeError("Master-only calibration downgrade is unsupported; restore an explicitly selected backup instead.")
