"""Readable classification, Windows paths and factual organization receipts."""

from errno import EOPNOTSUPP
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from astrophotoflow.contracts.data_nodes import NativeDataExecute
from astrophotoflow.contracts.datasets import DatasetPatch
from astrophotoflow.contracts.library import LibraryOrganizeExecute, LibraryOrganizeRequest
from astrophotoflow.core.errors import ApiError
from astrophotoflow.interfaces.application import library_organization
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.library import organization
from astrophotoflow.modules.data.library.layout import PURPOSE_DIRECTORIES, library_path, safe_component
from astrophotoflow.modules.data.public import (
    execute_data_node,
    get_dataset,
    get_library_organization,
    get_result_member,
    organize_library,
    plan_library_organization,
    update_dataset,
)


def _renamed_plan(library, receipt):
    identity = UUID(receipt['stages']['publication']['dataset_id'])
    with library.database.write_session() as session:
        current = get_dataset(session, identity)
        updated = update_dataset(session, identity, DatasetPatch(base_revision=current.revision, name='IC443_Green_reorganized'))
    body = LibraryOrganizeRequest(entry_type='dataset', id=identity, base_revision=updated.revision)
    with library.database.read_session() as session:
        plan = plan_library_organization(session, library.settings, body)
    return plan, LibraryOrganizeExecute(**body.model_dump(), request_id=uuid4(), plan_token=plan.token)


def test_complete_category_matrix_and_colocated_dataset_json(real_library, imported_group):
    root = real_library.settings.data_dir / 'library'
    for purpose in (*PURPOSE_DIRECTORIES.values(), 'Unclassified'):
        forms = ('Subframe', 'MasterFrame', 'Other') if purpose == 'Unclassified' else ('Subframe', 'MasterFrame')
        for form in forms:
            for status in ('UnCalibrated', 'Calibrated', 'Unknown'):
                assert (root / purpose / form / status).is_dir()
    assets = real_library.assets(imported_group)
    parents = {(real_library.settings.data_dir / asset.storage_location).parent for asset in assets}
    assert len(parents) == 1
    directory = parents.pop()
    assert directory.parent.relative_to(root).as_posix() == 'Light/Subframe/Unknown'
    assert 'GAIN90' in directory.name and 'T-20C' in directory.name and 'EXP120s' in directory.name and 'F-Green' in directory.name
    assert (directory / 'dataset.json').is_file()
    assert not (directory / 'Files').exists() and not (directory / 'Datasets').exists()


def test_master_is_independent_and_dark_name_omits_filter(real_library, master_dark):
    relative = Path(master_dark.storage_location).relative_to('library')
    assert relative.parts[:3] == ('Dark', 'MasterFrame', 'Unknown')
    assert 'EXP120s' in relative.parts[3] and 'F-' not in relative.parts[3]
    assert relative.name == master_dark.original_filename


def test_other_supported_files_use_unclassified_other(real_library, tmp_path):
    source = tmp_path / 'comparison-stars.csv'
    source.write_text('name,magnitude\nfixture-star,10\n', encoding='utf-8')
    receipt = real_library.import_files([source], frame_class=None, frame_type=None)
    asset = real_library.assets(receipt)[0]
    assert Path(asset.storage_location).parts[1:4] == ('Unclassified', 'Other', 'Unknown')
    assert (real_library.settings.data_dir / asset.storage_location).read_bytes() == source.read_bytes()


def test_windows_names_and_library_escape(real_library):
    assert safe_component('CON.fit') == '_CON.fit'
    assert safe_component('bad<>:"/\\|?* name. ') == 'bad_________ name'
    with pytest.raises(ApiError) as escaped:
        library_path(real_library.settings.data_dir, '../external-source.fits')
    assert escaped.value.code == 'FILE_SCOPE_INVALID'


def test_partial_moves_report_actual_locations_and_replay(real_library, imported_group, monkeypatch):
    plan, body = _renamed_plan(real_library, imported_group)
    assert plan.blockers == []
    original_link = organization.os.link
    failing = plan.moves[1].source

    def fail_second(source, target):
        if Path(source).as_posix().endswith(failing):
            raise PermissionError('Injected occupied workspace copy.')
        return original_link(source, target)

    monkeypatch.setattr(organization.os, 'link', fail_second)
    result = organize_library(real_library.database, real_library.settings, body)
    assert result.state == 'partial'
    assert [move.state for move in result.plan.moves] == ['completed', 'failed']
    with real_library.database.read_session() as session:
        for move in result.plan.moves:
            asset = session.get(Asset, str(move.asset_id))
            expected = move.destination if move.state == 'completed' else move.source
            assert asset.storage_location == (Path('library') / expected).as_posix()
            assert (real_library.settings.data_dir / asset.storage_location).is_file()
        stored = get_library_organization(session, body.request_id)
    assert stored == result
    assert organize_library(real_library.database, real_library.settings, body) == result


def test_new_destination_conflict_invalidates_the_reviewed_plan(real_library, imported_group):
    plan, body = _renamed_plan(real_library, imported_group)
    occupied = library_path(real_library.settings.data_dir, plan.moves[0].destination)
    occupied.parent.mkdir(parents=True, exist_ok=True)
    occupied.write_bytes(b'User-owned conflict fixture')
    with pytest.raises(ApiError) as stale:
        organize_library(real_library.database, real_library.settings, body)
    assert stale.value.code == 'REVISION_CONFLICT'
    assert occupied.read_bytes() == b'User-owned conflict fixture'
    assert all(library_path(real_library.settings.data_dir, move.source).is_file() for move in plan.moves)


def test_active_software_call_blocks_directory_changes(real_library, imported_group, monkeypatch):
    plan, body = _renamed_plan(real_library, imported_group)
    call_id = uuid4()
    observation = SimpleNamespace(state='running', invocation=SimpleNamespace(
        inputs={'image': [SimpleNamespace(kind='asset', asset_id=plan.moves[0].asset_id)]}, supporting_inputs={},
    ))
    monkeypatch.setattr(library_organization, 'unfinished_software_calls', lambda settings: iter([(uuid4(), call_id, observation)]))
    with pytest.raises(ApiError) as busy:
        library_organization.execute_organization(real_library.database, real_library.settings, body)
    assert busy.value.code == 'LIBRARY_BUSY'
    assert str(call_id) in busy.value.message
    assert all(library_path(real_library.settings.data_dir, move.source).is_file() for move in plan.moves)


def test_filesystems_without_hard_links_use_verified_copy(real_library, imported_group, monkeypatch):
    plan, body = _renamed_plan(real_library, imported_group)

    def unsupported(source, target):
        raise OSError(EOPNOTSUPP, 'Controlled filesystem without hard links.')

    monkeypatch.setattr(organization.os, 'link', unsupported)
    result = organize_library(real_library.database, real_library.settings, body)
    assert result.state == 'completed'
    assert all(library_path(real_library.settings.data_dir, move.destination).is_file() for move in plan.moves)
    assert all(not library_path(real_library.settings.data_dir, move.source).exists() for move in plan.moves)


def test_checked_data_results_survive_library_directory_changes(real_library, imported_group):
    identity = UUID(imported_group['stages']['publication']['dataset_id'])
    request = NativeDataExecute(run_id=uuid4(), execution_id=uuid4(), node_id='source',
                               reference={'kind': 'dataset', 'dataset_id': identity})
    result = execute_data_node(real_library.database, real_library.settings, request)
    assert result.state == 'completed'
    plan, body = _renamed_plan(real_library, imported_group)
    moved = organize_library(real_library.database, real_library.settings, body)
    assert moved.state == 'completed'
    checked, member, _ = get_result_member(real_library.settings, request.run_id, request.execution_id, 0, 0, full=True)
    assert checked.path.is_file()
    assert checked.content_hash == plan.moves[0].content_hash
    assert str(member.source_input.asset_id) == str(plan.moves[0].asset_id)
