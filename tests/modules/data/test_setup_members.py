"""Member identity and source constraints survive editing and reordering."""

from contextlib import closing
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from astrophotoflow.contracts.equipment import CameraCreate
from astrophotoflow.contracts.setups import EquipmentSetupCreate, EquipmentSetupPatch
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.database.schema import upgrade_database
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.equipment.models import EquipmentSetupMember
from astrophotoflow.modules.data.public import create_equipment, create_setup, get_setup, update_setup


@pytest.fixture
def database(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path / "data", (), workspace=tmp_path)
    upgrade_database(settings)
    with closing(Database(settings.database_path)) as database:
        yield database


def test_reordering_and_editing_preserve_setup_member_ids(database):
    with database.write_session() as session:
        camera = create_equipment(session, CameraCreate(kind="camera", name="camera"))
        setup = create_setup(session, EquipmentSetupCreate(name="rig", components=[
            {"source": "registered", "equipment_id": camera.id},
            {"source": "inline", "equipment": {"kind": "filter", "name": "Ha"}},
        ]))
    identities = [member.id for member in setup.components]
    components = [member.model_dump(mode="json", exclude={"effective_focal_length_mm"}) for member in reversed(setup.components)]
    components[0]["equipment"]["name"] = "OIII"
    with database.write_session() as session:
        changed = update_setup(session, setup.id, EquipmentSetupPatch(base_revision=1, components=components))
        assert [member.id for member in changed.components] == list(reversed(identities))
        assert changed.components[0].equipment.name == "OIII"
    with database.read_session() as session:
        rows = session.scalars(select(EquipmentSetupMember).where(EquipmentSetupMember.setup_id == str(setup.id))
                               .order_by(EquipmentSetupMember.position)).all()
        assert [(UUID(row.id), row.position) for row in rows] == [(identities[1], 0), (identities[0], 1)]


def test_member_id_from_another_setup_is_rejected_and_revision_rolls_back(database):
    with database.write_session() as session:
        first = create_setup(session, EquipmentSetupCreate(name="first", components=[
            {"source": "inline", "equipment": {"kind": "filter", "name": "Ha"}},
        ]))
        second = create_setup(session, EquipmentSetupCreate(name="second"))
    with pytest.raises(ApiError) as error, database.write_session() as session:
        update_setup(session, second.id, EquipmentSetupPatch(base_revision=1, components=first.components))
    assert error.value.code == "INVALID_REFERENCE"
    with database.read_session() as session:
        assert get_setup(session, second.id).revision == 1


@pytest.mark.parametrize("both", [False, True])
def test_database_rejects_ambiguous_or_absent_member_sources(database, both):
    with database.write_session() as session:
        camera = create_equipment(session, CameraCreate(kind="camera", name="camera"))
        setup = create_setup(session, EquipmentSetupCreate(name="rig"))
    with pytest.raises(IntegrityError), database.write_session() as session:
        session.add(EquipmentSetupMember(id=str(uuid4()), setup_id=str(setup.id), position=0,
                                        equipment_id=str(camera.id) if both else None,
                                        inline_equipment={"kind": "filter", "name": "Ha"} if both else None))
        session.flush()


def test_member_name_sort_uses_unicode_casefold_and_stable_setup_identity(database):
    from astrophotoflow.contracts.setups import EquipmentSetupQuery
    from astrophotoflow.modules.data.equipment.models import Equipment, EquipmentSetup, EquipmentSetupMember
    from astrophotoflow.modules.data.equipment.queries import list_setups

    camera_a, camera_b, setup_a, setup_b = [str(uuid4()) for _ in range(4)]
    with database.write_session() as session:
        session.add_all([Equipment(id=camera_a, kind="camera", name="Straße", specs={}),
                         Equipment(id=camera_b, kind="camera", name="STRASSE", specs={})]); session.flush()
        session.add_all([EquipmentSetup(id=setup_a, name="A rig"), EquipmentSetup(id=setup_b, name="B rig")]); session.flush()
        session.add_all([EquipmentSetupMember(id=str(uuid4()), setup_id=setup_a, position=0, equipment_id=camera_a),
                         EquipmentSetupMember(id=str(uuid4()), setup_id=setup_b, position=0, equipment_id=camera_b)])
    for order in ("asc", "desc"):
        with database.read_session() as session:
            page = list_setups(session, EquipmentSetupQuery(sort_by="camera", order=order))
        assert [str(item.id) for item in page.items] == [setup_a, setup_b]


@pytest.mark.parametrize("order", [
    ("equipment", "equipment_setup"),
    ("equipment_setup", "equipment"),
    ("equipment_setup",),
])
def test_deleting_setup_members_independent_of_selection_order(database, order):
    from astrophotoflow.contracts.trash import EquipmentDelete, EquipmentDeleteSelection
    from astrophotoflow.modules.data.equipment.models import Equipment, EquipmentSetup
    from astrophotoflow.modules.data.trash.management import delete_equipment_entries, preview_equipment_delete

    with database.write_session() as session:
        camera = create_equipment(session, CameraCreate(kind="camera", name="owned camera"))
        setup = create_setup(session, EquipmentSetupCreate(name="owned setup", components=[
            {"source": "registered", "equipment_id": camera.id},
        ]))
    targets = {"equipment": camera, "equipment_setup": setup}
    items = [{"entry_type": kind, "id": targets[kind].id, "revision": targets[kind].revision} for kind in order]
    with database.read_session() as session:
        preview = preview_equipment_delete(EquipmentDeleteSelection(items=items), session)
    with database.write_session() as session:
        result = delete_equipment_entries(EquipmentDelete(items=items, preview_fingerprint=preview.preview_fingerprint), session)
        assert result.deleted_count == (2 if "equipment" in order else 1)
    with database.read_session() as session:
        assert session.get(EquipmentSetup, str(setup.id)) is None
        assert session.scalars(select(EquipmentSetupMember)).all() == []
        assert (session.get(Equipment, str(camera.id)) is None) == ("equipment" in order)
