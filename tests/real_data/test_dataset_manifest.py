"""Current SQLite relations, independent originals and recoverable mirror failures."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID

from astrophotoflow.contracts.assets import AssetPatch
from astrophotoflow.modules.data.library import manifests
from astrophotoflow.modules.data.public import (
    get_dataset,
    library_location,
    rebuild_dataset_manifest,
    update_asset,
)


def _manifest(library, dataset_id):
    with library.database.read_session() as session:
        location = library_location(session, library.settings, 'dataset', dataset_id)
    return location, json.loads(Path(location.manifest_path).read_text(encoding='utf-8'))


def test_manifest_has_ordered_relative_paths_and_independent_originals(real_library, imported_group):
    dataset_id = imported_group['stages']['publication']['dataset_id']
    assets = real_library.assets(imported_group)
    location, mirror = _manifest(real_library, dataset_id)
    assert location.manifest_status == 'ready'
    assert Path(location.manifest_path).name == 'dataset.json'
    assert [member['asset_id'] for member in mirror['members']] == [asset.id for asset in assets]
    assert [member['position'] for member in mirror['members']] == [0, 1]
    assert all(not Path(member['path']).is_absolute() for member in mirror['members'])
    assert mirror['pending_calibration'] == {} and mirror['executed_processing'] == []
    assert len(list((real_library.settings.data_dir / 'library').rglob('*.fits'))) == 2


def test_failed_mirror_retains_database_changes_and_rebuilds(real_library, imported_group, monkeypatch):
    dataset_id = UUID(imported_group['stages']['publication']['dataset_id'])
    asset = real_library.assets(imported_group)[0]
    replace = manifests.os.replace

    def fail_manifest(source, destination):
        if Path(destination).name == 'dataset.json':
            raise PermissionError('Injected dataset mirror replacement failure.')
        return replace(source, destination)

    monkeypatch.setattr(manifests.os, 'replace', fail_manifest)
    with real_library.database.write_session() as session:
        changed = update_asset(session, UUID(asset.id), AssetPatch(base_revision=asset.revision, name='Committed current name'))
    with real_library.database.read_session() as session:
        dataset = get_dataset(session, dataset_id)
        assert dataset.manifest_status == 'failed'
        assert 'Injected' in dataset.manifest_error
    assert changed.name == 'Committed current name'
    monkeypatch.setattr(manifests.os, 'replace', replace)
    with real_library.database.write_session() as session:
        rebuilt = rebuild_dataset_manifest(session, real_library.settings, dataset_id, dataset.revision)
    assert rebuilt.manifest_status == 'ready'
    _, mirror = _manifest(real_library, dataset_id)
    assert mirror['members'][0]['name'] == 'Committed current name'
    Path(rebuilt.manifest_path).unlink()
    with real_library.database.write_session() as session:
        restored = rebuild_dataset_manifest(session, real_library.settings, dataset_id, dataset.revision)
    assert Path(restored.manifest_path).is_file()


def test_concurrent_member_edits_publish_latest_current_facts(real_library, imported_group):
    assets = real_library.assets(imported_group)

    def change(index):
        with real_library.database.write_session() as session:
            return update_asset(session, UUID(assets[index].id), AssetPatch(base_revision=assets[index].revision, name=f'Concurrent member {index}'))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(change, range(2)))
    _, mirror = _manifest(real_library, imported_group['stages']['publication']['dataset_id'])
    assert [member['name'] for member in mirror['members']] == [result.name for result in results]
    assert mirror['revision'] >= 1
