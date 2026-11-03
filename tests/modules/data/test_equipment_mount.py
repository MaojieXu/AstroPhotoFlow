"""Mount identity belongs to equipment snapshots, never capture parameters."""

import json
from copy import deepcopy
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from astrophotoflow.contracts.equipment import EquipmentCreate, MountCreate, MountPatch
from astrophotoflow.contracts.image_management import AssetRevisionRef, EquipmentApplication
from astrophotoflow.contracts.metadata import AssetParametersPatch
from astrophotoflow.contracts.setups import EquipmentSetupCreate, EquipmentSetupQuery
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.assets.image_management import apply_image_equipment
from astrophotoflow.modules.data.assets.image_metadata import freeze_equipment_application, freeze_import_equipment
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion
from astrophotoflow.modules.data.equipment.queries import list_equipment, list_setups
from astrophotoflow.modules.data.equipment.service import create_equipment, update_equipment
from astrophotoflow.modules.data.equipment.setups import create_setup
from astrophotoflow.modules.data.equipment.snapshots import capture_defaults_snapshot
from astrophotoflow.modules.data.persistence import schema_metadata


def parsed(model, value):
    return model.model_validate_json(json.dumps(value))


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "mounts.sqlite3")
    schema_metadata().create_all(database.engine)
    yield database
    database.close()


def test_mount_contract_rejects_specs_and_control_fields():
    assert MountCreate(kind="mount", name="AP1100").model_dump() == {
        "kind": "mount", "name": "AP1100", "model": None, "notes": None}
    for field, value in (("specs", {}), ("address", "COM4"), ("payload_kg", 50)):
        with pytest.raises(ValidationError):
            TypeAdapter(EquipmentCreate).validate_python({"kind": "mount", "name": "AP1100", field: value})
    with pytest.raises(ValidationError):
        AssetParametersPatch.model_validate({"mount_id": str(uuid4())})


def test_mount_registry_and_setup_cardinality_inline_and_sorting(db):
    from astrophotoflow.contracts.equipment import EquipmentQuery
    with db.write_session() as session:
        mount = create_equipment(session, MountCreate(kind="mount", name="Z mount"))
        assert "specs" not in mount.model_dump()
        renamed = update_equipment(session, mount.id, MountPatch(kind="mount", base_revision=1, notes="equatorial"))
        assert renamed.revision == 2
        assert list_equipment(session, EquipmentQuery(kind="mount")).total == 1
        create_setup(session, parsed(EquipmentSetupCreate, {"name": "registered", "components": [
            {"source": "registered", "equipment_id": str(mount.id)}]}))
        create_setup(session, parsed(EquipmentSetupCreate, {"name": "inline", "components": [
            {"source": "inline", "equipment": {"kind": "mount", "name": "A mount"}}]}))
        page = list_setups(session, EquipmentSetupQuery(sort_by="mount", order="asc", component_kind="mount"))
        assert [item.name for item in page.items] == ["inline", "registered"]
        with pytest.raises(ApiError):
            create_setup(session, parsed(EquipmentSetupCreate, {"name": "two mounts", "components": [
                {"source": "registered", "equipment_id": str(mount.id)},
                {"source": "inline", "equipment": {"kind": "mount", "name": "another"}}]}))
        with pytest.raises(ApiError):
            create_setup(session, parsed(EquipmentSetupCreate, {"name": "invalid accessory", "components": [
                {"source": "registered", "equipment_id": str(mount.id), "optical_accessory_id": str(uuid4())}]}))


def test_setup_and_import_freeze_mount_without_capture_parameters(db):
    with db.write_session() as session:
        mount = create_equipment(session, MountCreate(kind="mount", name="AP1100"))
        setup = create_setup(session, parsed(EquipmentSetupCreate, {"name": "rig", "components": [
            {"source": "registered", "equipment_id": str(mount.id)}]}))
        choice = parsed(EquipmentApplication, {"choice": {"source": "setup", "setup_id": str(setup.id), "expected_revision": 1}, "fields": ["mount"]})
        defaults = capture_defaults_snapshot(session, AssetParametersPatch(), choice).model_dump(mode="json", exclude_unset=True)
        assert defaults["selected_equipment"]["mount_id"]["id"] == str(mount.id)
        assert "specs" not in defaults["selected_equipment"]["mount_id"]
        assert "mount_id" not in defaults["parameters"]
        for source in ({"source": "setup", "setup_id": str(setup.id), "expected_revision": 1},):
            frozen = freeze_import_equipment(session, parsed(EquipmentApplication, {"choice": source, "fields": ["mount"]}), {"gain": 0})
            assert frozen["selected_equipment"]["mount_id"]["id"] == str(mount.id)
            assert frozen["parameters"] == {"gain": 0}
            assert frozen["equipment_setup"]["components"][0]["equipment"]["kind"] == "mount"
        old = deepcopy(defaults)
        update_equipment(session, mount.id, MountPatch(kind="mount", base_revision=1, name="renamed"))
        assert defaults == old and defaults["selected_equipment"]["mount_id"]["name"] == "AP1100"


def test_image_mount_apply_clear_omission_and_revision_preserve_content(db):
    with db.write_session() as session:
        mount = create_equipment(session, MountCreate(kind="mount", name="AP1100"))
        asset = Asset(id=str(uuid4()), name="light", scope="shared", role="raw", status="active", revision=1,
                      exposure_seconds=300, gain=0, offset=0, sensor_temperature_c=-10)
        session.add(asset)
        session.flush()
        version = AssetVersion(id=str(uuid4()), asset_id=asset.id, version_number=1, storage_mode="managed",
                               storage_location="objects/source.fits", availability="available",
                               capture_snapshot={"parameters": {"gain": 0}, "equipment_snapshot": {}})
        session.add(version)
        session.flush()
        asset.current_version_id = version.id
        session.flush()
        old_snapshot = deepcopy(version.capture_snapshot)
        app = parsed(EquipmentApplication, {"choice": {"source": "devices", "mount": {
            "equipment_id": str(mount.id), "expected_revision": 1}}, "fields": ["mount"]})
        result = apply_image_equipment(session, [AssetRevisionRef(asset_id=asset.id, expected_revision=1)], app)
        assert result["items"][0]["asset"]["equipment_snapshot"]["mount_id"]["id"] == str(mount.id)
        assert asset.exposure_seconds == 300 and asset.gain == 0 and asset.offset == 0 and asset.sensor_temperature_c == -10
        assert version.capture_snapshot == old_snapshot
        with pytest.raises(ApiError):
            apply_image_equipment(session, [AssetRevisionRef(asset_id=asset.id, expected_revision=1)], app)
        other = parsed(EquipmentApplication, {"choice": {"source": "devices", "filter": None}, "fields": ["filter"]})
        apply_image_equipment(session, [AssetRevisionRef(asset_id=asset.id, expected_revision=2)], other)
        assert asset.equipment_snapshot["mount_id"]["id"] == str(mount.id)
        clear = parsed(EquipmentApplication, {"choice": {"source": "devices", "mount": None}, "fields": ["mount"]})
        result = apply_image_equipment(session, [AssetRevisionRef(asset_id=asset.id, expected_revision=3)], clear)
        assert "mount_id" not in result["items"][0]["asset"]["equipment_snapshot"]
        assert asset.current_version_id == version.id and version.capture_snapshot == old_snapshot
        with pytest.raises(ApiError):
            freeze_equipment_application(session, parsed(EquipmentApplication, {"choice": {"source": "devices"}, "fields": ["mount"]}))


def test_explicit_import_pins_mount_and_delete_preview_preserves_image(tmp_path):
    import numpy as np
    from astropy.io import fits

    from astrophotoflow.contracts.image_imports import ExplicitImportRequest, ImageInspectionRequest
    from astrophotoflow.contracts.trash import EquipmentDelete, EquipmentDeleteSelection
    from astrophotoflow.core.config import Settings
    from astrophotoflow.core.database.schema import upgrade_database
    from astrophotoflow.modules.data.equipment.setups import get_setup
    from astrophotoflow.modules.data.imports.explicit import (
        get_image_import,
        inspect_image_files,
        list_image_inspection_files,
        submit_image_import,
    )
    from astrophotoflow.modules.data.imports.runner import run_import_task
    from astrophotoflow.modules.data.trash.management import delete_equipment_entries, preview_equipment_delete

    source = tmp_path / "light.fits"
    fits.PrimaryHDU(np.zeros((8, 8), dtype=np.float32)).writeto(source)
    settings = Settings("127.0.0.1", 8190, tmp_path / "data", (), workspace=tmp_path)
    upgrade_database(settings)
    database = Database(settings.database_path)
    try:
        with database.write_session() as session:
            mount = create_equipment(session, MountCreate(kind="mount", name="AP1100"))
            setup = create_setup(session, parsed(EquipmentSetupCreate, {"name": "rig", "components": [
                {"source": "registered", "equipment_id": str(mount.id)}]}))
        observed = inspect_image_files(settings, ImageInspectionRequest(paths=[str(source)]))
        entries = list_image_inspection_files(settings, observed["scan_id"])["items"]
        request = parsed(ExplicitImportRequest, {"request_id": str(uuid4()), "scan_id": observed["scan_id"],
            "files": [{"file_id": entries[0]["file_id"]}], "destination": {"mode": "standalone"},
            "defaults": {"equipment": {"choice": {"source": "setup", "setup_id": str(setup.id),
                "expected_revision": 1}, "fields": ["mount"]}}})
        with database.write_session() as session:
            accepted = submit_image_import(session, settings, request)
        run_import_task(database, settings, accepted.receipt["task_id"])
        with database.write_session() as session:
            receipt = get_image_import(session, request.request_id)
            assert receipt["status"] == "completed"
            asset = session.get(Asset, receipt["items"][0]["asset_id"])
            version = session.get(AssetVersion, receipt["items"][0]["asset_version_id"])
            frozen = deepcopy(version.capture_snapshot)
            assert asset.equipment_snapshot["mount_id"]["id"] == str(mount.id)
            assert frozen["equipment_snapshot"]["mount_id"]["id"] == str(mount.id)
            assert "mount_id" not in frozen["parameters"]
            assert "specs" not in frozen["equipment_snapshot"]["mount_id"]
            selection = parsed(EquipmentDeleteSelection, {"items": [
                {"entry_type": "equipment", "id": str(mount.id), "revision": 1}]})
            preview = preview_equipment_delete(selection, session)
            assert next(v for v in preview.dependencies if v.kind == "materials").count == 1
            delete_equipment_entries(EquipmentDelete(items=selection.items, preview_fingerprint=preview.preview_fingerprint), session)
            assert session.get(AssetVersion, version.id).capture_snapshot == frozen
            assert asset.equipment_snapshot["mount_id"]["name"] == "AP1100"
            assert get_setup(session, setup.id).components == []
    finally:
        database.close()
