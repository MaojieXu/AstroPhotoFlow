import json
import sqlite3
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from pydantic import TypeAdapter
from sqlalchemy import select

from astrophotoflow.contracts.calibration import CalibrationBindings
from astrophotoflow.contracts.metadata import AssetParametersPatch
from astrophotoflow.contracts.setups import EquipmentSetupCreate
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.database.schema import SCHEMA_REVISION, upgrade_database
from astrophotoflow.interfaces.http.app import create_app
from astrophotoflow.modules.data.equipment.models import CapturePreset, Equipment
from astrophotoflow.modules.data.equipment.snapshots import capture_defaults_snapshot
from astrophotoflow.modules.data.imports.models import AssetTask
from astrophotoflow.modules.data.public import create_setup


def test_fresh_baseline_contains_member_relations_without_legacy_profiles(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path, (), workspace=tmp_path)
    upgrade_database(settings)
    with sqlite3.connect(settings.database_path) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "equipment_setup_member" in tables
        assert "capture_profile" not in tables
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == SCHEMA_REVISION
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_import_snapshot_freezes_registered_and_inline_components(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path, (), workspace=tmp_path)
    upgrade_database(settings)
    database = Database(settings.database_path)
    camera, setup, preset = (str(uuid4()) for _ in range(3))
    components = EquipmentSetupCreate.model_validate({
        "name": "night rig", "components": [
            {"source": "registered", "equipment_id": camera},
            {"source": "inline", "equipment": {"kind": "telescope", "name": "hand-filled scope",
                                                   "specs": {"native_focal_length_mm": 400}}},
        ],
    }).model_dump(mode="json")["components"]
    with database.write_session() as session:
        session.add(Equipment(id=camera, kind="camera", name="camera", specs={"cfa_pattern": "RGGB"}, status="active", revision=1))
        session.flush()
        setup = str(create_setup(session, EquipmentSetupCreate.model_validate({"name": "night rig", "components": components})).id)
        session.flush()
        session.add(CapturePreset(id=preset, equipment_setup_id=setup, name="light 30s",
                                  parameters={"parameter_mode": "gain", "gain": 0, "exposure_seconds": 30}, status="active", revision=1))
    with database.read_session() as session:
        snapshot = capture_defaults_snapshot(session, UUID(preset), AssetParametersPatch()).model_dump(mode="json", exclude_unset=True)
        assert {key: snapshot["parameters"][key] for key in ("gain", "exposure_seconds", "camera_id")} == {"gain": 0, "exposure_seconds": 30, "camera_id": camera}
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
