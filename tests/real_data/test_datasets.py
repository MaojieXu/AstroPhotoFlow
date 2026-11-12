"""User-submitted membership, capture warnings and independently imported originals."""

from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import select

from astrophotoflow.contracts.datasets import DatasetCreate, DatasetMemberParametersUpdate, DatasetMembersCreate
from astrophotoflow.contracts.inputs import AssetInputReference, DatasetInputReference, ScienceSelection
from astrophotoflow.contracts.projects import ProjectCreate, ProjectDatasetReferenceCreate, ProjectReferenceCreate
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.datasets.models import DatasetMember
from astrophotoflow.modules.data.public import (
    add_project_asset_reference,
    add_project_dataset_reference,
    create_dataset,
    create_project,
    get_dataset,
    resolve_canvas_inputs,
    update_dataset_member_parameters,
    update_dataset_members,
)
from astrophotoflow.modules.data.science import inputs as input_service


def test_order_append_remove_and_exclusive_membership(real_library, imported_group, green_group):
    assets = real_library.assets(imported_group)
    dataset_id = UUID(imported_group['stages']['publication']['dataset_id'])
    positions = {asset.id: asset.storage_location for asset in assets}
    with pytest.raises(ApiError) as owner, real_library.database.write_session() as session:
        create_dataset(session, DatasetCreate(name='Conflicting owner', asset_ids=[asset.id for asset in assets]))
    assert owner.value.code == 'ASSET_DATASET_OWNERSHIP'
    with real_library.database.write_session() as session:
        first = get_dataset(session, dataset_id)
        ordered = update_dataset_members(session, dataset_id, DatasetMembersCreate(base_revision=first.revision, asset_ids=[asset.id for asset in reversed(assets)]))
    third = real_library.import_files([real_library.root / green_group['members'][2]['path']])
    added = real_library.assets(third)[0]
    with real_library.database.write_session() as session:
        extended = update_dataset_members(session, dataset_id, DatasetMembersCreate(
            base_revision=ordered.revision, asset_ids=[assets[1].id, assets[0].id, added.id],
        ))
        trimmed = update_dataset_members(session, dataset_id, DatasetMembersCreate(base_revision=extended.revision, asset_ids=[assets[1].id, added.id]))
        current = session.scalars(select(DatasetMember.asset_id).where(DatasetMember.dataset_id == str(dataset_id)).order_by(DatasetMember.position)).all()
        second = create_dataset(session, DatasetCreate(name='Reassigned removed member', asset_ids=[assets[0].id]))
    assert current == [assets[1].id, added.id]
    assert second.member_count == 1
    assert trimmed.member_count == 2
    assert all((real_library.settings.data_dir / path).exists() for path in positions.values())
    with pytest.raises(ApiError) as stale, real_library.database.write_session() as session:
        update_dataset_members(session, dataset_id, DatasetMembersCreate(base_revision=ordered.revision, asset_ids=[]))
    assert stale.value.code == 'REVISION_CONFLICT'


def test_filter_differences_and_masters_require_separate_organization(real_library, imported_group, real_data_catalog, master_dark):
    first = real_library.assets(imported_group)[0]
    red = next(group for group in real_data_catalog['groups'] if group['source_folder'] == 'IC443_RGB_P0' and group['header']['FILTER'] == 'Red')
    red_receipt = real_library.import_group(red, count=1)
    red_asset = real_library.assets(red_receipt)[0]
    with real_library.database.write_session() as session:
        current = get_dataset(session, UUID(imported_group['stages']['publication']['dataset_id']))
        update_dataset_members(session, current.id, DatasetMembersCreate(base_revision=current.revision, asset_ids=[]))
        red_group = get_dataset(session, UUID(red_receipt['stages']['publication']['dataset_id']))
        update_dataset_members(session, red_group.id, DatasetMembersCreate(base_revision=red_group.revision, asset_ids=[]))
        mixed = create_dataset(session, DatasetCreate(name='Submitted mixed filters', asset_ids=[first.id, red_asset.id]))
    assert any(warning.field == 'filter' for warning in mixed.capture_diagnostics.warnings)
    with pytest.raises(ApiError) as master_member, real_library.database.write_session() as session:
        create_dataset(session, DatasetCreate(name='Master cannot be a member', asset_ids=[master_dark.id]))
    assert master_member.value.code == 'INVALID_REFERENCE'


def test_partial_selection_uses_ids_and_current_dataset_order(real_library, imported_group, tmp_path):
    assets = real_library.assets(imported_group)
    dataset_id = UUID(imported_group['stages']['publication']['dataset_id'])
    reference = DatasetInputReference(kind='dataset', dataset_id=dataset_id, asset_ids=[asset.id for asset in assets])
    with real_library.database.write_session() as session:
        dataset = get_dataset(session, dataset_id)
        reordered = update_dataset_members(session, dataset_id, DatasetMembersCreate(base_revision=dataset.revision, asset_ids=[asset.id for asset in reversed(assets)]))
    resolved = resolve_canvas_inputs(real_library.database, real_library.settings, reference, run_directory=tmp_path / 'selected')
    assert [str(item.asset_id) for item in resolved.items] == [asset.id for asset in reversed(assets)]
    with real_library.database.write_session() as session:
        update_dataset_members(session, dataset_id, DatasetMembersCreate(base_revision=reordered.revision, asset_ids=[assets[1].id]))
    with pytest.raises(ApiError) as removed:
        resolve_canvas_inputs(real_library.database, real_library.settings, reference, run_directory=tmp_path / 'removed')
    assert removed.value.code == 'INVALID_REFERENCE'


def test_project_references_are_unique_stable_ids(real_library, imported_group):
    asset = real_library.assets(imported_group)[0]
    dataset_id = UUID(imported_group['stages']['publication']['dataset_id'])
    with real_library.database.write_session() as session:
        project = create_project(session, ProjectCreate(name='IC443 explicit project'))
        group_reference = add_project_dataset_reference(session, project.id, ProjectDatasetReferenceCreate(base_revision=project.revision, dataset_id=dataset_id))
        single = add_project_asset_reference(session, project.id, ProjectReferenceCreate(base_revision=project.revision + 1, asset_id=asset.id))
    assert group_reference.dataset_id == dataset_id
    assert str(single.asset_id) == asset.id
    with (
        pytest.raises(ApiError) as duplicate,
        real_library.database.write_session() as session,
    ):
        add_project_dataset_reference(session, project.id, ProjectDatasetReferenceCreate(base_revision=project.revision + 2, dataset_id=dataset_id))
    assert duplicate.value.status_code == 409


def test_one_call_freezes_all_input_ports_before_later_edits(real_library, imported_group, tmp_path, monkeypatch):
    assets = real_library.assets(imported_group)
    dataset_id = UUID(imported_group['stages']['publication']['dataset_id'])
    original = input_service._canvas_input_rows
    captured = 0

    def edit_between_ports(session, reference):
        nonlocal captured
        rows = original(session, reference)
        captured += 1
        if captured == 1:
            with real_library.database.write_session() as writer:
                dataset = get_dataset(writer, dataset_id)
                update_dataset_member_parameters(writer, dataset_id, DatasetMemberParametersUpdate.model_validate({
                    'base_revision': dataset.revision,
                    'members': [{'asset_id': asset.id, 'revision': asset.revision} for asset in assets],
                    'parameters': {'gain': 91.0},
                }))
        return rows

    monkeypatch.setattr(input_service, '_canvas_input_rows', edit_between_ports)
    references = {f'image/{index}': (AssetInputReference(kind='asset', asset_id=asset.id,
        selection=ScienceSelection(kind='whole_file')), None) for index, asset in enumerate(assets)}
    snapshot = input_service.resolve_canvas_input_groups(real_library.database, real_library.settings, references, run_directory=tmp_path / 'call')
    assert [value.items[0].parameters['gain'] for value in snapshot.values()] == [90, 90]
    future = resolve_canvas_inputs(real_library.database, real_library.settings, references['image/0'][0], run_directory=tmp_path / 'future-call')
    assert future.items[0].parameters['gain'] == 91


def test_mixed_submission_keeps_original_paths_factual(real_library, green_group, real_data_catalog):
    red = next(group for group in real_data_catalog['groups'] if group['source_folder'] == 'IC443_RGB_P0' and group['header']['FILTER'] == 'Red')
    receipt = real_library.import_files([real_library.root / group['members'][0]['path'] for group in [green_group, red]], name='Explicit invalid mixed filters')
    assert receipt['stages']['publication']['state'] == 'published'
    assets = real_library.assets(receipt)
    assert Path(assets[0].storage_location).parent == Path(assets[1].storage_location).parent
    with real_library.database.read_session() as session:
        dataset = get_dataset(session, UUID(receipt['stages']['publication']['dataset_id']))
    assert any(warning.field == 'filter' for warning in dataset.capture_diagnostics.warnings)
    assert all((real_library.settings.data_dir / asset.storage_location).is_file() for asset in assets)



def test_create_from_registered_members_attaches_project_atomically(real_library, imported_group):
    from uuid import uuid4

    from sqlalchemy import func

    from astrophotoflow.contracts.image_calibration import ImageDatasetCreate
    from astrophotoflow.modules.data.datasets.models import Dataset
    from astrophotoflow.modules.data.projects.models import ProjectDatasetReference
    from astrophotoflow.modules.data.public import create_image_dataset

    assets = real_library.assets(imported_group)
    with real_library.database.write_session() as session:
        project = create_project(session, ProjectCreate(name='Independent original project'))
        current = get_dataset(session, UUID(imported_group['stages']['publication']['dataset_id']))
        update_dataset_members(session, current.id, DatasetMembersCreate(base_revision=current.revision, asset_ids=[]))
    request = ImageDatasetCreate(request_id=uuid4(), name='Reuse current subframes',
        members=[{'asset_id': asset.id} for asset in assets], project_id=project.id, project_base_revision=project.revision)
    with real_library.database.write_session() as session:
        receipt = create_image_dataset(session, request)
    with real_library.database.write_session() as session:
        assert create_image_dataset(session, request) == receipt
        assert session.scalar(select(func.count()).select_from(ProjectDatasetReference).where(ProjectDatasetReference.project_id == str(project.id))) == 1
        count = session.scalar(select(func.count()).select_from(Dataset))
    with real_library.database.write_session() as session:
        current = get_dataset(session, UUID(receipt['result']['dataset_id']))
        update_dataset_members(session, current.id, DatasetMembersCreate(base_revision=current.revision, asset_ids=[]))
    stale = request.model_copy(update={'request_id':uuid4(), 'name':'Stale project creation'})
    with pytest.raises(ApiError) as error, real_library.database.write_session() as session:
        create_image_dataset(session, stale)
    assert error.value.code == 'REVISION_CONFLICT'
    with real_library.database.read_session() as session:
        assert session.scalar(select(func.count()).select_from(Dataset)) == count


@pytest.mark.parametrize(('temperatures', 'warns'), [([-19.9, -20.1], False), ([-20, -21], False), ([-19.9, -21], True)])
def test_capture_temperature_has_inclusive_one_degree_range(real_library, imported_group, temperatures, warns):
    from astrophotoflow.modules.data.assets.models import Asset
    dataset_id = UUID(imported_group['stages']['publication']['dataset_id'])
    assets = real_library.assets(imported_group)
    with real_library.database.write_session() as session:
        for asset, temperature in zip(assets, temperatures, strict=True):
            session.get(Asset, asset.id).sensor_temperature_c = temperature
        session.flush()
        dataset = get_dataset(session, dataset_id)
    assert any(warning.field == 'sensor_temperature_c' for warning in dataset.capture_diagnostics.warnings) is warns
