"""Managed copies, per-file failures, stable retries and original protection."""

import shutil
from uuid import UUID

import pytest
from sqlalchemy import event, func, select

from astrophotoflow.contracts.imports import RetryCreate
from astrophotoflow.contracts.inputs import AssetInputReference, ScienceSelection
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.imports import stages
from astrophotoflow.modules.data.public import (
    get_image_import_task,
    observe_asset_content,
    resolve_canvas_inputs,
    retry_asset_task,
    run_import_task,
)
from astrophotoflow.modules.data.science.files import hash_file


def test_each_authored_group_has_a_verified_representative(real_library, authored_group):
    source = real_library.root / authored_group['members'][0]['path']
    before = source.stat()
    receipt = real_library.import_group(authored_group, count=1)
    assert receipt['stages']['publication']['state'] == 'published', receipt
    asset = real_library.assets(receipt)[0]
    managed = real_library.settings.data_dir / asset.storage_location
    assert asset.storage_mode == 'managed' and managed.is_file()
    assert managed.name == source.name
    assert hash_file(managed)[:2] == hash_file(source)[:2] == (asset.content_hash, asset.byte_size)
    assert asset.calibration_status == receipt['items'][0]['calibration_status'] == 'Unknown'
    assert receipt['items'][0]['calibration_binding_status'] == 'saved'
    assert (source.stat().st_size, source.stat().st_mtime_ns) == (before.st_size, before.st_mtime_ns)


def test_partial_copy_failure_retries_the_same_asset(real_library, green_group, tmp_path, monkeypatch):
    faults = tmp_path / 'fault-sources'
    faults.mkdir()
    copies = []
    for member in green_group['members'][:2]:
        source = real_library.root / member['path']
        target = faults / source.name
        shutil.copy2(source, target)
        copies.append(target)
    original_copy = stages.read_hash_and_copy
    failures = {copies[1].name}

    def fail_once(path, *args, **kwargs):
        if path.name in failures:
            failures.remove(path.name)
            raise ApiError(422, 'SOURCE_UNAVAILABLE', 'Injected temporary-copy read failure.')
        return original_copy(path, *args, **kwargs)

    monkeypatch.setattr(stages, 'read_hash_and_copy', fail_once)
    initial = real_library.import_files(copies, name='Explicit partial-copy group')
    failed = next(item for item in initial['items'] if item['originals'] == 'failed')
    assert failed['asset_id'] is not None
    assert any(item['originals'] == 'available' for item in initial['items'])
    with real_library.database.write_session() as session:
        accepted = retry_asset_task(session, UUID(initial['task_id']), RetryCreate(item_ids=[failed['task_item_id']]))
    run_import_task(real_library.database, real_library.settings, str(accepted.task_id), real_library.workers)
    with real_library.database.read_session() as session:
        result = get_image_import_task(session, initial['task_id'], items_limit=200)
        assert session.scalar(select(func.count()).select_from(Asset)) == 2
    retried = next(item for item in result['items'] if item['file_id'] == failed['file_id'])
    assert retried['asset_id'] == failed['asset_id']
    assert retried['originals'] == 'available'


def test_original_changes_block_science_until_original_bytes_return(real_library, imported_group, tmp_path):
    asset = real_library.assets(imported_group)[0]
    path = real_library.settings.data_dir / asset.storage_location
    reference = AssetInputReference(kind='asset', asset_id=asset.id, selection=ScienceSelection(kind='whole_file'))
    with path.open('r+b') as stream:
        stream.seek(-1, 2)
        original = stream.read(1)
        stream.seek(-1, 2)
        stream.write(bytes([original[0] ^ 1]))
    with pytest.raises(ApiError, match='登记原件|Original|original') as changed:
        resolve_canvas_inputs(real_library.database, real_library.settings, reference, run_directory=tmp_path / 'blocked')
    assert changed.value.code == 'SOURCE_CHANGED'
    assert observe_asset_content(real_library.database, real_library.settings, UUID(asset.id)).state == 'changed'
    with path.open('r+b') as stream:
        stream.seek(-1, 2)
        stream.write(original)
    assert observe_asset_content(real_library.database, real_library.settings, UUID(asset.id)).state == 'unchanged'
    result = resolve_canvas_inputs(real_library.database, real_library.settings, reference, run_directory=tmp_path / 'restored')
    assert result.items[0].asset_id == UUID(asset.id)
    assert result.items[0].content_hash == asset.content_hash


def test_publication_interruption_keeps_the_registered_hash(real_library, green_group):
    fail = True

    def stop_availability(session, _context, _instances):
        nonlocal fail
        if fail and any(isinstance(row, Asset) and row.availability == 'available' for row in session.dirty):
            fail = False
            raise RuntimeError('Controlled interruption after atomic original placement.')

    event.listen(real_library.database.sessions, 'before_flush', stop_availability)
    try:
        initial = real_library.import_group(green_group, count=1)
    finally:
        event.remove(real_library.database.sessions, 'before_flush', stop_availability)
    asset = real_library.assets(initial)[0]
    path = real_library.settings.data_dir / asset.storage_location
    assert path.exists() and asset.content_hash
    with path.open('r+b') as stream:
        stream.seek(-1, 2)
        value = stream.read(1)
        stream.seek(-1, 2)
        stream.write(bytes([value[0] ^ 1]))
    item = initial['items'][0]
    with real_library.database.write_session() as session:
        retry = retry_asset_task(session, UUID(initial['task_id']), RetryCreate(item_ids=[item['task_item_id']]))
    real_library.node.user_properties.append(('retry_task_ids', [str(retry.task_id)]))
    run_import_task(real_library.database, real_library.settings, str(retry.task_id), real_library.workers)
    with real_library.database.read_session() as session:
        current = session.get(Asset, asset.id)
        assert current.content_hash == asset.content_hash
        assert current.availability == 'changed'
    with path.open('r+b') as stream:
        stream.seek(-1, 2)
        stream.write(value)
    restored = observe_asset_content(real_library.database, real_library.settings, UUID(asset.id))
    assert restored.state == 'unchanged'


@pytest.mark.full_import
def test_full_corpus_is_copied_once_with_514_receipts(real_library, real_data_catalog):
    required = sum(member['byte_size'] for group in real_data_catalog['groups'] for member in group['members'])
    required += sum(master['byte_size'] for master in real_data_catalog['masters'])
    assert shutil.disk_usage(real_library.settings.data_dir).free > required + 256 * 1024 * 1024
    assets = []
    for group in real_data_catalog['groups']:
        receipt = real_library.import_group(group, count=len(group['members']))
        assert receipt['items_total'] == len(group['members'])
        assert all(item['originals'] == 'available' for item in receipt['items']), receipt
        assets.extend(real_library.assets(receipt))
    for master in real_data_catalog['masters']:
        receipt = real_library.import_files([real_library.root / master['path']], frame_class='masterframe', frame_type=master['frame_type'])
        assert receipt['items'][0]['originals'] == 'available'
        assets.extend(real_library.assets(receipt))
    assert len(assets) == len({asset.id for asset in assets}) == 514
    assert sum(asset.byte_size for asset in assets) == required
    assert all(hash_file(real_library.settings.data_dir / asset.storage_location)[:2] == (asset.content_hash, asset.byte_size) for asset in assets)
