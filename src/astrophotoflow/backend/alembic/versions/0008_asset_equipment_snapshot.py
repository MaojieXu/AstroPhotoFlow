"""Keep material equipment facts independent from the live equipment registry."""
import json

from alembic import op
import sqlalchemy as sa


revision = "0008_asset_equipment_snapshot"
down_revision = "0007_setups_and_calibration"
branch_labels = None
depends_on = None


def _json(value):
    if isinstance(value, dict):
        return value
    if value:
        return json.loads(value)
    return {}


def upgrade() -> None:
    op.add_column("asset", sa.Column("equipment_snapshot", sa.JSON(), nullable=False, server_default="{}"))
    connection = op.get_bind()
    equipment = {
        row.id: {"id": row.id, "kind": row.kind, "name": row.name, "model": row.model,
                 "serial_number": row.serial_number, "specs": _json(row.specs), "notes": row.notes}
        for row in connection.execute(sa.text(
            "SELECT id, kind, name, model, serial_number, specs, notes FROM equipment"
        )).mappings()
    }
    for row in connection.execute(sa.text("SELECT id, parameters FROM asset")).mappings():
        parameters = _json(row.parameters)
        snapshot = {
            key: equipment[parameters[key]]
            for key in ("camera_id", "optical_system_id", "filter_id")
            if parameters.get(key) in equipment
        }
        connection.execute(sa.text("UPDATE asset SET equipment_snapshot=:snapshot WHERE id=:id"),
                           {"snapshot": json.dumps(snapshot, separators=(",", ":")), "id": row.id})
    for row in connection.execute(sa.text(
        "SELECT id, camera_id, optical_system_id, filter_id, capture_snapshot FROM asset_version"
    )).mappings():
        snapshot = _json(row.capture_snapshot)
        snapshot["equipment_snapshot"] = {
            key: equipment[value]
            for key, value in (("camera_id", row.camera_id), ("optical_system_id", row.optical_system_id), ("filter_id", row.filter_id))
            if value in equipment
        }
        connection.execute(sa.text("UPDATE asset_version SET capture_snapshot=:snapshot WHERE id=:id"),
                           {"snapshot": json.dumps(snapshot, separators=(",", ":")), "id": row.id})


def downgrade() -> None:
    raise RuntimeError("0008 downgrade is unsupported; restore the pre-upgrade SQLite backup.")
