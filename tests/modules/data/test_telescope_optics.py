"""Telescope-owned accessories, setup selection, and frozen optical facts."""

from contextlib import closing
from copy import deepcopy
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from astrophotoflow.contracts.equipment import EquipmentCreate, OpticalAccessory, TelescopeCreate, TelescopePatch
from astrophotoflow.contracts.metadata import AssetParametersPatch
from astrophotoflow.contracts.setups import EquipmentSetupCreate, EquipmentSetupPatch
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.database.schema import initialize_database
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.equipment.service import create_equipment, get_equipment, update_equipment
from astrophotoflow.modules.data.equipment.setups import create_setup, get_setup, update_setup
from astrophotoflow.modules.data.equipment.snapshots import capture_defaults_snapshot


def freeze_setup(session, setup_id):
    from astrophotoflow.contracts.image_management import EquipmentApplication
    current = get_setup(session, setup_id)
    application = EquipmentApplication(choice={"source": "setup", "setup_id": setup_id, "expected_revision": current.revision},
                                       fields=["telescope", "optical_accessory"] if current.components else ["telescope"])
    return capture_defaults_snapshot(session, AssetParametersPatch(), application).model_dump(mode="json")


@pytest.fixture
def database(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path / "data", (), workspace=tmp_path)
    initialize_database(settings)
    with closing(Database(settings.database_path)) as database:
        yield database


def optical_rig(session):
    telescope = create_equipment(session, TelescopeCreate(kind="telescope", name="scope", specs={
        "native_focal_length_mm": 600,
        "optical_accessories": [{"name": "Reducer", "factor": 0.8}, {"name": "Flattener", "factor": 1.0}],
    }))
    reducer, flattener = telescope.specs.optical_accessories
    setup = create_setup(session, EquipmentSetupCreate(name="rig", components=[{
        "source": "registered", "equipment_id": telescope.id, "optical_accessory_id": reducer.id,
    }]))
    return telescope, setup, reducer, flattener


@pytest.mark.parametrize("factor", [0, -0.8, float("inf"), float("nan")])
def test_accessory_requires_a_finite_positive_factor(factor):
    with pytest.raises(ValidationError):
        OpticalAccessory(name="Reducer", factor=factor)


@pytest.mark.parametrize("kind", ["accessory", "optical_system"])
def test_removed_equipment_kinds_are_rejected(kind):
    with pytest.raises(ValidationError):
        TypeAdapter(EquipmentCreate).validate_python({"kind": kind, "name": "removed"})


def test_imports_freeze_the_setup_accessory_and_follow_explicit_setup_changes(database):
    with database.write_session() as session:
        telescope, setup, reducer, flattener = optical_rig(session)
        def frozen():
            return freeze_setup(session, setup.id)["selected_equipment"]["optical_system_id"]
        assert frozen()["optical_accessory"]["id"] == str(reducer.id)
        component = setup.components[0].model_dump(mode="json", exclude={"effective_focal_length_mm"})
        component["optical_accessory_id"] = None
        update_setup(session, setup.id, EquipmentSetupPatch(base_revision=1, components=[component]))
        assert frozen()["optical_accessory"] is None
        assert frozen()["effective_focal_length_mm"] == 600
        component["optical_accessory_id"] = flattener.id
        update_setup(session, setup.id, EquipmentSetupPatch(base_revision=2, components=[component]))
        assert frozen()["optical_accessory"]["name"] == "Flattener"
        assert frozen()["optical_accessory"]["id"] == str(flattener.id)
        assert get_equipment(session, telescope.id).specs.optical_accessories[0].id == reducer.id


def test_accessory_ids_must_belong_to_the_selected_telescope(database):
    with database.write_session() as session:
        telescope, _setup, reducer, _ = optical_rig(session)
    with pytest.raises(ApiError), database.write_session() as session:
        create_setup(session, EquipmentSetupCreate(name="wrong", components=[{
            "source": "registered", "equipment_id": telescope.id, "optical_accessory_id": uuid4(),
        }]))
    with pytest.raises(ApiError), database.write_session() as session:
        create_setup(session, EquipmentSetupCreate(name="wrong kind", components=[{
            "source": "inline", "equipment": {"kind": "camera", "name": "camera"},
            "optical_accessory_id": reducer.id,
        }]))


def test_removal_of_a_selected_accessory_is_rejected_but_renaming_keeps_frozen_facts(database):
    with database.write_session() as session:
        telescope, setup, reducer, flattener = optical_rig(session)
        component = setup.components[0].model_dump(mode="json", exclude={"effective_focal_length_mm"})
        component["optical_accessory_id"] = flattener.id
        update_setup(session, setup.id, EquipmentSetupPatch(base_revision=1, components=[component]))
        frozen = deepcopy(freeze_setup(session, setup.id))
    for accessories in ([], [reducer.model_dump(mode="json")]):
        with pytest.raises(ApiError), database.write_session() as session:
            update_equipment(session, telescope.id, TelescopePatch(kind="telescope", base_revision=1,
                             specs={"optical_accessories": accessories}))
    with database.write_session() as session:
        changed = flattener.model_copy(update={"name": "Changed", "factor": 2.0})
        update_equipment(session, telescope.id, TelescopePatch(kind="telescope", base_revision=1,
                         specs={"optical_accessories": [reducer, changed]}))
        current = freeze_setup(session, setup.id)
        assert current["selected_equipment"]["optical_system_id"]["effective_focal_length_mm"] == 1200
    assert frozen["selected_equipment"]["optical_system_id"]["optical_accessory"]["name"] == "Flattener"
    assert frozen["selected_equipment"]["optical_system_id"]["effective_focal_length_mm"] == 600


def test_removing_telescope_member_leaves_no_current_override_but_keeps_history(database):
    with database.write_session() as session:
        _, setup, _, flattener = optical_rig(session)
        component = setup.components[0].model_dump(mode="json", exclude={"effective_focal_length_mm"})
        component["optical_accessory_id"] = flattener.id
        update_setup(session, setup.id, EquipmentSetupPatch(base_revision=1, components=[component]))
        frozen = freeze_setup(session, setup.id)
    with database.write_session() as session:
        update_setup(session, setup.id, EquipmentSetupPatch(base_revision=2, components=[]))
        assert get_setup(session, setup.id).components == []
        assert freeze_setup(session, setup.id)["selected_equipment"]["optical_system_id"] is None
    assert frozen["selected_equipment"]["optical_system_id"]["optical_accessory"]["id"] == str(flattener.id)


def test_inline_telescope_uses_member_selection_and_unknown_focal_stays_unknown(database):
    identity = uuid4()
    with database.write_session() as session:
        setup = create_setup(session, EquipmentSetupCreate(name="inline", components=[{
            "source": "inline", "optical_accessory_id": identity, "equipment": {
                "kind": "telescope", "name": "scope", "specs": {
                    "optical_accessories": [{"id": identity, "name": "Reducer", "factor": 0.8}],
                },
            },
        }]))
        assert setup.components[0].effective_focal_length_mm is None
        frozen = freeze_setup(session, setup.id)
        assert frozen["selected_equipment"]["optical_system_id"]["optical_accessory"]["id"] == str(identity)
        assert frozen["selected_equipment"]["optical_system_id"]["effective_focal_length_mm"] is None
