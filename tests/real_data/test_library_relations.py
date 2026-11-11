"""Regressions for reference boundaries and original cleanup admission."""

from copy import deepcopy
from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import select

from astrophotoflow.contracts.assets import AssetPatch
from astrophotoflow.contracts.datasets import DatasetCreate, DatasetMemberParametersUpdate
from astrophotoflow.contracts.equipment import CameraCreate
from astrophotoflow.contracts.projects import ProjectCreate, ProjectDatasetReferenceCreate, ProjectReferenceCreate
from astrophotoflow.contracts.trash import (
    EquipmentDelete,
    EquipmentDeleteSelection,
    LibraryEntriesRemove,
    LibraryTrashDelete,
    LibraryTrashSelection,
)
from astrophotoflow.core.errors import ApiError
from astrophotoflow.interfaces.application import library_organization
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.datasets.bindings import set_dataset_bindings
from astrophotoflow.modules.data.datasets.models import Dataset
from astrophotoflow.modules.data.public import (
    add_project_asset_reference,
    add_project_dataset_reference,
    create_dataset,
    create_equipment,
    create_project,
    delete_equipment_entries,
    get_dataset,
    library_trash,
    plan_cleanup,
    preview_equipment_delete,
    remove_library_entries,
    update_asset,
    update_dataset_member_parameters,
)


def _trash_dataset(library, dataset_id):
    with library.database.write_session() as session:
        dataset = get_dataset(session, UUID(dataset_id))
        remove_library_entries(
            session, LibraryEntriesRemove(items=[{"entry_type": "dataset", "id": dataset.id, "revision": dataset.revision}])
        )
    with library.database.read_session() as session:
        row = next(item for item in library_trash(session).items if str(item.id) == str(dataset_id))
    return LibraryTrashSelection(items=[{"entry_type": "dataset", "id": row.id, "revision": row.revision, "removed_at": row.removed_at}])


def test_reimport_has_independent_identity_and_original(real_library, green_group):
    path = real_library.root / green_group["members"][0]["path"]
    first = real_library.assets(real_library.import_files([path]))[0]
    second = real_library.assets(real_library.import_files([path]))[0]
    assert first.id != second.id
    assert first.storage_location != second.storage_location
    assert first.content_hash == second.content_hash
    assert all((real_library.settings.data_dir / asset.storage_location).is_file() for asset in (first, second))


def test_external_project_reference_blocks_dataset_cleanup(real_library, imported_group):
    dataset_id = imported_group["stages"]["publication"]["dataset_id"]
    assets = real_library.assets(imported_group)
    with real_library.database.write_session() as session:
        project = create_project(session, ProjectCreate(name="Referenced material project"))
        add_project_dataset_reference(
            session, project.id, ProjectDatasetReferenceCreate(base_revision=project.revision, dataset_id=dataset_id)
        )
    selection = _trash_dataset(real_library, dataset_id)
    with real_library.database.read_session() as session:
        preview = plan_cleanup(session, real_library.settings, selection)
    assert any(reference.kind == "project_dataset" for reference in preview.references)
    command = LibraryTrashDelete(**selection.model_dump(), preview_fingerprint=preview.preview_fingerprint)
    with pytest.raises(ApiError) as blocked:
        library_organization.execute_cleanup(real_library.database, real_library.settings, command)
    assert blocked.value.code == "REFERENCES_EXIST"
    assert all((real_library.settings.data_dir / asset.storage_location).is_file() for asset in assets)


def test_trash_material_cannot_gain_project_or_dataset_reference(real_library, green_group):
    asset = real_library.assets(real_library.import_files([real_library.root / green_group["members"][0]["path"]]))[0]
    with real_library.database.write_session() as session:
        project = create_project(session, ProjectCreate(name="Reference boundary project"))
        remove_library_entries(session, LibraryEntriesRemove(items=[{"entry_type": "asset", "id": asset.id, "revision": asset.revision}]))
    with pytest.raises(ApiError) as grouped, real_library.database.write_session() as session:
        create_dataset(session, DatasetCreate(name="Unavailable member", asset_ids=[asset.id]))
    assert grouped.value.code == "REFERENCE_UNAVAILABLE"
    with pytest.raises(ApiError) as referenced, real_library.database.write_session() as session:
        add_project_asset_reference(session, project.id, ProjectReferenceCreate(base_revision=project.revision, asset_id=asset.id))
    assert referenced.value.code == "REFERENCE_UNAVAILABLE"


def test_bound_master_classification_edit_rolls_back(real_library, imported_group, master_dark):
    dataset_id = imported_group["stages"]["publication"]["dataset_id"]
    with real_library.database.write_session() as session:
        set_dataset_bindings(session.get(Dataset, dataset_id), {"dark": {"kind": "asset", "id": master_dark.id}})
    with pytest.raises(ApiError) as invalid, real_library.database.write_session() as session:
        update_asset(
            session,
            UUID(master_dark.id),
            AssetPatch(base_revision=master_dark.revision, classification={"frame_class": "subframe", "frame_type": "dark"}),
        )
    assert invalid.value.code == "CALIBRATION_DEPENDENCY_CONFLICT"
    with real_library.database.read_session() as session:
        assert session.get(Asset, master_dark.id).frame_class == "masterframe"


def test_consumer_purpose_edit_preserves_valid_existing_bindings(real_library, imported_group, master_dark):
    dataset_id = imported_group["stages"]["publication"]["dataset_id"]
    assets = real_library.assets(imported_group)
    with real_library.database.write_session() as session:
        set_dataset_bindings(session.get(Dataset, dataset_id), {"dark": {"kind": "asset", "id": master_dark.id}})
        dataset = get_dataset(session, UUID(dataset_id))
    command = DatasetMemberParametersUpdate(
        base_revision=dataset.revision,
        members=[{"asset_id": asset.id, "revision": asset.revision} for asset in assets],
        classification={"frame_class": "subframe", "frame_type": "flat"},
    )
    with pytest.raises(ApiError) as invalid, real_library.database.write_session() as session:
        update_dataset_member_parameters(session, UUID(dataset_id), command)
    assert invalid.value.code == "CALIBRATION_DEPENDENCY_CONFLICT"
    with real_library.database.read_session() as session:
        assert set(session.scalars(select(Asset.frame_type).where(Asset.id.in_([asset.id for asset in assets])))) == {"light"}


def test_active_software_blocks_cleanup_before_file_deletion(real_library, imported_group, monkeypatch):
    dataset_id = imported_group["stages"]["publication"]["dataset_id"]
    assets = real_library.assets(imported_group)
    selection = _trash_dataset(real_library, dataset_id)
    invocation = SimpleNamespace(inputs={"image": [SimpleNamespace(kind="asset", asset_id=UUID(assets[0].id))]}, supporting_inputs={})
    record = SimpleNamespace(invocation=invocation, state="running")
    monkeypatch.setattr(library_organization, "unfinished_software_calls", lambda settings: [("prompt", "active-call", record)])
    preview = library_organization.preflight_cleanup(real_library.database, real_library.settings, selection)
    assert any("active-call" in blocker for blocker in preview.blockers)
    command = LibraryTrashDelete(**selection.model_dump(), preview_fingerprint=preview.preview_fingerprint)
    with pytest.raises(ApiError) as busy:
        library_organization.execute_cleanup(real_library.database, real_library.settings, command)
    assert busy.value.code == "ORIGINALS_IN_USE"
    assert all((real_library.settings.data_dir / asset.storage_location).is_file() for asset in assets)


def test_equipment_delete_advances_material_and_preserves_import_snapshot(real_library, imported_group):
    asset = real_library.assets(imported_group)[0]
    with real_library.database.write_session() as session:
        camera = create_equipment(session, CameraCreate(kind="camera", name="Import camera"))
        current = update_asset(session, UUID(asset.id), AssetPatch(base_revision=asset.revision, parameters={"camera_id": camera.id}))
        capture = deepcopy(session.get(Asset, asset.id).capture_snapshot)
    selection = EquipmentDeleteSelection(items=[{"entry_type": "equipment", "id": camera.id, "revision": camera.revision}])
    with real_library.database.read_session() as session:
        preview = preview_equipment_delete(selection, session)
    with real_library.database.write_session() as session:
        delete_equipment_entries(EquipmentDelete(**selection.model_dump(), preview_fingerprint=preview.preview_fingerprint), session)
    with real_library.database.read_session() as session:
        updated = session.get(Asset, asset.id)
        assert updated.revision == current.revision + 1
        assert updated.camera_id is None and updated.updated_at is not None
        assert updated.capture_snapshot == capture
        assert updated.equipment_snapshot["camera_id"]["id"] == str(camera.id)
    with pytest.raises(ApiError) as stale, real_library.database.write_session() as session:
        update_asset(session, UUID(asset.id), AssetPatch(base_revision=current.revision, notes="Stale edit"))
    assert stale.value.code == "REVISION_CONFLICT"


def test_direct_import_request_replay_retains_one_task(real_library, green_group):
    from uuid import uuid4

    from astrophotoflow.contracts.imports import ImportCreate
    from astrophotoflow.modules.data.imports.models import AssetTask
    from astrophotoflow.modules.data.public import create_import

    path = real_library.root / green_group["members"][0]["path"]
    body = ImportCreate(request_id=uuid4(), mode="standalone", storage_mode="managed", sources=[{"path": str(path)}])
    with real_library.database.write_session() as session:
        first = create_import(session, real_library.settings, body)
    with real_library.database.write_session() as session:
        second = create_import(session, real_library.settings, body)
        identities = list(session.scalars(select(AssetTask.id).where(AssetTask.request_id == str(body.request_id))))
    assert first.task_id == second.task_id
    assert identities == [str(first.task_id)]
