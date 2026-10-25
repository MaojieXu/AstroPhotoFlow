import json
import sqlite3
from uuid import UUID, uuid4

from alembic import command
from pydantic import TypeAdapter
from sqlalchemy import select
from fastapi.testclient import TestClient

from astrophotoflow.backend.api import create_app
from astrophotoflow.backend.db import Database
from astrophotoflow.backend.models import AssetTask, CapturePreset, Equipment, EquipmentSetup
from astrophotoflow.backend.presets import capture_defaults_snapshot
from astrophotoflow.backend.schema import SCHEMA_REVISION, _alembic_config, upgrade_database
from astrophotoflow.backend.schemas import CalibrationBindings
from astrophotoflow.backend.setup_schemas import EquipmentSetupCreate
from astrophotoflow.config import Settings


def test_shared_migration_preserves_existing_camera_dependants(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path, ())
    command.upgrade(_alembic_config(settings), "0006_library_trash_cleanup_state")
    camera, profile = str(uuid4()), str(uuid4())
    with sqlite3.connect(settings.database_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("INSERT INTO equipment (id,kind,name,specs,status,revision) VALUES (?,?,?,?,?,?)",
                           (camera, "camera", "original camera", "{}", "active", 1))
        connection.execute("INSERT INTO capture_profile (id,name,camera_id,frame_type,status,revision) VALUES (?,?,?,?,?,?)",
                           (profile, "original preset", camera, "dark", "active", 1))
        before = connection.execute("SELECT * FROM capture_profile").fetchall()
    assert upgrade_database(settings) is not None
    with sqlite3.connect(settings.database_path) as connection:
        assert connection.execute("SELECT * FROM capture_profile").fetchall() == before
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == SCHEMA_REVISION
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        connection.execute("INSERT INTO equipment (id,kind,name,specs,status,revision) VALUES (?,?,?,?,?,?)",
                           (str(uuid4()), "mount", "new mount", "{}", "active", 1))


def test_import_snapshot_freezes_registered_and_inline_components(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path, ())
    upgrade_database(settings)
    database = Database(settings.database_path)
    camera, setup, preset = (str(uuid4()) for _ in range(3))
    components = EquipmentSetupCreate.model_validate({
        "name": "night rig", "components": [
            {"source": "registered", "equipment_id": camera},
            {"source": "inline", "equipment": {"kind": "telescope", "name": "hand-filled scope",
                                                   "specs": {"aperture_mm": 80}}},
        ],
    }).model_dump(mode="json")["components"]
    with database.write_session() as session:
        session.add(Equipment(id=camera, kind="camera", name="camera", specs={"cfa_pattern": "RGGB"}, status="active", revision=1))
        session.add(EquipmentSetup(id=setup, name="night rig", components=components, status="active", revision=1))
        session.flush()
        session.add(CapturePreset(id=preset, equipment_setup_id=setup, name="light 30s", classification={"frame_type": "light"},
                                  parameters={"gain": 0, "exposure_seconds": 30, "camera_id": None}, status="active", revision=1))
    with database.read_session() as session:
        snapshot = capture_defaults_snapshot(session, UUID(preset))
        assert snapshot["parameters"] == {"gain": 0, "exposure_seconds": 30, "camera_id": camera}
        assert len(session.scalars(select(Equipment)).all()) == 1
    app = create_app(settings, "test-token")
    with TestClient(app) as client:
        response = client.post("/api/v1/uploads", headers={"Authorization": "Bearer test-token"}, json={
            "files": [{"name": "light.fits", "size": 100}], "capture_preset_id": preset,
        })
        assert response.status_code == 202, response.text
        task_id = response.json()["task_id"]
    with database.read_session() as session:
        assert session.get(AssetTask, task_id).import_defaults_snapshot == snapshot
    app.state.database.close()
    frozen = json.dumps(snapshot, sort_keys=True)
    with database.write_session() as session:
        session.get(Equipment, camera).name = "changed camera"
        session.get(CapturePreset, preset).parameters = {"exposure_seconds": 60}
    assert json.dumps(snapshot, sort_keys=True) == frozen
    assert snapshot["equipment_setup"]["components"][0]["equipment"]["name"] == "camera"
    assert snapshot["equipment_setup"]["components"][1]["equipment"]["name"] == "hand-filled scope"
    database.close()


def test_calibration_contract_preserves_inherit_none_and_version_target():
    adapter = TypeAdapter(CalibrationBindings)
    version_id = str(uuid4())
    parsed = adapter.validate_python({"bias": None, "flat": {"kind": "dataset_version", "id": version_id}})
    assert adapter.dump_python(parsed, mode="json") == {
        "bias": None, "flat": {"kind": "dataset_version", "id": version_id},
    }
    assert "dark" not in parsed
