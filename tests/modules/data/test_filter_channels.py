"""Filter channels are explicit metadata, not a replacement for filter identity."""

from contextlib import closing

from astrophotoflow.contracts.equipment import FilterCreate, FilterPatch, FilterSnapshot, FilterSpecs
from astrophotoflow.contracts.metadata import AssetParametersPatch
from astrophotoflow.contracts.setups import EquipmentSetupCreate, EquipmentSetupQuery
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.database.schema import initialize_database
from astrophotoflow.modules.data.equipment.queries import list_setups
from astrophotoflow.modules.data.equipment.service import create_equipment, update_equipment
from astrophotoflow.modules.data.equipment.setups import create_setup
from astrophotoflow.modules.data.equipment.snapshots import capture_defaults_snapshot


def test_free_text_channel_and_unknown_legacy_snapshot():
    assert FilterSpecs(channel="  Ha + OIII  ").channel == "Ha + OIII"
    assert FilterSpecs(channel="   ").channel is None
    legacy = FilterSnapshot(kind="filter", name="Ha 7nm", specs={"bandwidth_nm": 7})
    assert legacy.specs.channel is None
    assert "channel" not in legacy.model_dump(mode="json", exclude_unset=True)["specs"]


def test_selected_filter_channel_is_frozen_without_renaming_the_filter(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path / "data", (), workspace=tmp_path)
    initialize_database(settings)
    with closing(Database(settings.database_path)) as database, database.write_session() as session:
        device = create_equipment(session, FilterCreate(kind="filter", name="L-Pro", specs={"channel": "RGB"}))
        setup = create_setup(session, EquipmentSetupCreate(name="Rig", components=[
            {"source": "registered", "equipment_id": device.id},
        ]))
        from astrophotoflow.contracts.image_management import EquipmentApplication
        application = EquipmentApplication(choice={"source": "setup", "setup_id": setup.id, "expected_revision": 1}, fields=["filter"])
        frozen = capture_defaults_snapshot(session, AssetParametersPatch(), application).model_dump(mode="json")
        changed = update_equipment(session, device.id, FilterPatch(
            kind="filter", base_revision=1, specs={"channel": "Custom", "bandwidth_nm": 7}))
        assert changed.id == device.id and changed.name == "L-Pro"
        assert frozen["selected_equipment"]["filter_id"]["specs"]["channel"] == "RGB"
        assert frozen["selected_equipment"]["filter_id"]["name"] == "L-Pro"
        cleared = update_equipment(session, device.id, FilterPatch(kind="filter", base_revision=2, specs={"channel": None}))
        assert cleared.specs.channel is None and cleared.specs.bandwidth_nm == 7


def test_filter_sort_uses_channel_then_numeric_bandwidth_for_both_sources(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path / "data", (), workspace=tmp_path)
    initialize_database(settings)
    with closing(Database(settings.database_path)) as database, database.write_session() as session:
        for bandwidth in (12, 7, 3):
            body = {"kind": "filter", "name": "Same physical label", "specs": {"channel": "Ha", "bandwidth_nm": bandwidth}}
            component = {"source": "inline", "equipment": body}
            if bandwidth == 7:
                device = create_equipment(session, FilterCreate(**body))
                component = {"source": "registered", "equipment_id": device.id}
            create_setup(session, EquipmentSetupCreate(name=f"width-{bandwidth}", components=[component]))
        create_setup(session, EquipmentSetupCreate(name="unknown", components=[
            {"source": "inline", "equipment": {"kind": "filter", "name": "L-Pro"}},
        ]))
        assert [item.name for item in list_setups(session, EquipmentSetupQuery(sort_by="filter", order="asc")).items] == [
            "width-3", "width-7", "width-12", "unknown"]
        assert [item.name for item in list_setups(session, EquipmentSetupQuery(sort_by="filter", order="desc")).items] == [
            "width-12", "width-7", "width-3", "unknown"]
