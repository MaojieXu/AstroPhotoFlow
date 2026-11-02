"""New preset boundaries preserve hardware identity and explicit non-use."""

from contextlib import closing
from copy import deepcopy

import pytest
from pydantic import ValidationError

from astrophotoflow.contracts.equipment import CameraCreate, TelescopeCreate
from astrophotoflow.contracts.metadata import AssetParametersPatch
from astrophotoflow.contracts.setups import CapturePresetCreate, CapturePresetPatch, EquipmentSetupCreate, EquipmentSetupPatch
from astrophotoflow.contracts.snapshots import ImportDefaultsSnapshot
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.database.schema import upgrade_database
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.equipment.presets import create_capture_preset, get_capture_preset, update_capture_preset
from astrophotoflow.modules.data.equipment.service import create_equipment
from astrophotoflow.modules.data.equipment.setups import create_setup, get_setup, update_setup
from astrophotoflow.modules.data.equipment.snapshots import capture_defaults_snapshot


@pytest.fixture
def database(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path / "data", (), workspace=tmp_path)
    upgrade_database(settings)
    with closing(Database(settings.database_path)) as database:
        yield database


def rig(session):
    return create_setup(session, EquipmentSetupCreate(name="Rig", components=[
        {"source": "inline", "equipment": {"kind": "camera", "name": "Camera"}},
        {"source": "inline", "equipment": {"kind": "telescope", "name": "Scope"}},
        {"source": "inline", "equipment": {"kind": "filter", "name": "R"}},
        {"source": "inline", "equipment": {"kind": "filter", "name": "G"}},
    ]))


@pytest.mark.parametrize("kind", ["camera", "telescope"])
def test_registered_and_inline_counts_share_one_limit_and_rollback(database, kind):
    with database.write_session() as session:
        equipment = create_equipment(session, CameraCreate(kind="camera", name="Registered") if kind == "camera" else TelescopeCreate(kind="telescope", name="Registered"))
        setup = rig(session)
    components = [item.model_dump(mode="json", exclude={"effective_focal_length_mm"}) for item in setup.components]
    components.append({"source": "registered", "equipment_id": equipment.id})
    with pytest.raises(ApiError), database.write_session() as session:
        update_setup(session, setup.id, EquipmentSetupPatch(base_revision=1, name="Must rollback", components=components))
    with database.read_session() as session:
        current = get_setup(session, setup.id)
        assert current.revision == 1 and current.name == "Rig"
        assert len(current.components) == 4


@pytest.mark.parametrize("retired", [{"name": "manual"}, {"classification": {}}, {"notes": "old"},
                                     {"optical_accessory_selection": None}, {"equipment_selection": {"camera": None}},
                                     {"equipment_selection": {"optical_system": None}}, {"parameters": {"cfa_pattern": "MONO"}}])
def test_new_preset_contract_rejects_retired_inputs(retired):
    with pytest.raises(ValidationError):
        CapturePresetCreate.model_validate(retired)


def test_modes_keep_draft_values_but_freeze_only_active_parameters(database):
    with database.write_session() as session:
        setup = rig(session)
        preset = create_capture_preset(session, setup.id, CapturePresetCreate(parameters={
            "parameter_mode": "gain", "iso": 800, "gain": 0, "offset": 0, "exposure_seconds": 60, "sensor_temperature_c": 0}))
        assert preset.parameters.iso == 800
        assert "Gain 0" in preset.name and "Offset 0" in preset.name and "ISO" not in preset.name
        frozen = capture_defaults_snapshot(session, preset.id, AssetParametersPatch())
        assert frozen.parameters.gain == frozen.parameters.offset == 0
        assert "iso" not in frozen.parameters.model_fields_set
        standard = update_capture_preset(session, preset.id, CapturePresetPatch(base_revision=1, parameters={"parameter_mode": "standard"}))
        assert standard.parameters.gain == standard.parameters.offset == 0
        current = capture_defaults_snapshot(session, preset.id, AssetParametersPatch())
        assert current.parameters.parameter_mode == "standard"
        assert not {"iso", "gain", "offset"} & current.parameters.model_fields_set
        update_capture_preset(session, preset.id, CapturePresetPatch(base_revision=2, parameters={"parameter_mode": "iso"}))
        iso = capture_defaults_snapshot(session, preset.id, AssetParametersPatch())
        assert iso.parameters.iso == 800 and "gain" not in iso.parameters.model_fields_set


def test_removing_inherited_effective_filter_explicitly_disables_without_changing_history(database):
    with database.write_session() as session:
        setup = rig(session)
        preset = create_capture_preset(session, setup.id, CapturePresetCreate())
        history = deepcopy(capture_defaults_snapshot(session, preset.id, AssetParametersPatch()).model_dump(mode="json", exclude_unset=True))
        assert history["selected_equipment"]["filter_id"]["name"] == "R"
    components = [item.model_dump(mode="json", exclude={"effective_focal_length_mm"}) for index,item in enumerate(setup.components) if index != 2]
    with database.write_session() as session:
        update_setup(session, setup.id, EquipmentSetupPatch(base_revision=1, components=components))
        preset = get_capture_preset(session, preset.id)
        assert preset.equipment_selection.model_dump(exclude_unset=True) == {"filter": None}
        assert "filter_id" not in capture_defaults_snapshot(session, preset.id, AssetParametersPatch()).selected_equipment.model_fields_set
    assert history["selected_equipment"]["filter_id"]["name"] == "R"
    assert ImportDefaultsSnapshot.model_validate(history).model_dump(mode="json", exclude_unset=True) == history


def test_old_selected_member_and_accessory_facts_still_parse():
    from uuid import uuid4
    ids = [str(uuid4()) for _ in range(3)]
    original = {"selected_members": {"camera": ids[0], "optical_system": ids[1], "filter": ids[2]},
                "capture_preset": {"id": str(uuid4()), "revision": 1, "name": "Old",
                                   "optical_accessory_selection": {"accessory_id": None}},
                "parameters": {"cfa_pattern": "RGGB", "binning_x": 2, "offset": 0}}
    assert ImportDefaultsSnapshot.model_validate(original).model_dump(mode="json", exclude_unset=True) == original


def test_explicit_cleanup_preserves_rows_history_and_blocks_real_overrides(database, tmp_path):
    import sqlite3

    from scripts.simplify_capture_presets import simplify
    with database.write_session() as session:
        setup = rig(session)
        preset = create_capture_preset(session, setup.id, CapturePresetCreate(parameters={"parameter_mode": "gain", "offset": 0}))
    path = tmp_path / "copy.sqlite3"
    with sqlite3.connect(database.path) as source, sqlite3.connect(path) as target:
        source.backup(target)
        target.execute("ALTER TABLE capture_preset ADD COLUMN classification JSON DEFAULT '{}'")
        target.execute("ALTER TABLE capture_preset ADD COLUMN notes TEXT")
        target.execute("ALTER TABLE capture_preset ADD COLUMN optical_accessory_selection JSON")
        target.execute("UPDATE capture_preset SET notes='A real prior note'")
    blocked = simplify(path, apply=True)
    assert blocked["state"] == "blocked"
    assert any(item.get("field") == "notes" for item in blocked["conflicts"])
    with sqlite3.connect(path) as target:
        assert target.execute("SELECT notes FROM capture_preset").fetchone()[0] == "A real prior note"
        target.execute("UPDATE capture_preset SET notes=NULL")
    result = simplify(path, apply=True)
    assert result["unchanged_data_verified"] and result["before"] == result["after"]
    with sqlite3.connect(path) as target:
        assert target.execute("SELECT id,equipment_setup_id FROM capture_preset").fetchone() == (str(preset.id),str(setup.id))
        assert target.execute("PRAGMA foreign_key_check").fetchall() == []
