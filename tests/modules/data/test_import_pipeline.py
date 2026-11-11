from __future__ import annotations
from astrophotoflow.modules.data.datasets.models import Dataset
import astrophotoflow.modules.data.media.display as owner_display
import astrophotoflow.modules.data.imports.errors as owner_errors
import astrophotoflow.modules.data.media.import_previews as owner_import_previews
import astrophotoflow.modules.data.imports.enumeration as owner_enumeration
import astrophotoflow.modules.data.imports.tasks as owner_tasks
import astrophotoflow.modules.data.imports.runner as owner_runner
import astrophotoflow.modules.data.imports.stages as owner_stages
from astrophotoflow.modules.data.formats import xisf as codec_formats_xisf, raster as codec_formats_raster
from astrophotoflow.modules.data.formats import pixels as codec_formats_pixels
import os
import time
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from threading import Event, Lock, Thread
from uuid import uuid4
import blake3
import numpy as np
import pytest
from astropy.io import fits
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from astrophotoflow.core.config import ImportRoot, Settings
from astrophotoflow.core.database.schema import database_lock, initialize_database
from astrophotoflow.interfaces.http.app import create_app
from astrophotoflow.modules.data.assets.metadata import asset_parameters
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.equipment.models import EquipmentSetup
from astrophotoflow.modules.data.imports.models import AssetTask, AssetTaskItem
from astrophotoflow.modules.data.media.models import Preview
AUTH = {'Authorization': 'Bearer import-pipeline-test'}

def test_task_directory_omits_frozen_plans_and_batches_item_counts(service):
    _, app, client, _ = service
    task_id = str(uuid4())
    source = {'path': 'source.fits', 'header_snapshot': 'large-frozen-header' * 10000}
    with app.state.database.write_session() as session:
        session.add(AssetTask(id=task_id, status='completed', sources=[source], storage_mode='managed', classification={}, parameters={}, report={'registration': {'total': 2, 'registered': 2, 'completed': True}, 'internal_frozen_plan': 'private-large-plan' * 10000}, enumeration_completed=True))
        session.flush()
        for position, status in enumerate(('completed', 'failed')):
            item_id = str(uuid4())
            session.add(AssetTaskItem(id=item_id, task_id=task_id, root_item_id=item_id, root_id='', source_path=f'{position}.fits', source_identity=str(position), position=position, status=status))
    response = client.get('/api/v1/asset-tasks', headers=AUTH)
    assert response.status_code == 200
    summary = next((item for item in response.json()['items'] if item['id'] == task_id))
    assert summary['items_total'] == summary['items_completed'] == 2
    assert summary['report']['registration']['registered'] == 2
    assert 'sources' not in summary and 'items' not in summary
    assert 'internal_frozen_plan' not in summary['report']
    detail = client.get(f'/api/v1/asset-tasks/{task_id}', headers=AUTH)
    assert detail.status_code == 200
    assert detail.json()['sources'] == [source]
    assert len(detail.json()['items']) == 2

def test_direct_absolute_import_without_configured_roots_keeps_original_and_manages_copy(service):
    settings, app, client, root = service
    settings = replace(settings, import_roots=())
    app.state.settings = settings
    source = root / 'direct.fits'
    original = image(source, GAIN=0)
    response = client.post('/api/v1/imports', headers=AUTH, json={'sources': [{'path': str(source)}], 'storage_mode': 'managed'})
    assert response.status_code == 202
    result = task(client, response.json()['task_id'])
    assert result['status'] == 'completed'
    assert len(result['items']) == 1
    item = result['items'][0]
    assert item['root_id'] == ''
    asset = client.get(f"/api/v1/library/assets/{item['asset_id']}", headers=AUTH).json()
    copied = settings.data_dir / asset['storage_location']
    assert copied.read_bytes() == source.read_bytes() == original
    assert not copied.samefile(source)
    assert asset['content_hash'] == 'blake3:' + blake3.blake3(original).hexdigest()

def test_direct_folder_freezes_current_level_only_without_root_configuration(service, monkeypatch):
    settings, app, client, root = service
    app.state.settings = replace(settings, import_roots=())
    image(root / 'one.fits')
    image(root / 'nested/two.fits')
    monkeypatch.setattr('astrophotoflow.modules.data.public.run_import_task', lambda *args: None)
    response = client.post('/api/v1/imports', headers=AUTH, json={'sources': [{'path': str(root)}], 'storage_mode': 'managed'})
    assert response.status_code == 202
    image(root / 'late.fits')
    with app.state.database.read_session() as session:
        created = session.get(AssetTask, response.json()['task_id'])
        assert len(created.sources[0]['entries']) == 1
        entry = created.sources[0]['entries'][0]
        assert Path(entry['path']).name == 'one.fits'
        assert entry['source_stamp']['size'] > 0

def test_native_selection_cancellation_and_empty_roots_do_not_create_tasks(service, monkeypatch):
    settings, app, client, root = service
    app.state.settings = replace(settings, import_roots=())
    from astrophotoflow.modules.data.imports import sources as imports
    monkeypatch.setattr(imports, 'select_local_paths', lambda *args: [])
    response = client.post('/api/v1/imports/select-local', headers=AUTH, json={'mode': 'files'})
    assert response.status_code == 200
    assert response.json() == {'cancelled': True, 'files': [], 'name': None, 'folder': False}
    with app.state.database.read_session() as session:
        assert session.scalar(select(func.count()).select_from(AssetTask)) == 0
    image(root / 'native.fits')
    monkeypatch.setattr(imports, 'select_local_paths', lambda *args: [root])
    selected = client.post('/api/v1/imports/select-local', headers=AUTH, json={'mode': 'folder'})
    assert selected.status_code == 200
    assert selected.json()['files'][0]['path'] == str((root / 'native.fits').resolve())
    assert selected.json()['files'][0]['name'] == 'native.fits'
    assert client.post('/api/v1/imports', headers=AUTH, json={'sources': [{'path': 'relative.fits'}], 'storage_mode': 'managed'}).status_code == 422

def test_native_selection_busy_is_explicit_and_does_not_create_import_tasks(service, monkeypatch):
    _, app, client, _ = service
    from astrophotoflow.modules.data.imports import sources as imports
    from astrophotoflow.modules.data.local_selection import LocalSelectionBusy

    def busy(*args):
        raise LocalSelectionBusy('已有本机选择窗口打开。')
    monkeypatch.setattr(imports, 'select_local_paths', busy)
    response = client.post('/api/v1/imports/select-local', headers=AUTH, json={'mode': 'files'})
    assert response.status_code == 409
    assert response.json()['error']['code'] == 'LOCAL_PICKER_BUSY'
    with app.state.database.read_session() as session:
        assert session.scalar(select(func.count()).select_from(AssetTask)) == 0

def test_native_selection_disconnect_cancels_the_owned_chooser_without_importing(tmp_path, monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from astrophotoflow.contracts.imports import LocalSelectionRequest
    from astrophotoflow.interfaces.http.data.imports import select_local_import as request_selection
    from astrophotoflow.modules.data.imports import sources as imports
    stopped = Event()

    def choose(mode, initial_path, cancelled):
        assert cancelled.wait(3)
        stopped.set()
        return []
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(workspace=tmp_path))), is_disconnected=AsyncMock(return_value=True))
    monkeypatch.setattr(imports, 'select_local_paths', choose)
    result = asyncio.run(request_selection(LocalSelectionRequest(mode='files'), request))
    assert stopped.is_set()
    assert result.cancelled and (not result.files)

@pytest.mark.parametrize('change_stage', ['before_content', 'during_copy'])
def test_changed_external_source_cannot_publish_stale_registration(service, monkeypatch, change_stage):
    settings, app, client, root = service
    source = root / 'changing.fits'
    image(source, EXPTIME=30)
    before = source.stat()

    def change_source():
        with fits.open(source, mode='update') as hdus:
            hdus[0].header['EXPTIME'] = 99
        os.utime(source, ns=(before.st_atime_ns, before.st_mtime_ns + 1000000000))
    if change_stage == 'before_content':
        original = owner_stages.materialize_content

        def change_then_process(*args, **kwargs):
            change_source()
            return original(*args, **kwargs)
        monkeypatch.setattr(owner_stages, 'materialize_content', change_then_process)
    else:
        original = owner_stages.read_hash_and_copy

        def change_then_copy(*args, **kwargs):
            change_source()
            return original(*args, **kwargs)
        monkeypatch.setattr(owner_stages, 'read_hash_and_copy', change_then_copy)
    task_id = enqueue(app, [source.name])
    owner_runner.run_import_task(app.state.database, settings, task_id, app.state.import_workers)
    current = task(client, task_id)
    assert current['status'] == 'failed'
    item = current['items'][0]
    assert item['error']['code'] == 'SOURCE_CHANGED'
    assert item['content_status'] == 'failed'
    assert fits.getheader(source)['EXPTIME'] == 99
    asset = client.get(f"/api/v1/library/assets/{item['asset_id']}", headers=AUTH).json()
    assert asset['parameters']['exposure_seconds'] == 30
    assert asset['availability'] == 'changed'
    assert asset['content_hash'] is None
    assert not (settings.data_dir / asset['storage_location']).exists()
    assert not list((settings.data_dir / 'staging').rglob('*.part'))

def image(path, label='Light Frame', offset=0, **headers):
    path.parent.mkdir(parents=True, exist_ok=True)
    hdu = fits.PrimaryHDU(np.arange(120, dtype=np.float32).reshape(10, 12) + offset)
    if label is not None:
        hdu.header['IMAGETYP'] = label
    for key, value in headers.items():
        hdu.header[key] = value
    hdu.writeto(path)
    return path.read_bytes()

@pytest.fixture
def service(tmp_path, request):
    root = tmp_path / 'science'
    root.mkdir()
    settings = Settings('127.0.0.1', 8190, tmp_path / 'data', ('http://127.0.0.1:8188',), (ImportRoot('science', root),), **getattr(request, 'param', {}), workspace=tmp_path)
    with database_lock(settings):
        initialize_database(settings)
    app = create_app(settings, 'import-pipeline-test')
    with TestClient(app) as client:
        yield (settings, app, client, root)
    assert all((executor._shutdown for executor in app.state.import_workers))

def enqueue(app, paths=None, **changes):
    task_id = str(uuid4())
    values = dict(id=task_id, status='queued', sources=[{'root_id': 'science', 'path': path, 'enumeration_completed': False, 'kind': 'file'} for path in paths or ['']], storage_mode='managed', classification={}, parameters={}, notes=None, dataset_name='pending group', target_dataset_id=str(uuid4()), dataset_base_revision=None, dataset_id=None, enumeration_completed=False, retry_of_task_id=None, report={}, error=None)
    values.update(changes)
    with app.state.database.write_session() as session:
        session.add(AssetTask(**values))
    return task_id

def run(app, settings, task_id):
    thread = Thread(target=owner_runner.run_import_task, args=(app.state.database, settings, task_id, app.state.import_workers))
    thread.start()
    return thread

def requested_previews(app, settings, task_id, *, auto=False):
    """Explicitly open every member for tests that exercise pixel rendering."""
    display = owner_display.DisplayPreviews(app.state.database, settings, app.state.import_workers[1], recover=False)
    with app.state.database.read_session() as session:
        rows = list(session.scalars(select(AssetTaskItem).where(AssetTaskItem.task_id == task_id).order_by(AssetTaskItem.position)))
        versions = [row.asset_id for row in rows if row.content_status == 'available' and row.metadata_status != 'failed']
    for version_id in versions:
        state = display.schedule(version_id, auto=auto)
        deadline = time.monotonic() + 5
        while state['status'] == 'generating' and time.monotonic() < deadline:
            time.sleep(0.01)
            state = display.status(version_id)
        assert state['status'] != 'generating', state
    return display

def task(client, task_id):
    return client.get(f'/api/v1/asset-tasks/{task_id}', headers=AUTH).json()

def test_registration_publishes_pending_members_and_keeps_trash_protected(service, monkeypatch):
    settings, app, client, root = service
    original_bytes = [image(root / f'{i}.fits', GAIN=9) for i in range(2)]
    entered, release = (Event(), Event())
    read = owner_stages.read_hash_and_copy

    def blocked(*args):
        entered.set()
        assert release.wait(5)
        return read(*args)
    monkeypatch.setattr(owner_stages, 'read_hash_and_copy', blocked)
    task_id = enqueue(app)
    thread = run(app, settings, task_id)
    try:
        assert entered.wait(5)
        current = task(client, task_id)
        assert current['report']['registration'] == {'total': 2, 'registered': 2, 'completed': True}
        assert current['status'] == 'running'
        assert current['items_completed'] == 0
        entry = client.get('/api/v1/library/items', headers=AUTH).json()['items'][0]
        assert entry['entry_type'] == 'dataset'
        members = client.get(f"/api/v1/datasets/{entry['id']}/members", headers=AUTH).json()['items']
        assert len(members) == 2
        assert all((member['asset']['availability'] == 'unknown' for member in members))
        assert all((member['asset']['content_hash'] is None for member in members))
        first = members[0]
        assert client.get(f"/api/v1/library/assets/{first['asset']['id']}/previews/thumbnail", headers=AUTH).status_code == 404
        assert client.patch(f"/api/v1/library/assets/{first['asset']['id']}", headers=AUTH, json={'base_revision': 1, 'parameters': {'gain': None, 'offset': 0}}).status_code == 200
        dataset = entry
        removed = client.request('DELETE', '/api/v1/library/items', headers=AUTH, json={'items': [{'entry_type': 'dataset', 'id': dataset['id'], 'revision': dataset['revision']}]})
        assert removed.status_code == 200
        trash = client.get('/api/v1/library/trash', headers=AUTH).json()['items'][0]
        selection = {'items': [{key: trash[key] for key in ('entry_type', 'id', 'removed_at', 'revision')}]}
        preview = client.post('/api/v1/library/trash/delete-preview', headers=AUTH, json=selection).json()
        assert preview['tasks'] == [task_id]
        deletion = client.post('/api/v1/library/trash/delete', headers=AUTH, json={**selection, 'preview_fingerprint': preview['preview_fingerprint']})
        assert deletion.status_code == 409
        assert deletion.json()['error']['code'] == 'IMPORT_ACTIVE'
    finally:
        release.set()
        thread.join(5)
    assert not thread.is_alive()
    assert task(client, task_id)['status'] == 'completed'
    updated = client.get(f"/api/v1/library/assets/{first['asset']['id']}", headers=AUTH).json()
    assert updated['parameters']['gain'] is None
    assert updated['parameters']['offset'] == 0
    assert updated['capture_snapshot']['parameters']['gain'] == 9
    assert [path.read_bytes() for path in sorted(root.glob('*.fits'))] == original_bytes
    with app.state.database.read_session() as session:
        assert session.scalar(select(func.count()).select_from(Dataset)) == 1

@pytest.mark.parametrize('label,expected', [('Light Frame', {'frame_class': 'subframe', 'frame_type': 'light'}), ('MASTER DARK', {'frame_class': 'masterframe', 'frame_type': 'dark'}), ('Dark Flat Frame', {'frame_class': 'subframe', 'frame_type': 'dark_flat'}), ('dark', {'frame_class': None, 'frame_type': 'dark'}), (None, {'frame_class': None, 'frame_type': None}), ('something else', {'frame_class': None, 'frame_type': None})])
def test_header_classification_and_missing_fields(service, label, expected):
    _, _, client, root = service
    image(root / 'Master_Light_filename_is_not_evidence.fits', label)
    accepted = client.post('/api/v1/imports', headers=AUTH, json={'sources': [{'root_id': 'science', 'path': ''}], 'storage_mode': 'reference'})
    current = task(client, accepted.json()['task_id'])
    asset = client.get(f"/api/v1/library/assets/{current['items'][0]['asset_id']}", headers=AUTH).json()
    assert asset['classification'] == expected
    for key, value in expected.items():
        assert asset['value_sources'][f'classification.{key}'] == ('unknown' if value is None else 'file')
    if expected['frame_class'] is None:
        assert asset['calibration_level'] is None

def test_mixed_batch_manual_override_and_frozen_equipment_selection(service):
    settings, app, client, root = service
    image(root / 'a.fits', 'Light Frame', EXPTIME=11, GAIN=9, BAYERPAT='RGGB')
    image(root / 'b.fits', 'Master Dark', EXPTIME=12, GAIN=8)
    setup_id = str(uuid4())
    with app.state.database.write_session() as session:
        session.add(EquipmentSetup(id=setup_id, name='Setup', members=[]))
    equipment = {'choice': {'source': 'setup', 'setup_id': setup_id, 'expected_revision': 1}, 'fields': ['camera']}
    import astrophotoflow.modules.data.public as routes
    process = routes.run_import_task
    captured = []
    routes.run_import_task = lambda *args: captured.append(args)
    try:
        accepted = client.post('/api/v1/imports', headers=AUTH, json={'sources': [{'root_id': 'science', 'path': ''}], 'storage_mode': 'reference', 'equipment': equipment, 'parameters': {'gain': 0, 'offset': 7}})
    finally:
        routes.run_import_task = process
    task_id = accepted.json()['task_id']
    process(*captured[0])
    current = task(client, task_id)
    assets = [client.get(f"/api/v1/library/assets/{item['asset_id']}", headers=AUTH).json() for item in current['items']]
    assert [asset['classification']['frame_type'] for asset in assets] == ['light', 'dark']
    assert assets[0]['parameters']['gain'] == 0
    assert assets[0]['parameters']['offset'] == 7
    assert assets[0]['parameters']['exposure_seconds'] == 11
    assert assets[0]['parameters']['cfa_pattern'] == 'RGGB'
    assert assets[0]['value_sources']['gain'] == 'manual'
    assert assets[0]['value_sources']['offset'] == 'manual'
    assert assets[0]['value_sources']['exposure_seconds'] == 'file'
    assert assets[0]['value_sources']['iso'] == 'unknown'
    provenance = assets[0]['capture_snapshot']['import_provenance']
    assert provenance['defaults_snapshot']['equipment_setup']['id'] == setup_id
    before = deepcopy(assets[0]['capture_snapshot'])
    edited = client.patch(f"/api/v1/library/assets/{assets[0]['id']}", headers=AUTH, json={'base_revision': 1, 'parameters': {'gain': None}}).json()
    assert edited['capture_snapshot'] == before
    manual = client.post('/api/v1/imports', headers=AUTH, json={'sources': [{'root_id': 'science', 'path': ''}], 'storage_mode': 'reference', 'classification': {'frame_class': 'masterframe', 'frame_type': None}})
    overridden = task(client, manual.json()['task_id'])
    for item in overridden['items']:
        asset = client.get(f"/api/v1/library/assets/{item['asset_id']}", headers=AUTH).json()
        assert asset['classification'] == {'frame_class': 'masterframe', 'frame_type': None}
        assert asset['value_sources']['classification.frame_type'] == 'manual'

def test_service_worker_limits_are_shared_between_tasks(service, monkeypatch):
    settings, app, client, root = service
    for group in ('one', 'two'):
        for i in range(3):
            image(root / group / f'{i}.fits')
    counters = {'file': 0, 'preview': 0}
    peaks = {'file': 0, 'preview': 0}
    lock = Lock()

    def measured(kind, original):

        def wrapped(*args, **kwargs):
            with lock:
                counters[kind] += 1
                peaks[kind] = max(peaks[kind], counters[kind])
            try:
                time.sleep(0.03)
                return original(*args, **kwargs)
            finally:
                with lock:
                    counters[kind] -= 1
        return wrapped
    monkeypatch.setattr(owner_stages, 'read_hash_and_copy', measured('file', owner_stages.read_hash_and_copy))
    monkeypatch.setattr(owner_display.DisplayPreviews, '_render', measured('preview', owner_display.DisplayPreviews._render))
    ids = [enqueue(app, [group]) for group in ('one', 'two')]
    threads = [run(app, settings, task_id) for task_id in ids]
    for thread in threads:
        thread.join(10)
        assert not thread.is_alive()
    app.state.import_workers[1].submit(lambda: None).result()
    assert peaks == {'file': 2, 'preview': 1}
    assert all((task(client, task_id)['status'] == 'completed' for task_id in ids))

@pytest.mark.parametrize('service', [{'preview_workers': 2}], indirect=True)
def test_each_photo_stretches_independently_of_content_order_and_survives_resume(service, monkeypatch):
    settings, app, client, root = service
    for name, offset, filter_name in (('a', 0, 'L'), ('b', 1000, 'L'), ('c', 0, 'Ha'), ('d', 2000, 'Ha')):
        image(root / f'{name}.fits', offset=offset, FILTER=filter_name)
    with fits.open(root / 'c.fits', mode='update') as hdus:
        hdus[0].data[:] = np.nan
    completed = []
    read = owner_stages.read_hash_and_copy

    def out_of_order(path, *args):
        if path.name == 'a.fits':
            time.sleep(0.12)
        result = read(path, *args)
        completed.append(path.name)
        return result
    monkeypatch.setattr(owner_stages, 'read_hash_and_copy', out_of_order)
    task_id = enqueue(app)
    owner_runner.run_import_task(app.state.database, settings, task_id, app.state.import_workers)
    requested_previews(app, settings, task_id)
    current = task(client, task_id)
    assert completed.index('b.fits') < completed.index('a.fits')
    items = {Path(row['source_path']).stem: row for row in current['items']}
    with app.state.database.read_session() as session:
        displays = {name: session.scalar(select(Preview).where(Preview.size == 'thumbnail', Preview.asset_id == items[name]['asset_id'])).display_parameters for name in ('a', 'b', 'd')}
    assert displays['b']['auto_stretch']['highlights'] == pytest.approx(displays['a']['auto_stretch']['highlights'] + 1000)
    assert displays['d']['auto_stretch']['highlights'] == pytest.approx(displays['a']['auto_stretch']['highlights'] + 2000)
    assert all(('stretch_reference_asset_id' not in recipe and 'stretch_group' not in recipe for recipe in displays.values()))
    assert 'preview_stretch_groups' not in current['report']
    display = owner_display.DisplayPreviews(app.state.database, settings, app.state.import_workers[1], recover=False)
    assert display.status(items['c']['asset_id'])['status'] == 'failed'
    assert items['c']['preview_status'] == 'not_requested'
    with app.state.database.write_session() as session:
        preview = session.scalar(select(Preview).where(Preview.size == 'thumbnail', Preview.asset_id == items['b']['asset_id']))
        session.delete(preview)
        session.get(AssetTaskItem, items['b']['id']).status = 'running'
        session.get(AssetTaskItem, items['b']['id']).preview_status = 'pending'
        session.get(AssetTask, task_id).status = 'running'
    owner_runner.recover_import_tasks(app.state.database)
    assert client.post(f'/api/v1/asset-tasks/{task_id}/resume', headers=AUTH, json={}).status_code == 202
    requested_previews(app, settings, task_id)
    with app.state.database.read_session() as session:
        regenerated = session.scalar(select(Preview).where(Preview.size == 'thumbnail', Preview.asset_id == items['b']['asset_id']))
        assert regenerated.display_parameters == displays['b']
        assert session.scalar(select(func.count()).select_from(Asset)) == 4
        assert session.scalar(select(func.count()).select_from(Dataset)) == 1

def test_upload_renames_without_second_write_and_recovers_identity_after_rename_failure(service, monkeypatch):
    settings, app, client, root = service
    data = image(root / 'upload.fits')
    created = client.post('/api/v1/uploads', headers=AUTH, json={'files': [{'name': 'upload.fits', 'size': len(data)}]})
    task_id = created.json()['task_id']
    assert client.put(f'/api/v1/uploads/{task_id}/0', headers=AUTH, content=data).status_code == 200
    read, replace = (owner_stages.read_hash_and_copy, owner_stages.os.replace)
    reads = []

    def hash_only(path, stage, cancelled, progress=None):
        assert stage is None
        reads.append(path)
        return read(path, stage, cancelled, progress)

    def crash_after_rename(source, destination):
        replace(source, destination)
        if Path(destination).parent.parent.name == 'objects':
            raise RuntimeError('interrupted after object rename')
    monkeypatch.setattr(owner_stages, 'read_hash_and_copy', hash_only)
    monkeypatch.setattr(owner_stages.os, 'replace', crash_after_rename)
    client.post(f'/api/v1/uploads/{task_id}/start', headers=AUTH, json={})
    failed = task(client, task_id)
    item = failed['items'][0]
    assert item['content_status'] == 'failed'
    with app.state.database.read_session() as session:
        version = session.get(Asset, item['asset_id'])
        path = settings.data_dir / version.storage_location
        assert version.availability == 'unknown'
    assert path.read_bytes() == data
    monkeypatch.setattr(owner_stages.os, 'replace', replace)
    retried = client.post(f'/api/v1/asset-tasks/{task_id}/retry', headers=AUTH, json={'item_ids': [item['id']]})
    recovered = task(client, retried.json()['task_id'])
    assert recovered['status'] == 'completed'
    assert recovered['items'][0]['asset_id'] == item['asset_id']
    assert recovered['items'][0]['asset_id'] == item['asset_id']
    assert reads[-1] == path
    assert not (settings.data_dir / 'upload-staging' / task_id / '0.fits').exists()
    with app.state.database.read_session() as session:
        version = session.get(Asset, item['asset_id'])
        assert version.content_hash == 'blake3:' + blake3.blake3(data).hexdigest()
        assert session.scalar(select(func.count()).select_from(Asset)) == 1

def test_cancelled_managed_copy_retries_registered_identity_and_preserves_source(service, monkeypatch):
    settings, app, client, root = service
    data = image(root / 'original.fits')
    task_id = enqueue(app)
    read = owner_stages.read_hash_and_copy

    def cancel_copy(path, stage, cancelled, progress=None):
        stage.write_bytes(b'partial')
        with app.state.database.write_session() as session:
            session.get(AssetTask, task_id).status = 'cancelling'
        raise owner_errors.IngestionError('CANCELLED', 'cancel injected', message_key='import_cancelled')
    monkeypatch.setattr(owner_stages, 'read_hash_and_copy', cancel_copy)
    owner_runner.run_import_task(app.state.database, settings, task_id, app.state.import_workers)
    cancelled = task(client, task_id)
    assert cancelled['status'] == 'cancelled'
    item = cancelled['items'][0]
    assert item['asset_id'] and item['content_status'] == 'pending'
    assert not list((settings.data_dir / 'staging').rglob('*.part'))
    assert (root / 'original.fits').read_bytes() == data
    monkeypatch.setattr(owner_stages, 'read_hash_and_copy', read)
    retried = client.post(f'/api/v1/asset-tasks/{task_id}/retry', headers=AUTH, json={'item_ids': [item['id']]})
    recovered = task(client, retried.json()['task_id'])
    assert recovered['status'] == 'completed'
    assert recovered['items'][0]['asset_id'] == item['asset_id']
    assert (root / 'original.fits').read_bytes() == data
    with app.state.database.read_session() as session:
        assert session.scalar(select(func.count()).select_from(Asset)) == 1
        assert session.scalar(select(func.count()).select_from(Dataset)) == 1

def test_upload_accepts_explicit_parameters_before_task_items_are_flushed(service):
    _, app, client, _ = service
    accepted = client.post('/api/v1/uploads', headers=AUTH, json={'files': [{'name': 'one.fits', 'size': 100}, {'name': 'two.fits', 'size': 100}], 'parameters': {'parameter_mode': 'gain', 'gain': 19}})
    assert accepted.status_code == 202, accepted.text
    with app.state.database.read_session() as session:
        row = session.get(AssetTask, accepted.json()['task_id'])
        assert row.parameters['gain'] == 19
        assert session.scalar(select(func.count()).select_from(AssetTaskItem)) == 2

def test_resume_after_registration_keeps_identity_snapshot_and_input_bytes(service):
    settings, app, client, root = service
    data = image(root / 'resume.fits', GAIN=4)
    task_id = enqueue(app)
    with app.state.database.write_session() as session:
        session.get(AssetTask, task_id).status = 'running'
    from astrophotoflow.modules.data.imports.context import ImportTaskContext
    with app.state.database.read_session() as session:
        task_data = ImportTaskContext.from_task(session.get(AssetTask, task_id))
    task_data.sources = [{'root_id': 'science', 'path': '', 'enumeration_completed': False}]
    task_data.parameters, task_data.classification = ({}, {})
    task_data.import_defaults_snapshot = {'parameters': {'offset': 8}}
    owner_enumeration.enumerate_task(app.state.database, settings, task_id, task_data.sources, upload_manifest=task_data.upload_manifest)
    current = task(client, task_id)
    item_id = current['items'][0]['id']
    owner_stages.register_asset(app.state.database, settings, task_data, item_id)
    before = task(client, task_id)['items'][0]
    with app.state.database.read_session() as session:
        snapshot = deepcopy(session.get(Asset, before['asset_id']).capture_snapshot)
    assert owner_runner.recover_import_tasks(app.state.database) == 1
    response = client.post(f'/api/v1/asset-tasks/{task_id}/resume', headers=AUTH, json={})
    assert response.status_code == 202
    recovered = task(client, task_id)
    assert recovered['status'] == 'completed'
    assert recovered['items'][0]['asset_id'] == before['asset_id']
    assert recovered['items'][0]['asset_id'] == before['asset_id']
    assert (root / 'resume.fits').read_bytes() == data
    with app.state.database.read_session() as session:
        assert session.get(Asset, before['asset_id']).capture_snapshot == snapshot
        assert session.scalar(select(func.count()).select_from(Asset)) == 1

def test_service_shutdown_drains_submitted_file_and_preview_jobs(service):
    settings, _, _, _ = service
    app = create_app(settings, 'import-pipeline-test')
    client = TestClient(app)
    client.__enter__()
    entered = [Event(), Event()]
    release, exited = (Event(), Event())

    def blocked(index):
        entered[index].set()
        assert release.wait(5)
        return index
    futures = [executor.submit(blocked, index) for index, executor in enumerate(app.state.import_workers)]
    assert all((event.wait(5) for event in entered))

    def close():
        client.__exit__(None, None, None)
        exited.set()
    thread = Thread(target=close)
    thread.start()
    try:
        assert not exited.wait(0.05)
    finally:
        release.set()
        thread.join(5)
    assert exited.is_set()
    assert [future.result() for future in futures] == [0, 1]
    assert all((executor._shutdown for executor in app.state.import_workers))

def test_preview_retry_computes_failed_photos_own_stretch_and_keeps_other_recipe(service, monkeypatch):
    settings, app, client, root = service
    image(root / 'a.fits')
    image(root / 'b.fits', offset=1000)
    render = owner_display.DisplayPreviews._render

    def fail_first(self, job):
        if job['path'].name == 'a.fits':
            raise ValueError('injected first preview failure')
        return render(self, job)
    monkeypatch.setattr(owner_display.DisplayPreviews, '_render', fail_first)
    task_id = enqueue(app, storage_mode='reference')
    owner_runner.run_import_task(app.state.database, settings, task_id, app.state.import_workers)
    display = requested_previews(app, settings, task_id)
    original = task(client, task_id)
    first, second = original['items']
    assert original['status'] == 'completed'
    assert display.status(first['asset_id'])['status'] == 'failed'
    assert display.status(second['asset_id'])['status'] == 'available'
    assert first['preview_status'] == second['preview_status'] == 'not_requested'
    with app.state.database.read_session() as session:
        other_recipe = dict(session.scalar(select(Preview).where(Preview.asset_id == second['asset_id'], Preview.size == 'thumbnail')).display_parameters)
    monkeypatch.setattr(owner_display.DisplayPreviews, '_render', render)
    requested_previews(app, settings, task_id)
    assert display.status(first['asset_id'])['status'] == 'available'
    with app.state.database.read_session() as session:
        preview = session.scalar(select(Preview).where(Preview.asset_id == first['asset_id'], Preview.size == 'thumbnail'))
        assert preview.display_parameters['auto_stretch']['highlights'] == pytest.approx(other_recipe['auto_stretch']['highlights'] - 1000)
        assert 'stretch_reference_asset_id' not in preview.display_parameters
        assert session.scalar(select(Preview).where(Preview.asset_id == second['asset_id'], Preview.size == 'thumbnail')).display_parameters == other_recipe
        assert session.scalar(select(func.count()).select_from(Asset)) == 2

@pytest.mark.parametrize('service', [{'preview_workers': 2}], indirect=True)
def test_second_preview_can_finish_while_first_is_blocked(service, monkeypatch):
    settings, app, client, root = service
    image(root / 'a.fits')
    image(root / 'b.fits', offset=1000)
    entered, release = (Event(), Event())
    render = owner_display.DisplayPreviews._render

    def blocked(self, job):
        if job['path'].name == 'a.fits':
            entered.set()
            assert release.wait(5)
        return render(self, job)
    monkeypatch.setattr(owner_display.DisplayPreviews, '_render', blocked)
    task_id = enqueue(app, storage_mode='reference')
    thread = run(app, settings, task_id)
    try:
        assert entered.wait(3)
        current = task(client, task_id)
        assert current['status'] == 'completed'
        second = current['items'][1]
        display = owner_display.DisplayPreviews(app.state.database, settings, app.state.import_workers[1], recover=False)
        display.schedule(second['asset_id'])
        deadline = time.monotonic() + 3
        while display.status(second['asset_id'])['status'] == 'generating' and time.monotonic() < deadline:
            time.sleep(0.01)
        assert display.status(second['asset_id'])['status'] == 'available'
        assert task(client, task_id)['status'] == 'completed'
    finally:
        release.set()
        thread.join(5)
    assert not thread.is_alive()

@pytest.mark.parametrize('service', [{'preview_workers': 2}], indirect=True)
@pytest.mark.parametrize('category', ['fits', 'xisf'])
def test_folder_subframes_reuse_first_object_recipe_and_masters_measure_independently(service, monkeypatch, category):
    from xisf import XISF
    from astrophotoflow.modules.data.formats import fits as codec_formats_fits
    settings, app, client, root = service
    cases = [('a', 'Light Frame', ' M42 ', 0), ('b', 'Light Frame', 'm42', 1000), ('c', 'Master Light', 'M42', 2000), ('d', 'Master Light', 'M42', 3000), ('e', 'Light Frame', 'M31', 4000), ('f', 'Light Frame', 'M31', 5000), ('g', 'Light Frame', None, 6000), ('h', 'Light Frame', None, 7000)]
    originals = {}
    for name, label, target, offset in cases:
        path = root / f'{name}.{category}'
        if category == 'fits':
            image(path, label=label, offset=offset, **{'OBJECT': target} if target is not None else {})
        else:
            keywords = {'IMAGETYP': [{'value': label, 'comment': ''}]}
            if target is not None:
                keywords['OBJECT'] = [{'value': target, 'comment': ''}]
            XISF.write(str(path), (np.arange(120, dtype=np.float32).reshape(10, 12) + offset)[..., None], image_metadata={'FITSKeywords': keywords})
        originals[path] = path.read_bytes()
    measured = []
    module = owner_display
    calculate = module.calculate_stretch

    def counted(pixels):
        measured.append(float(np.min(pixels)))
        return calculate(pixels)
    monkeypatch.setattr(module, 'calculate_stretch', counted)
    task_id = enqueue(app, paths=[f'{name}.{category}' for name, *_ in cases])
    owner_runner.run_import_task(app.state.database, settings, task_id, app.state.import_workers)
    requested_previews(app, settings, task_id)
    result = task(client, task_id)
    assert result['status'] == 'completed_with_errors'
    assert {item['name'] for item in result['report']['dataset_exclusions']} == {f'c.{category}', f'd.{category}'}
    with app.state.database.read_session() as session:
        recipes = [session.scalar(select(Preview).where(Preview.size == 'thumbnail', Preview.asset_id == item['asset_id'])).display_parameters for item in result['items']]
    assert sorted(measured) == [0, 2000, 3000, 4000, 6000, 7000]
    assert recipes[0]['auto_stretch'] == recipes[1]['auto_stretch']
    assert recipes[1]['stretch_reference_asset_id'] == result['items'][0]['asset_id']
    assert recipes[4]['auto_stretch'] == recipes[5]['auto_stretch']
    assert recipes[5]['stretch_reference_asset_id'] == result['items'][4]['asset_id']
    assert recipes[0]['stretch_group'] != recipes[4]['stretch_group']
    assert recipes[2]['auto_stretch'] != recipes[3]['auto_stretch']
    assert all(('stretch_group' not in recipes[index] for index in (2, 3, 6, 7)))
    assert len(result['report']['preview_stretch_groups']) == 2
    assert all((path.read_bytes() == data for path, data in originals.items()))

def test_same_object_in_different_folders_or_incompatible_layouts_never_shares_recipe(service):
    settings, app, client, root = service
    image(root / 'one/a.fits', OBJECT='M42')
    image(root / 'two/b.fits', OBJECT='M42', offset=1000)
    hdu = fits.PrimaryHDU(np.stack([np.arange(120, dtype=np.float32).reshape(10, 12) + value for value in (10, 20, 40)]))
    hdu.header['CTYPE3'] = 'RGB'
    hdu.header['OBJECT'], hdu.header['IMAGETYP'] = ('M42', 'Light Frame')
    hdu.writeto(root / 'one/rgb.fits')
    task_id = enqueue(app, paths=['one/a.fits', 'two/b.fits', 'one/rgb.fits'])
    owner_runner.run_import_task(app.state.database, settings, task_id, app.state.import_workers)
    requested_previews(app, settings, task_id)
    result = task(client, task_id)
    assert result['status'] == 'completed'
    assert len(result['report']['preview_stretch_groups']) == 3
    with app.state.database.read_session() as session:
        for item in result['items']:
            recipe = session.scalar(select(Preview).where(Preview.size == 'thumbnail', Preview.asset_id == item['asset_id'])).display_parameters
            assert recipe['stretch_reference_asset_id'] == item['asset_id']

def test_first_failed_subframe_uses_next_valid_frame_then_retry_and_backfill_keep_shared_recipe(service, monkeypatch):
    settings, app, client, root = service
    for name, offset in (('a', 0), ('b', 1000), ('c', 2000)):
        image(root / f'{name}.fits', OBJECT='M42', offset=offset)
    render = owner_display.DisplayPreviews._render

    def fail_first(self, job):
        if job['path'].name == 'a.fits':
            raise ValueError('controlled first-frame failure')
        return render(self, job)
    monkeypatch.setattr(owner_display.DisplayPreviews, '_render', fail_first)
    task_id = enqueue(app, storage_mode='reference')
    owner_runner.run_import_task(app.state.database, settings, task_id, app.state.import_workers)
    original = task(client, task_id)
    assert original['status'] == 'completed'
    assert original['items'][1]['preview_status'] == 'not_requested'
    requested_previews(app, settings, task_id)
    original = task(client, task_id)
    first, second, third = original['items']
    display = owner_display.DisplayPreviews(app.state.database, settings, app.state.import_workers[1], recover=False)
    assert display.status(first['asset_id'])['status'] == 'failed'
    assert display.status(second['asset_id'])['status'] == display.status(third['asset_id'])['status'] == 'available'
    assert all((item['preview_status'] == 'not_requested' for item in original['items']))
    monkeypatch.setattr(owner_display.DisplayPreviews, '_render', render)

    def no_measurement(*_args, **_kwargs):
        raise AssertionError('a saved group recipe must be reused')
    monkeypatch.setattr(owner_display, 'calculate_stretch', no_measurement)
    requested_previews(app, settings, task_id)
    with app.state.database.write_session() as session:
        row = session.scalar(select(Preview).where(Preview.asset_id == third['asset_id'], Preview.size == 'thumbnail'))
        recipe = dict(row.display_parameters)
        assert recipe['stretch_reference_asset_id'] == second['asset_id']
        session.delete(row)
    (root / 'b.fits').unlink()
    assert owner_import_previews.backfill_missing_previews(app.state.database, settings) == {'generated': 1, 'failed': 0}
    with app.state.database.read_session() as session:
        restored = session.scalar(select(Preview).where(Preview.asset_id == third['asset_id'], Preview.size == 'thumbnail')).display_parameters
        assert restored['auto_stretch'] == recipe['auto_stretch']
        assert restored['stretch_reference_asset_id'] == recipe['stretch_reference_asset_id']
        assert session.scalar(select(func.count()).select_from(Asset)) == 3

def test_resume_recovers_first_subframe_recipe_from_published_thumbnail_after_report_gap(service, monkeypatch):
    from astrophotoflow.modules.data.formats import fits as codec_formats_fits
    settings, app, client, root = service
    image(root / 'a.fits', OBJECT='M42')
    image(root / 'b.fits', OBJECT='M42', offset=1000)
    task_id = enqueue(app)
    owner_runner.run_import_task(app.state.database, settings, task_id, app.state.import_workers)
    requested_previews(app, settings, task_id)
    result = task(client, task_id)
    first, second = result['items']
    with app.state.database.write_session() as session:
        row = session.scalar(select(Preview).where(Preview.size == 'thumbnail', Preview.asset_id == second['asset_id']))
        recipe = dict(row.display_parameters)
        session.delete(row)
        item = session.get(AssetTaskItem, second['id'])
        item.preview_status, item.status = ('pending', 'interrupted')
        current = session.get(AssetTask, task_id)
        current.status = 'running'
        current.report = {key: value for key, value in current.report.items() if key != 'preview_stretch_groups'}

    def no_measurement(*args, **kwargs):
        raise AssertionError('the first published thumbnail owns the measured values')
    monkeypatch.setattr(owner_display, 'calculate_stretch', no_measurement)
    owner_runner.run_import_task(app.state.database, settings, task_id, app.state.import_workers)
    requested_previews(app, settings, task_id)
    assert task(client, task_id)['status'] == 'completed'
    with app.state.database.read_session() as session:
        restored = session.scalar(select(Preview).where(Preview.size == 'thumbnail', Preview.asset_id == second['asset_id']))
        assert restored.display_parameters == recipe
        assert restored.display_parameters['stretch_reference_asset_id'] == first['asset_id']

def test_backfill_after_all_group_previews_failed_uses_fixed_member_order_without_rewriting_history(service, monkeypatch):
    from astrophotoflow.modules.data.formats import fits as codec_formats_fits
    settings, app, client, root = service
    image(root / 'a.fits', OBJECT='M42')
    image(root / 'b.fits', OBJECT='M42', offset=1000)
    render = owner_display.DisplayPreviews._render

    def failed(*_args, **_kwargs):
        raise ValueError('controlled preview outage')
    monkeypatch.setattr(owner_display.DisplayPreviews, '_render', failed)
    task_id = enqueue(app, paths=['b.fits', 'a.fits'])
    owner_runner.run_import_task(app.state.database, settings, task_id, app.state.import_workers)
    requested_previews(app, settings, task_id)
    original = task(client, task_id)
    assert original['status'] == 'completed'
    first, second = original['items']
    display = owner_display.DisplayPreviews(app.state.database, settings, app.state.import_workers[1], recover=False)
    assert all((display.status(item['asset_id'])['status'] == 'failed' for item in original['items']))
    assert all((item['preview_status'] == 'not_requested' for item in original['items']))
    monkeypatch.setattr(owner_display.DisplayPreviews, '_render', render)
    calculate = codec_formats_fits.calculate_stretch
    measured = []

    def counted(pixels):
        measured.append(float(np.min(pixels)))
        return calculate(pixels)
    monkeypatch.setattr(codec_formats_fits, 'calculate_stretch', counted)
    assert owner_import_previews.backfill_missing_previews(app.state.database, settings) == {'generated': 2, 'failed': 0}
    assert measured == [1000]
    with app.state.database.read_session() as session:
        for item in (first, second):
            recipe = session.scalar(select(Preview).where(Preview.asset_id == item['asset_id'], Preview.size == 'thumbnail')).display_parameters
            assert recipe['stretch_reference_asset_id'] == first['asset_id']
    assert task(client, task_id) == original

@pytest.mark.parametrize('category', ['fits', 'xisf', 'tif'])
def test_import_and_missing_cache_backfill_use_each_photos_own_range(service, category):
    from PIL import Image
    from xisf import XISF
    settings, app, client, root = service
    originals = {}
    for name, offset in (('a', 0), ('b', 1000)):
        path = root / f'{name}.{category}'
        values = np.arange(120, dtype=np.uint16).reshape(10, 12) + offset
        if category == 'fits':
            fits.PrimaryHDU(values).writeto(path)
        elif category == 'xisf':
            XISF.write(str(path), values[..., None])
        else:
            Image.fromarray(values).save(path)
        originals[path] = path.read_bytes()
    task_id = enqueue(app, target_dataset_id=None, dataset_name=None)
    owner_runner.run_import_task(app.state.database, settings, task_id, app.state.import_workers)
    requested_previews(app, settings, task_id)
    current = task(client, task_id)
    assert current['status'] == 'completed'
    first, second = current['items']
    with app.state.database.write_session() as session:
        rows = [session.scalar(select(Preview).where(Preview.size == 'thumbnail', Preview.asset_id == item['asset_id'])) for item in (first, second)]
        recipes = [dict(row.display_parameters) for row in rows]
        assert recipes[1]['stretch_low'] == pytest.approx(recipes[0]['stretch_low'] + 1000)
        session.delete(rows[1])
    assert owner_import_previews.backfill_missing_previews(app.state.database, settings) == {'generated': 1, 'failed': 0}
    with app.state.database.read_session() as session:
        for item, recipe in zip((first, second), recipes):
            restored = session.scalar(select(Preview).where(Preview.size == 'thumbnail', Preview.asset_id == item['asset_id'])).display_parameters
            assert {key: restored[key] for key in ('stretch_low', 'stretch_high')} == {key: recipe[key] for key in ('stretch_low', 'stretch_high')}
            assert 'stretch_reference_asset_id' not in restored
    assert task(client, task_id) == current
    assert all((path.read_bytes() == data for path, data in originals.items()))

@pytest.mark.parametrize('category', ['xisf', 'tif'])
def test_high_depth_thumbnail_maps_only_preview_sized_pixels(tmp_path, monkeypatch, category):
    from PIL import Image
    from xisf import XISF
    values = np.arange(1200 * 1600, dtype=np.uint16).reshape(1200, 1600)
    path = tmp_path / f'large.{category}'
    if category == 'xisf':
        XISF.write(str(path), values[..., None])
        decode = owner_stages.read_xisf_preview
    else:
        Image.fromarray(values).save(path)
        decode = owner_stages.read_raster_preview
    original = path.read_bytes()
    module = codec_formats_xisf if category == 'xisf' else codec_formats_raster
    display = module.display_pixels
    sizes = []

    def counted(pixels, stretch):
        sizes.append(pixels.shape)
        return display(pixels, stretch)
    monkeypatch.setattr(module, 'display_pixels', counted)
    thumbnail, recipe = decode(path)
    assert thumbnail.size == (100, 75)
    assert sizes == [(150, 200)]
    large, large_recipe = decode(path, (recipe['stretch_low'], recipe['stretch_high']), 1080)
    assert large.size == (1080, 810)
    assert large_recipe == recipe
    assert path.read_bytes() == original

def test_xisf_headers_register_without_pixels_and_preserve_explicit_overrides(service, monkeypatch):
    from xisf import XISF
    settings, app, client, root = service
    keywords = {'IMAGETYP': [{'value': 'Master Light', 'comment': 'Type of image'}], 'EXPTIME': [{'value': '300.000', 'comment': 'Exposure seconds'}], 'GAIN': [{'value': '9', 'comment': 'Observed gain'}], 'FILTER': [{'value': 'O', 'comment': 'Observed filter'}]}
    path = root / 'observed.xisf'
    XISF.write(str(path), np.arange(120, dtype=np.float32).reshape(10, 12, 1), image_metadata={'FITSKeywords': keywords})
    defaults = {'parameters': {'exposure_seconds': 60, 'gain': 50, 'offset': 7}, 'classification': {'frame_class': 'subframe', 'frame_type': 'dark'}}
    task_id = enqueue(app, target_dataset_id=None, dataset_name=None, import_defaults_snapshot=defaults, parameters={'gain': 0})
    entered, release = (Event(), Event())
    read = owner_stages.read_hash_and_copy

    def blocked(*args):
        entered.set()
        assert release.wait(5)
        return read(*args)
    original_pixels = XISF.read_image
    pixel_calls = []

    def pixels(*args, **kwargs):
        pixel_calls.append(1)
        return original_pixels(*args, **kwargs)
    monkeypatch.setattr(owner_stages, 'read_hash_and_copy', blocked)
    monkeypatch.setattr(XISF, 'read_image', pixels)
    thread = run(app, settings, task_id)
    try:
        assert entered.wait(5)
        assert pixel_calls == []
        item = task(client, task_id)['items'][0]
        asset = client.get(f"/api/v1/library/assets/{item['asset_id']}", headers=AUTH).json()
        assert asset['classification'] == {'frame_class': 'masterframe', 'frame_type': 'light'}
        assert asset['parameters']['exposure_seconds'] == 300
        assert asset['parameters']['gain'] == 0
        assert asset['parameters']['offset'] == 7
        assert asset['parameters']['iso'] is None
        assert asset['value_sources']['exposure_seconds'] == 'file'
        observed = asset['scientific_metadata']['observed_parameters']
        assert observed['xisf_fits_keywords'] == keywords
        assert observed['filter_name'] == 'O'
        assert asset['capture_snapshot']['import_provenance']['observed_parameters'] == observed
        assert item['metadata_status'] == 'available'
    finally:
        release.set()
        thread.join(5)
    assert task(client, task_id)['status'] == 'completed'
    monkeypatch.setattr(owner_stages, 'read_hash_and_copy', read)
    manual_id = enqueue(app, target_dataset_id=None, dataset_name=None, import_defaults_snapshot=defaults, classification={'frame_class': 'subframe', 'frame_type': None}, parameters={'exposure_seconds': 0})
    owner_runner.run_import_task(app.state.database, settings, manual_id, app.state.import_workers)
    item = task(client, manual_id)['items'][0]
    asset = client.get(f"/api/v1/library/assets/{item['asset_id']}", headers=AUTH).json()
    assert asset['classification'] == {'frame_class': 'subframe', 'frame_type': None}
    assert asset['parameters']['exposure_seconds'] == 0
    assert asset['value_sources']['classification.frame_type'] == 'manual'

def test_xisf_missing_headers_remain_unknown_and_metadata_failure_retries(service, monkeypatch):
    from xisf import XISF
    settings, app, client, root = service
    XISF.write(str(root / 'unknown.xisf'), np.ones((10, 12, 1), dtype=np.float32))
    task_id = enqueue(app, target_dataset_id=None, dataset_name=None)
    owner_runner.run_import_task(app.state.database, settings, task_id, app.state.import_workers)
    item = task(client, task_id)['items'][0]
    asset = client.get(f"/api/v1/library/assets/{item['asset_id']}", headers=AUTH).json()
    assert asset['classification'] == {'frame_class': None, 'frame_type': None}
    assert asset['parameters']['exposure_seconds'] is None
    inspect = owner_stages.inspect_xisf

    def failed(_path):
        raise ValueError('injected XISF metadata failure')
    monkeypatch.setattr(owner_stages, 'inspect_xisf', failed)
    failed_id = enqueue(app, target_dataset_id=None, dataset_name=None)
    owner_runner.run_import_task(app.state.database, settings, failed_id, app.state.import_workers)
    item = task(client, failed_id)['items'][0]
    assert item['metadata_status'] == 'failed'
    assert item['preview_status'] == 'not_requested'
    assert item['error']['code'] == 'XISF_PARSE_FAILED'
    monkeypatch.setattr(owner_stages, 'inspect_xisf', inspect)
    retried = client.post(f'/api/v1/asset-tasks/{failed_id}/retry', headers=AUTH, json={'item_ids': [item['id']]})
    recovered = task(client, retried.json()['task_id'])
    assert recovered['status'] == 'completed'
    assert recovered['items'][0]['asset_id'] == item['asset_id']
    assert recovered['items'][0]['metadata_status'] == 'available'

@pytest.mark.parametrize(('file_cfa', 'supplied_cfa', 'manual_cfa', 'expected_cfa', 'expected_source', 'expected_kind'), [('RGGB', 'MONO', None, 'MONO', 'manual', 'mono'), (None, 'RGGB', None, 'RGGB', 'manual', 'bayer'), ('RGGB', 'BGGR', 'MONO', 'MONO', 'manual', 'mono'), ('BGGR', 'MONO', 'RGGB', 'RGGB', 'manual', 'bayer')])
def test_fits_metadata_retry_preserves_cfa_precedence_and_frozen_snapshot(service, monkeypatch, file_cfa, supplied_cfa, manual_cfa, expected_cfa, expected_source, expected_kind):
    from astrophotoflow.modules.data.assets.models import FitsHduMetadata
    settings, app, client, root = service
    original_bytes = image(root / 'retry.fits', **{'BAYERPAT': file_cfa} if file_cfa else {})
    from astrophotoflow.contracts.snapshots import ImportDefaultsSnapshot
    monkeypatch.setattr('astrophotoflow.modules.data.imports.submission.capture_defaults_snapshot', lambda *_args: ImportDefaultsSnapshot(parameters={'cfa_pattern': supplied_cfa}))
    inspect = owner_stages.inspect_fits

    def failed(*_args, **_kwargs):
        raise OSError('controlled initial header failure')
    monkeypatch.setattr(owner_stages, 'inspect_fits', failed)
    accepted = client.post('/api/v1/imports', headers=AUTH, json={'sources': [{'root_id': 'science', 'path': 'retry.fits'}], 'storage_mode': 'managed'})
    assert accepted.status_code == 202, accepted.text
    original_task = task(client, accepted.json()['task_id'])
    original_item = original_task['items'][0]
    assert original_item['metadata_status'] == 'failed'
    with app.state.database.read_session() as session:
        snapshot = deepcopy(session.get(Asset, original_item['asset_id']).capture_snapshot)
    if manual_cfa is not None:
        edited = client.patch(f"/api/v1/library/assets/{original_item['asset_id']}", headers=AUTH, json={'base_revision': 1, 'parameters': {'cfa_pattern': manual_cfa}})
        assert edited.status_code == 200, edited.text
    monkeypatch.setattr(owner_stages, 'inspect_fits', inspect)
    retried = client.post(f"/api/v1/asset-tasks/{original_task['id']}/retry", headers=AUTH, json={'item_ids': [original_item['id']]})
    assert retried.status_code == 202, retried.text
    recovered = task(client, retried.json()['task_id'])
    requested_previews(app, settings, retried.json()['task_id'])
    assert recovered['status'] == 'completed'
    item = recovered['items'][0]
    assert item['asset_id'] == original_item['asset_id']
    assert item['asset_id'] == original_item['asset_id']
    with app.state.database.read_session() as session:
        asset = session.get(Asset, item['asset_id'])
        version = session.get(Asset, item['asset_id'])
        hdu = session.scalar(select(FitsHduMetadata).where(FitsHduMetadata.asset_id == version.id, FitsHduMetadata.is_selected.is_(True)))
        preview = session.scalar(select(Preview).where(Preview.size == 'thumbnail', Preview.asset_id == version.id, Preview.size == 'thumbnail'))
        assert asset_parameters(asset)['cfa_pattern'] == expected_cfa
        assert asset.value_sources['cfa_pattern'] == expected_source
        assert hdu.supported_kind == expected_kind
        assert preview.display_parameters['cfa_pattern'] == (expected_cfa if expected_kind == 'bayer' else None)
        assert version.scientific_metadata['observed_parameters'].get('cfa_pattern') == file_cfa
        assert version.capture_snapshot == snapshot
        assert asset.revision == (2 if manual_cfa is not None else 1)
        assert (settings.data_dir / version.storage_location).read_bytes() == original_bytes
    assert (root / 'retry.fits').read_bytes() == original_bytes

def test_local_task_freezes_accepted_scope_and_source_stamp(service, monkeypatch):
    settings, app, client, root = service
    original = image(root / 'first.fits', EXPTIME=30)
    monkeypatch.setattr('astrophotoflow.modules.data.public.run_import_task', lambda *_args: None)
    response = client.post('/api/v1/imports', headers=AUTH, json={'sources': [{'root_id': 'science', 'path': ''}], 'storage_mode': 'managed'})
    assert response.status_code == 202
    task_id = response.json()['task_id']
    image(root / 'arrived-later.fits')
    owner_runner.run_import_task(app.state.database, settings, task_id, app.state.import_workers)
    result = task(client, task_id)
    assert [item['source_path'] for item in result['items']] == ['first.fits']
    assert result['report']['content'] == {'total': 1, 'succeeded': 1, 'failed': 0, 'skipped': 0, 'metadata_failed': 0, 'bytes_total': len(original), 'bytes_copied': len(original), 'completed': True}
    assert result['report']['preview']['completed'] is False
    assert (root / 'first.fits').read_bytes() == original
    with app.state.database.read_session() as session:
        version = session.get(Asset, result['items'][0]['asset_id'])
        assert version.content_hash == 'blake3:' + blake3.blake3(original).hexdigest()
        destination = settings.data_dir / version.storage_location
    assert destination.read_bytes() == original
    assert not os.path.samefile(root / 'first.fits', destination)

def test_changed_source_after_acceptance_is_not_silently_imported(service, monkeypatch):
    settings, app, client, root = service
    image(root / 'changing.fits')
    monkeypatch.setattr('astrophotoflow.modules.data.public.run_import_task', lambda *_args: None)
    accepted = client.post('/api/v1/imports', headers=AUTH, json={'sources': [{'root_id': 'science', 'path': 'changing.fits'}], 'storage_mode': 'managed'}).json()
    source = root / 'changing.fits'
    stamp = source.stat()
    os.utime(source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 1000000000))
    owner_runner.run_import_task(app.state.database, settings, accepted['task_id'], app.state.import_workers)
    result = task(client, accepted['task_id'])
    assert result['report']['content']['failed'] == 1
    assert result['items'][0]['error']['code'] == 'SOURCE_CHANGED'
    assert result['items'][0]['asset_id'] is None

def test_copy_starts_before_last_registration_and_originals_finish_before_previews(service, monkeypatch):
    settings, app, client, root = service
    for index in range(3):
        image(root / f'{index}.fits')
    copied, second_copy, release_copy, preview_entered, release_preview = (Event(), Event(), Event(), Event(), Event())
    original_read, original_register, original_preview = (owner_stages.read_hash_and_copy, owner_stages.register_asset, owner_display.DisplayPreviews._render)

    def read(*args, **kwargs):
        copied.set()
        if args[0].name == '1.fits':
            second_copy.set()
        assert release_copy.wait(5)
        return original_read(*args, **kwargs)

    def register(database, selected_settings, data, item_id):
        with database.read_session() as session:
            item = session.get(AssetTaskItem, item_id)
            if item.source_path == '2.fits' and item.asset_id is None:
                assert copied.wait(5)
                assert second_copy.wait(5)
        return original_register(database, selected_settings, data, item_id)

    def preview(*args, **kwargs):
        preview_entered.set()
        assert release_preview.wait(5)
        return original_preview(*args, **kwargs)
    monkeypatch.setattr(owner_stages, 'read_hash_and_copy', read)
    monkeypatch.setattr(owner_stages, 'register_asset', register)
    monkeypatch.setattr(owner_display.DisplayPreviews, '_render', preview)
    task_id = enqueue(app)
    thread = run(app, settings, task_id)
    try:
        assert copied.wait(5)
        release_copy.set()
        assert preview_entered.wait(5)
        current = task(client, task_id)
        assert current['status'] == 'completed'
        assert current['report']['content']['completed'] is True
        assert current['report']['content']['succeeded'] == 3
        assert current['report']['preview']['completed'] is False
        with app.state.database.read_session() as session:
            assert all((version.availability == 'available' for version in session.scalars(select(Asset)).all()))
    finally:
        release_copy.set()
        release_preview.set()
        thread.join(10)
    assert not thread.is_alive()
    assert task(client, task_id)['status'] == 'completed'

def test_preview_only_retry_reuses_available_managed_content(service, monkeypatch):
    settings, app, client, root = service
    image(root / 'ready.fits')
    task_id = enqueue(app)
    owner_runner.run_import_task(app.state.database, settings, task_id, app.state.import_workers)
    original = task(client, task_id)['items'][0]
    with app.state.database.write_session() as session:
        item = session.get(AssetTaskItem, original['id'])
        item.status, item.preview_status = ('completed_with_errors', 'failed')
        item.error = {'code': 'PREVIEW_FAILED', 'message': 'injected preview failure'}
        session.get(AssetTask, task_id).status = 'completed_with_errors'

    def unexpected_copy(*_args, **_kwargs):
        raise AssertionError('available original must not be copied or hashed again')
    monkeypatch.setattr(owner_stages, 'read_hash_and_copy', unexpected_copy)
    retry = client.post(f'/api/v1/asset-tasks/{task_id}/retry', headers=AUTH, json={'item_ids': [original['id']]})
    assert retry.status_code == 202
    result = task(client, retry.json()['task_id'])
    assert result['status'] == 'completed'
    assert result['items'][0]['asset_id'] == original['asset_id']
    assert result['items'][0]['asset_id'] == original['asset_id']
    assert result['report']['content']['succeeded'] == 1
