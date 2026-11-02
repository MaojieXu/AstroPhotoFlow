from astrophotoflow.contracts.metadata import AssetParametersPatch

"""Owned member choices distinguish inheritance, disabling and exact selection."""

from contextlib import closing
from copy import deepcopy
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.exc import IntegrityError

from astrophotoflow.contracts.equipment import TelescopeCreate
from astrophotoflow.contracts.setups import CapturePresetCreate, CapturePresetPatch, EquipmentSetupCreate, EquipmentSetupPatch
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.database.schema import upgrade_database
from astrophotoflow.core.errors import ApiError
from astrophotoflow.interfaces.http.app import create_app
from astrophotoflow.modules.data.equipment.models import CapturePresetSelection
from astrophotoflow.modules.data.equipment.snapshots import capture_defaults_snapshot
from astrophotoflow.modules.data.equipment.references import validate_import_equipment
from astrophotoflow.modules.data.imports.metadata import current_asset_parameters
from astrophotoflow.modules.data.public import (
    create_capture_preset,
    create_equipment,
    create_setup,
    get_capture_preset,
    update_capture_preset,
    update_setup,
)


@pytest.fixture
def database(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path / "data", (), workspace=tmp_path)
    upgrade_database(settings)
    with closing(Database(settings.database_path)) as database:
        yield database


def rig(session):
    return create_setup(session, EquipmentSetupCreate(name="rig", components=[
        {"source": "inline", "equipment": {"kind": "camera", "name": "inline camera"}},
        {"source": "inline", "equipment": {"kind": "filter", "name": "Ha"}},
        {"source": "inline", "equipment": {"kind": "filter", "name": "OIII"}},
    ]))


def test_member_choice_disable_and_restore_inheritance_preserve_zero(database):
    with database.write_session() as session:
        setup = rig(session)
        preset = create_capture_preset(session, setup.id, CapturePresetCreate(parameters={"parameter_mode": "gain", "gain": 0, "offset": 0},
                                                                             equipment_selection={"filter": setup.components[2].id}))
        frozen = capture_defaults_snapshot(session, preset.id, AssetParametersPatch()).model_dump(mode="json", exclude_unset=True)
        assert frozen["selected_equipment"]["filter_id"]["name"] == "OIII"
        assert frozen["selected_equipment"]["camera_id"]["name"] == "inline camera"
        assert frozen["parameters"]["gain"] == frozen["parameters"]["offset"] == 0
        assert frozen["parameters"]["camera_id"] is None
    with database.write_session() as session:
        disabled = update_capture_preset(session, preset.id, CapturePresetPatch(base_revision=1, equipment_selection={"filter": None}))
        assert disabled.equipment_selection.model_dump(exclude_unset=True) == {"filter": None}
        frozen = capture_defaults_snapshot(session, preset.id, AssetParametersPatch()).model_dump(mode="json", exclude_unset=True)
        assert frozen["selected_equipment"]["camera_id"]["name"] == "inline camera"
        assert frozen["parameters"]["camera_id"] is None
        assert "filter_id" not in frozen["selected_equipment"]
    with database.write_session() as session:
        inherited = update_capture_preset(session, preset.id, CapturePresetPatch(base_revision=2, equipment_selection={}))
        assert inherited.equipment_selection.model_dump(exclude_unset=True) == {}
        assert capture_defaults_snapshot(session, preset.id, AssetParametersPatch()).model_dump(mode="json", exclude_unset=True)["selected_equipment"]["camera_id"]["name"] == "inline camera"


def test_member_removal_clears_current_choice_but_not_frozen_input(database):
    with database.write_session() as session:
        setup = rig(session)
        preset = create_capture_preset(session, setup.id, CapturePresetCreate(equipment_selection={"filter": setup.components[2].id}))
        frozen = deepcopy(capture_defaults_snapshot(session, preset.id, AssetParametersPatch()).model_dump(mode="json", exclude_unset=True))
    with database.write_session() as session:
        update_setup(session, setup.id, EquipmentSetupPatch(base_revision=1, components=setup.components[:2]))
        current = get_capture_preset(session, preset.id)
        assert current.revision == 2
        assert current.equipment_selection.model_dump(exclude_unset=True) == {"filter": None}
        assert "filter_id" not in capture_defaults_snapshot(session, preset.id, AssetParametersPatch()).model_dump(mode="json", exclude_unset=True)["selected_equipment"]
    assert frozen["selected_equipment"]["filter_id"]["name"] == "OIII"
    assert frozen["selected_members"]["filter"] == str(setup.components[2].id)


def test_wrong_kind_and_foreign_setup_member_are_rejected(database):
    with database.write_session() as session:
        setup, other = rig(session), rig(session)
    for identity in (setup.components[0].id, other.components[1].id):
        with pytest.raises(ApiError) as error, database.write_session() as session:
            create_capture_preset(session, setup.id, CapturePresetCreate(equipment_selection={"filter": identity}))
        assert error.value.code == "INVALID_REFERENCE"


def test_database_rejects_a_selection_outside_the_presets_setup(database):
    with database.write_session() as session:
        setup, other = rig(session), rig(session)
        preset = create_capture_preset(session, setup.id, CapturePresetCreate())
    with pytest.raises(IntegrityError), database.write_session() as session:
        session.add(CapturePresetSelection(preset_id=str(preset.id), setup_id=str(setup.id), kind="filter",
                                           member_id=str(other.components[1].id)))
        session.flush()


def test_registered_telescope_uses_the_same_optics_slot_as_inline_optics(database):
    with database.write_session() as session:
        telescope = create_equipment(session, TelescopeCreate(kind="telescope", name="scope"))
        setup = create_setup(session, EquipmentSetupCreate(name="rig", components=[
            {"source": "registered", "equipment_id": telescope.id},
        ]))
        preset = create_capture_preset(session, setup.id, CapturePresetCreate())
        frozen = capture_defaults_snapshot(session, preset.id, AssetParametersPatch()).model_dump(mode="json", exclude_unset=True)
        assert frozen["parameters"]["optical_system_id"] == str(telescope.id)
        validate_import_equipment(session, frozen["parameters"])


def test_manual_null_clears_observed_value_and_preserves_other_defaults():
    values, sources = current_asset_parameters({"gain": None}, {"gain": 123}, {"gain": 0, "offset": 0})
    assert values["gain"] is None and sources["gain"] == "manual"
    assert values["offset"] == 0 and sources["offset"] == "preset"


def test_deleting_a_setup_removes_owned_presets_and_selections(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path / "data", (), workspace=tmp_path)
    upgrade_database(settings)
    with TestClient(create_app(settings, "delete-test"), headers={"Authorization": "Bearer delete-test"}) as client:
        setup = client.post("/api/v1/equipment-setups", json={"name": "rig", "components": [
            {"source": "inline", "equipment": {"kind": "filter", "name": "Ha"}},
        ]}).json()
        preset = client.post(f"/api/v1/equipment-setups/{setup['id']}/presets", json={'equipment_selection': {'filter': setup['components'][0]['id']}}).json()
        selection = {"items": [{"entry_type": "equipment_setup", "id": setup["id"], "revision": 1}]}
        preview = client.post("/api/v1/equipment-management/delete-preview", json=selection).json()
        result = client.post("/api/v1/equipment-management/delete", json={**selection, "preview_fingerprint": preview["preview_fingerprint"]})
        assert result.status_code == 200, result.text
        assert result.json()["deleted_count"] == 2
        assert client.get(f"/api/v1/capture-presets/{preset['id']}").status_code == 404
        assert client.get(f"/api/v1/equipment-setups/{setup['id']}").status_code == 404


def test_inline_equipment_is_frozen_before_upload_and_never_registered(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path / "data", (), workspace=tmp_path)
    upgrade_database(settings)
    app = create_app(settings, "preset-test")
    with TestClient(app, headers={"Authorization": "Bearer preset-test"}) as client:
        setup = client.post("/api/v1/equipment-setups", json={"name": "rig", "components": [
            {"source": "inline", "equipment": {"kind": "camera", "name": "accepted camera"}},
            {"source": "inline", "equipment": {"kind": "filter", "name": "Ha"}},
            {"source": "inline", "equipment": {"kind": "filter", "name": "OIII"}},
        ]}).json()
        preset = client.post(f"/api/v1/equipment-setups/{setup['id']}/presets", json={'equipment_selection': {'filter': setup['components'][2]['id']}, 'parameters': {'parameter_mode': 'gain', 'gain': 0}}).json()
        image = BytesIO()
        Image.new("RGB", (8, 8), "blue").save(image, format="PNG")
        content = image.getvalue()
        accepted = client.post("/api/v1/uploads", json={"files": [{"name": "frame.png", "size": len(content)}],
                                                         "capture_preset_id": preset["id"]})
        assert accepted.status_code == 202, accepted.text
        task_id = accepted.json()["task_id"]
        setup["components"][0]["equipment"]["name"] = "changed later"
        assert client.patch(f"/api/v1/equipment-setups/{setup['id']}", json={"base_revision": 1, "components": [{key: value for key, value in component.items() if key != "effective_focal_length_mm"} for component in setup["components"]]}).status_code == 200
        assert client.put(f"/api/v1/uploads/{task_id}/0", content=content).status_code == 200
        assert client.post(f"/api/v1/uploads/{task_id}/start").status_code == 202
        task = client.get(f"/api/v1/asset-tasks/{task_id}").json()
        assert task["status"] == "completed", task
        asset = client.get(f"/api/v1/library/assets/{task['items'][0]['asset_id']}").json()
        assert asset["parameters"]["camera_id"] is None
        assert asset["equipment_snapshot"]["camera_id"]["name"] == "accepted camera"
        assert asset["equipment_snapshot"]["filter_id"]["name"] == "OIII"
        assert client.get("/api/v1/equipment").json()["total"] == 0
