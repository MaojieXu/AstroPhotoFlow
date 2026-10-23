"""Preserve current asset facts and track removed library entries."""
import json

from alembic import op
import sqlalchemy as sa


revision = "0004_library_entry_removal_and_asset_facts"
down_revision = "0003_capture_profile_gain_mode"
branch_labels = None
depends_on = None


PARAMETER_KEYS = {
    "camera_id", "optical_system_id", "filter_id", "parameter_mode", "iso", "gain", "offset",
    "exposure_seconds", "integration_seconds", "sensor_temperature_c", "binning_x", "binning_y", "cfa_pattern",
}


def _json(value, default):
    if value is None:
        return default
    return json.loads(value) if isinstance(value, str) else value


def upgrade() -> None:
    op.create_table(
        "library_entry_removal",
        sa.Column("entry_type", sa.String(16), primary_key=True),
        sa.Column("entry_id", sa.String(36), primary_key=True),
        sa.Column("removed_at", sa.DateTime(timezone=True), server_default=sa.func.current_timestamp(), nullable=False),
        sa.CheckConstraint("entry_type IN ('asset', 'dataset')", name="ck_library_entry_removal_type"),
    )

    connection = op.get_bind()
    rows = connection.execute(sa.text(
        "SELECT a.id, a.role, a.classification, a.parameters, a.value_sources, "
        "v.frame_type, v.calibration_level, v.camera_id, v.optical_system_id, v.filter_id, v.capture_snapshot "
        "FROM asset AS a JOIN asset_version AS v "
        "ON v.id = a.current_version_id AND v.asset_id = a.id"
    )).mappings()
    for row in rows:
        classification = _json(row["classification"], None)
        parameters = _json(row["parameters"], {})
        sources = _json(row["value_sources"], {})
        snapshot = _json(row["capture_snapshot"], {})
        changed = False

        facts = {
            "camera_id": row["camera_id"],
            "optical_system_id": row["optical_system_id"],
            "filter_id": row["filter_id"],
            **{key: snapshot[key] for key in PARAMETER_KEYS if key in snapshot},
        }
        for key, value in facts.items():
            if value is not None and key not in parameters and sources.get(key) != "manual":
                parameters[key] = value
                sources[key] = "file"
                changed = True

        classification_facts = {"frame_type": row["frame_type"]}
        if row["role"] == "calibration":
            if row["calibration_level"] == "master":
                classification_facts["frame_class"] = "masterframe"
            elif row["calibration_level"] == "individual":
                classification_facts["frame_class"] = "subframe"
        for key, value in classification_facts.items():
            if value is not None and (classification is None or key not in classification) and sources.get("classification." + key) != "manual":
                if classification is None:
                    classification = {}
                classification[key] = value
                sources["classification." + key] = "file"
                changed = True

        if changed:
            connection.execute(sa.text(
                "UPDATE asset SET classification = :classification, parameters = :parameters, value_sources = :value_sources WHERE id = :id"
            ), {
                "id": row["id"],
                "classification": json.dumps(classification, separators=(",", ":")) if classification is not None else None,
                "parameters": json.dumps(parameters, separators=(",", ":")),
                "value_sources": json.dumps(sources, separators=(",", ":")),
            })


def downgrade() -> None:
    op.drop_table("library_entry_removal")
