"""Public equipment services preserve caller-owned transactions and revisions."""

from contextlib import closing

import pytest

from astrophotoflow.contracts.equipment import CameraCreate, CameraOut, CameraPatch, CameraSpecs, EquipmentQuery
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.database.schema import upgrade_database
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.public import create_equipment, get_equipment, list_equipment, update_equipment


def test_equipment_service_does_not_commit_the_callers_transaction(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path / "data", (), workspace=tmp_path)
    upgrade_database(settings)
    with closing(Database(settings.database_path)) as database:
        with pytest.raises(RuntimeError, match="rollback"), database.write_session() as session:
            created = create_equipment(session, CameraCreate(kind="camera", name="temporary"))
            assert isinstance(created, CameraOut)
            raise RuntimeError("rollback")
        with database.read_session() as session:
            assert list_equipment(session, EquipmentQuery(status="all")).total == 0


def test_typed_equipment_update_preserves_omitted_specs_and_checks_revision(tmp_path):
    settings = Settings("127.0.0.1", 8190, tmp_path / "data", (), workspace=tmp_path)
    upgrade_database(settings)
    with closing(Database(settings.database_path)) as database:
        with database.write_session() as session:
            created = create_equipment(session, CameraCreate(kind="camera", name="camera",
                                                             specs=CameraSpecs(sensor_width_px=4096, pixel_size_um=3.76)))
        with database.write_session() as session:
            changed = update_equipment(session, created.id, CameraPatch(kind="camera", base_revision=1,
                                                                       specs={"pixel_size_um": None}))
            assert isinstance(changed, CameraOut)
            assert changed.specs.pixel_size_um is None
            assert changed.specs.sensor_width_px == 4096
            assert changed.revision == 2
        with pytest.raises(ApiError) as conflict, database.write_session() as session:
            update_equipment(session, created.id, CameraPatch(kind="camera", base_revision=1, name="stale"))
        assert conflict.value.code == "REVISION_CONFLICT"
        with database.read_session() as session:
            assert get_equipment(session, created.id).name == "camera"
