from __future__ import annotations
import astrophotoflow.modules.data.imports.stages as owner_stages
import astrophotoflow.modules.data.imports.enumeration as owner_enumeration
from astrophotoflow.modules.data.formats import layout as codec_formats_layout
from astrophotoflow.modules.data.formats import pixels as codec_formats_pixels
from astrophotoflow.modules.data.formats import fits as codec_formats_fits
from astrophotoflow.modules.data.assets.metadata import classification_columns, parameter_columns
from astrophotoflow.core.localization import error_message
from pathlib import Path
from io import BytesIO
import struct
import sqlite3
import subprocess
from uuid import uuid4
import blake3
import numpy as np
import pytest
from astropy.io import fits
from fastapi.testclient import TestClient
from PIL import Image
from pillow_heif import register_heif_opener
from sqlalchemy import select
from xisf import XISF
from astrophotoflow.interfaces.http.app import create_app
from astrophotoflow.modules.data.assets.models import Asset, FitsHduMetadata
from astrophotoflow.modules.data.media.models import Preview
from astrophotoflow.modules.data.imports.models import AssetTask, AssetTaskItem
from astrophotoflow.modules.data.media.import_previews import backfill_missing_previews
from astrophotoflow.modules.data.imports.tasks import mark_interrupted_tasks
from astrophotoflow.modules.data.imports.runner import run_import_task
from astrophotoflow.core.database.schema import database_lock, initialize_database
from astrophotoflow.core.config import ImportRoot, Settings
TOKEN = 'test-token'
AUTH = {'Authorization': f'Bearer {TOKEN}'}

def write_fits(path: Path, value: int=1) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    primary = fits.PrimaryHDU(np.arange(48, dtype=np.int16).reshape(6, 8) + value)
    primary.header['EXPTIME'] = 30
    primary.header['GAIN'] = 9
    primary.header['CCD-TEMP'] = -15
    primary.header['IMAGETYP'] = 'Light Frame'
    primary.header['BAYERPAT'] = 'RGGB'
    primary.header['COMMENT'] = 'first comment'
    primary.header['COMMENT'] = 'second comment'
    fits.HDUList([primary, fits.ImageHDU(np.ones((3, 4), dtype=np.float32))]).writeto(path)
    return path.read_bytes()

def make_client(tmp_path: Path, roots: tuple[ImportRoot, ...]):
    settings = Settings('127.0.0.1', 8190, tmp_path / 'data', ('http://127.0.0.1:8188',), roots, workspace=tmp_path)
    with database_lock(settings):
        initialize_database(settings)
    app = create_app(settings, TOKEN)
    client = TestClient(app)
    client.__enter__()
    return (settings, app, client)

def start_import(client: TestClient, path: str, storage_mode: str='reference', *, sources=None, classification=None):
    return client.post('/api/v1/imports', headers=AUTH, json={'sources': sources or [{'root_id': 'science', 'path': path}], 'storage_mode': storage_mode, 'classification': classification or {'frame_class': 'subframe', 'frame_type': 'light'}, 'parameters': {'parameter_mode': 'gain', 'gain': 42, 'exposure_seconds': 0, 'sensor_temperature_c': -10, 'binning_x': 1, 'binning_y': 2}, 'notes': 'night one\nM31'})

def test_root_browser_import_versions_edit_and_dataset_references(tmp_path):
    root = tmp_path / 'science'
    first_path = root / 'M31' / '星云 #1.fits'
    first_bytes = write_fits(first_path)
    settings, app, client = make_client(tmp_path, (ImportRoot('science', root),))
    try:
        entries = client.get('/api/v1/import-roots/science/entries', headers=AUTH, params={'path': 'M31'})
        assert entries.status_code == 200
        assert entries.json()['items'][0]['path'] == 'M31/星云 #1.fits'
        assert client.get('/api/v1/import-roots/science/entries', headers=AUTH, params={'path': '../'}).status_code == 422
        outside = tmp_path / 'outside'
        write_fits(outside / 'outside.fits')
        (root / 'escape').symlink_to(outside, target_is_directory=True)
        assert all((item['name'] != 'escape' for item in client.get('/api/v1/import-roots/science/entries', headers=AUTH).json()['items']))
        assert start_import(client, 'escape/outside.fits').status_code == 404
        imported = start_import(client, 'M31/星云 #1.fits')
        assert imported.status_code == 202
        task_id = imported.json()['task_id']
        task = client.get(f'/api/v1/asset-tasks/{task_id}', headers=AUTH).json()
        item = task['items'][0]
        assert task['status'] == 'completed', ([{key: item[key] for key in ('status', 'content_status', 'metadata_status', 'preview_status', 'error')} for item in task['items']], task['report'])
        assert item['content_status'] == 'available'
        assert item['metadata_status'] == 'available'
        assert item['preview_status'] == 'available'
        asset_response = client.get('/api/v1/library/assets', headers=AUTH)
        asset = asset_response.json()['items'][0]
        version = asset
        assert version['content_hash'] == 'blake3:' + blake3.blake3(first_bytes).hexdigest()
        assert version['byte_size'] == len(first_bytes)
        assert asset['parameters']['gain'] == 42
        assert asset['parameters']['exposure_seconds'] == 0
        assert asset['value_sources']['gain'] == 'manual'
        assert asset['value_sources']['classification.frame_type'] == 'manual'
        assert version['scientific_metadata']['observed_parameters']['gain'] == 9.0
        assert version['scientific_metadata']['observed_parameters']['exposure_seconds'] == 30.0
        assert version['scientific_metadata']['observed_parameters']['sensor_temperature_setpoint_c'] == -15.0
        assert version['scientific_metadata']['observed_parameters']['file_classification_header'] == {'keyword': 'IMAGETYP', 'value': 'Light Frame'}
        assert asset['parameters']['sensor_temperature_c'] == -10
        assert asset['value_sources']['sensor_temperature_c'] == 'manual'
        assert first_path.read_bytes() == first_bytes
        header = client.get(f"/api/v1/library/assets/{asset['id']}/hdus/0/header", headers=AUTH).json()
        comments = [card['value'] for card in header['cards'] if card['keyword'] == 'COMMENT']
        assert comments == ['first comment', 'second comment']
        hdus = client.get(f"/api/v1/library/assets/{asset['id']}/hdus", headers=AUTH)
        assert hdus.status_code == 200 and hdus.json()['total'] == 2
        preview = client.get(f"/api/v1/library/assets/{asset['id']}/previews/thumbnail", headers=AUTH)
        assert preview.status_code == 200
        assert preview.headers['content-type'] == 'image/jpeg'
        with Image.open(__import__('io').BytesIO(preview.content)) as image:
            assert image.size == (8, 6)
        project = client.post('/api/v1/projects', headers=AUTH, json={'name': 'M31'}).json()
        reference = client.post(f"/api/v1/projects/{project['id']}/asset-references", headers=AUTH, json={'base_revision': 1, 'asset_id': version['id']})
        assert reference.status_code == 201, reference.text
        reference_hdus = client.get(f"/api/v1/projects/{project['id']}/asset-references/{reference.json()['id']}/hdus", headers=AUTH)
        assert reference_hdus.status_code == 200 and reference_hdus.json()['total'] == 2
        edited = client.patch(f"/api/v1/library/assets/{asset['id']}", headers=AUTH, json={'base_revision': 1, 'notes': 'edited\nnotes', 'classification': {'frame_class': 'subframe', 'frame_type': 'dark'}, 'parameters': {'gain': None}})
        assert edited.status_code == 200
        assert edited.json()['revision'] == 2
        assert edited.json()['notes'] == 'edited\nnotes'
        assert edited.json()['role'] == 'calibration'
        assert edited.json()['calibration_level'] == 'individual'
        assert edited.json()['parameters']['gain'] is None
        assert client.get('/api/v1/library/assets', headers=AUTH, params={'role': 'calibration', 'calibration_level': 'master'}).json()['total'] == 1
        project_asset = client.get(f"/api/v1/projects/{project['id']}/asset-references/{reference.json()['id']}", headers=AUTH).json()
        assert project_asset['asset']['notes'] == 'edited\nnotes'
        assert project_asset['asset']['id'] == version['id']

        repeated = start_import(client, 'M31/星云 #1.fits', classification={'frame_class': 'subframe', 'frame_type': 'dark'})
        assert repeated.status_code == 202
        second_task = client.get(f"/api/v1/asset-tasks/{repeated.json()['task_id']}", headers=AUTH).json()
        second_asset_id = second_task['items'][0]['asset_id']
        assert second_asset_id != asset['id']
        second_asset = client.get(f'/api/v1/library/assets/{second_asset_id}', headers=AUTH).json()
        assert second_task['status'] == 'completed'
        assert second_asset['classification'] == {'frame_class': 'subframe', 'frame_type': 'dark'}
        assert second_asset['role'] == 'calibration'
        assert second_asset['scientific_metadata']['observed_parameters']['file_classification_header']['value'] == 'Light Frame'
        duplicate_batch = start_import(client, '', storage_mode='managed', sources=[{'root_id': 'science', 'path': 'M31/星云 #1.fits'}, {'root_id': 'science', 'path': 'M31/星云 #1.fits'}])
        duplicate_task = client.get(f"/api/v1/asset-tasks/{duplicate_batch.json()['task_id']}", headers=AUTH).json()
        assert duplicate_task['status'] == 'completed'
        assert sum((item['content_status'] == 'available' for item in duplicate_task['items'])) == 1
        assert sum((item['status'] == 'skipped' for item in duplicate_task['items'])) == 1
        dataset = client.get('/api/v1/datasets', headers=AUTH).json()['items'][0]
        assert dataset['member_count'] == 1
        dataset_version = client.get(f"/api/v1/datasets/{dataset['id']}/members", headers=AUTH).json()
        assert dataset_version['items'][0]['relative_path'] == 'M31/星云 #1.fits'
        managed_path = settings.data_dir / dataset_version['items'][0]['asset']['storage_location']
        assert managed_path.read_bytes() == first_bytes
        assert first_path.read_bytes() == first_bytes
        dataset_ref = client.post(f"/api/v1/projects/{project['id']}/dataset-references", headers=AUTH, json={'base_revision': 2, 'dataset_id': dataset['id']})
        assert dataset_ref.status_code == 201
        assert dataset_ref.json()['dataset_id'] == dataset['id']
        retained_member = dataset_version['items'][0]
        appended_version_id = second_task['items'][0]['asset_id']
        changed = client.put(f"/api/v1/datasets/{dataset['id']}/members", headers=AUTH, json={'base_revision': dataset['revision'], 'asset_ids': [retained_member['asset_id'], appended_version_id]})
        assert changed.status_code == 200
        assert [member['asset_id'] for member in client.get(f"/api/v1/datasets/{dataset['id']}/members", headers=AUTH).json()['items']] == [retained_member['asset_id'], appended_version_id]
        assert client.get(f"/api/v1/projects/{project['id']}/dataset-references/{dataset_ref.json()['id']}", headers=AUTH).json()['dataset_id'] == dataset['id']
        reordered = client.put(f"/api/v1/datasets/{dataset['id']}/members", headers=AUTH, json={'base_revision': dataset['revision'] + 1, 'asset_ids': [appended_version_id, retained_member['asset_id']]})
        assert reordered.status_code == 422
        archived = client.patch(f"/api/v1/datasets/{dataset['id']}", headers=AUTH, json={'base_revision': dataset['revision'] + 1, 'status': 'archived'})
        assert archived.status_code == 200
        pinned = client.get(f"/api/v1/projects/{project['id']}/dataset-references/{dataset_ref.json()['id']}", headers=AUTH).json()
        assert pinned['dataset']['status'] == 'archived'
        assert pinned['dataset_id'] == dataset['id']
        write_fits(root / 'set' / 'z-last.fits', 2)
        write_fits(root / 'set' / 'A-first.fits', 3)
        folder_task = start_import(client, 'set')
        folder_result = client.get(f"/api/v1/asset-tasks/{folder_task.json()['task_id']}", headers=AUTH).json()
        assert folder_result['status'] == 'completed'
        assert [item['source_path'] for item in folder_result['items']] == ['set/A-first.fits', 'set/z-last.fits']
        folder_dataset = client.get(f"/api/v1/datasets/{folder_result['dataset_id']}", headers=AUTH).json()
        folder_version = client.get(f"/api/v1/datasets/{folder_dataset['id']}/members", headers=AUTH).json()
        assert [member['relative_path'] for member in folder_version['items']] == ['set/A-first.fits', 'set/z-last.fits']
        first_path.unlink()
        assert client.get('/api/v1/library/assets', headers=AUTH).json()['total'] == 5
        assert client.get(f"/api/v1/projects/{project['id']}/asset-references/{reference.json()['id']}", headers=AUTH).json()['asset']['id'] == version['id']
    finally:
        client.__exit__(None, None, None)

def test_browser_upload_creates_one_dataset_row_and_managed_assets(tmp_path):
    first = write_fits(tmp_path / 'first.fits', 2)
    second = write_fits(tmp_path / 'second.fits', 3)
    settings, app, client = make_client(tmp_path, ())
    try:
        created = client.post('/api/v1/uploads', headers=AUTH, json={'files': [{'name': 'first.fits', 'size': len(first)}, {'name': 'second.fits', 'size': len(second)}], 'classification': {'frame_class': 'subframe', 'frame_type': 'light'}, 'parameters': {}, 'notes': 'batch note', 'dataset_name': 'M31 session'})
        assert created.status_code == 202
        task_id = created.json()['task_id']
        assert client.get('/api/v1/asset-tasks', headers=AUTH).json()['items'][0]['status'] == 'queued'
        assert client.put(f'/api/v1/uploads/{task_id}/0', headers=AUTH, content=first).status_code == 200
        assert client.put(f'/api/v1/uploads/{task_id}/1', headers=AUTH, content=second).status_code == 200
        started = client.post(f'/api/v1/uploads/{task_id}/start', headers=AUTH, json={})
        assert started.status_code == 202
        task = client.get(f'/api/v1/asset-tasks/{task_id}', headers=AUTH).json()
        assert task['status'] == 'completed'
        assert task['dataset_id']
        items = client.get('/api/v1/library/items', headers=AUTH).json()
        assert items['total'] == 1
        entry = items['items'][0]
        assert entry['entry_type'] == 'dataset'
        assert entry['name'] == 'M31 session'
        assert client.get('/api/v1/library/items', headers=AUTH, params={'q': 'first'}).json()['total'] == 1
        assert entry['member_count'] == 2
        assert entry['summary']['storage_mode'] == {'state': 'consistent', 'value': 'managed'}
        assert not list((settings.data_dir / 'upload-staging' / task_id).glob('*'))
        failed_batch = client.post('/api/v1/uploads', headers=AUTH, json={'files': [{'name': 'partial.fits', 'size': len(first) + 1}], 'classification': {'frame_class': 'subframe', 'frame_type': 'light'}}).json()['task_id']
        assert client.put(f'/api/v1/uploads/{failed_batch}/0', headers=AUTH, content=first).status_code == 400
        failed = client.post(f'/api/v1/uploads/{failed_batch}/fail', headers=AUTH, json={})
        assert failed.status_code == 200
        assert client.get(f'/api/v1/asset-tasks/{failed_batch}', headers=AUTH).json()['status'] == 'failed'
        assert not (settings.data_dir / 'upload-staging' / failed_batch).exists()
        incomplete = client.post('/api/v1/uploads', headers=AUTH, json={'files': [{'name': 'one.fits', 'size': len(first)}, {'name': 'two.fits', 'size': len(second)}], 'classification': {'frame_class': 'subframe', 'frame_type': 'light'}}).json()['task_id']
        client.put(f'/api/v1/uploads/{incomplete}/0', headers=AUTH, content=first)
        mark_interrupted_tasks(app.state.database)
        resume = client.post(f'/api/v1/asset-tasks/{incomplete}/resume', headers=AUTH, json={})
        assert resume.status_code == 409
        assert resume.json()['error']['code'] == 'UPLOAD_REQUIRES_SELECTION'
    finally:
        client.__exit__(None, None, None)

def test_completed_upload_cancelled_items_can_retry_from_original_staging(tmp_path):
    second_bytes = write_fits(tmp_path / 'second.fits', 2)
    _, app, client = make_client(tmp_path, ())
    try:
        task_id = str(uuid4())
        staging = app.state.settings.data_dir / 'upload-staging' / task_id
        staging.mkdir(parents=True)
        (staging / '1.fits').write_bytes(second_bytes)
        with app.state.database.write_session() as session:
            session.add(AssetTask(id=task_id, status='cancelled', sources=[], storage_mode='managed', classification={}, parameters={}, notes=None, dataset_name=None, target_dataset_id=None, dataset_base_revision=None, dataset_id=None, enumeration_completed=True, retry_of_task_id=None, report={'upload_manifest': True, 'upload_complete': True, 'upload_files': [{'name': 'first.fits', 'size': 1, 'received': 1, 'stored_name': '0.fits'}, {'name': 'second.fits', 'size': len(second_bytes), 'received': len(second_bytes), 'stored_name': '1.fits'}]}, error=None))
            session.flush()
            session.add_all([AssetTaskItem(id=str(uuid4()), task_id=task_id, root_item_id=str(uuid4()), retry_of_item_id=None, root_id='__upload__', source_path='0.fits', source_identity='upload:0', position=0, status='completed', content_status='available', metadata_status='unsupported', preview_status='available'), AssetTaskItem(id=str(uuid4()), task_id=task_id, root_item_id=str(uuid4()), retry_of_item_id=None, root_id='__upload__', source_path='1.fits', source_identity='upload:1', position=1, status='cancelled', content_status='pending', metadata_status='pending', preview_status='pending')])
            unprocessed_id = session.scalar(select(AssetTaskItem.id).where(AssetTaskItem.task_id == task_id, AssetTaskItem.position == 1))
        task = client.get(f'/api/v1/asset-tasks/{task_id}', headers=AUTH).json()
        unprocessed = next((item for item in task['items'] if item['id'] == unprocessed_id))
        source_file = app.state.settings.data_dir / 'upload-staging' / task_id / unprocessed['source_path']
        assert source_file.is_file()
        retried = client.post(f'/api/v1/asset-tasks/{task_id}/retry', headers=AUTH, json={'item_ids': [unprocessed['id']]})
        assert retried.status_code == 202
        retry = client.get(f"/api/v1/asset-tasks/{retried.json()['task_id']}", headers=AUTH).json()
        assert retry['status'] == 'completed'
        assert retry['retry_of_task_id'] == task_id
        assert retry['items'][0]['content_status'] == 'available'
        assert not source_file.exists()
        assert client.get('/api/v1/library/items', headers=AUTH).json()['total'] == 1
        assert client.get('/api/v1/library/assets', headers=AUTH).json()['total'] == 1
    finally:
        client.__exit__(None, None, None)

def test_project_asset_and_dataset_reference_deletes_check_revision_without_deleting_data(tmp_path):
    root = tmp_path / 'science'
    original = write_fits(root / 'single.fits')
    write_fits(root / 'group' / 'one.fits', 2)
    write_fits(root / 'group' / 'two.fits', 3)
    _, app, client = make_client(tmp_path, (ImportRoot('science', root),))
    try:
        asset_task_id = start_import(client, 'single.fits').json()['task_id']
        asset_item = client.get(f'/api/v1/asset-tasks/{asset_task_id}', headers=AUTH).json()['items'][0]
        dataset_task_id = start_import(client, 'group', sources=[{'root_id': 'science', 'path': 'group/one.fits'}, {'root_id': 'science', 'path': 'group/two.fits'}]).json()['task_id']
        dataset_task = client.get(f'/api/v1/asset-tasks/{dataset_task_id}', headers=AUTH).json()
        dataset = client.get(f"/api/v1/datasets/{dataset_task['dataset_id']}", headers=AUTH).json()
        project = client.post('/api/v1/projects', headers=AUTH, json={'name': 'reference deletion'}).json()
        asset_reference = client.post(f"/api/v1/projects/{project['id']}/asset-references", headers=AUTH, json={'base_revision': 1, 'asset_id': asset_item['asset_id']}).json()
        stale_asset_delete = client.request('DELETE', f"/api/v1/projects/{project['id']}/asset-references/{asset_reference['id']}", headers=AUTH, json={'base_revision': 1})
        assert stale_asset_delete.status_code == 409
        assert client.get(f"/api/v1/projects/{project['id']}/assets", headers=AUTH).json()['total'] == 1
        asset_delete = client.request('DELETE', f"/api/v1/projects/{project['id']}/asset-references/{asset_reference['id']}", headers=AUTH, json={'base_revision': 2})
        assert asset_delete.status_code == 200 and asset_delete.json()['revision'] == 3
        dataset_reference = client.post(f"/api/v1/projects/{project['id']}/dataset-references", headers=AUTH, json={'base_revision': 3, 'dataset_id': dataset['id']}).json()
        stale_dataset_delete = client.request('DELETE', f"/api/v1/projects/{project['id']}/dataset-references/{dataset_reference['id']}", headers=AUTH, json={'base_revision': 3})
        assert stale_dataset_delete.status_code == 409
        assert client.get(f"/api/v1/projects/{project['id']}/dataset-references", headers=AUTH).json()['total'] == 1
        dataset_delete = client.request('DELETE', f"/api/v1/projects/{project['id']}/dataset-references/{dataset_reference['id']}", headers=AUTH, json={'base_revision': 4})
        assert dataset_delete.status_code == 200 and dataset_delete.json()['revision'] == 5
        assert client.get(f"/api/v1/projects/{project['id']}/dataset-references", headers=AUTH).json()['total'] == 0
        assert client.get(f"/api/v1/library/assets/{asset_item['asset_id']}", headers=AUTH).status_code == 200
        assert client.get(f"/api/v1/datasets/{dataset['id']}", headers=AUTH).status_code == 200
        assert (root / 'single.fits').read_bytes() == original
    finally:
        client.__exit__(None, None, None)

def test_import_without_override_uses_explicit_fits_classification(tmp_path):
    root = tmp_path / 'science'
    write_fits(root / 'unclassified.fits')
    settings, app, client = make_client(tmp_path, (ImportRoot('science', root),))
    try:
        response = client.post('/api/v1/imports', headers=AUTH, json={'sources': [{'root_id': 'science', 'path': 'unclassified.fits'}], 'storage_mode': 'reference'})
        assert response.status_code == 202, response.text
        task_id = response.json()['task_id']
        task = client.get(f'/api/v1/asset-tasks/{task_id}', headers=AUTH).json()
        asset = client.get(f"/api/v1/library/assets/{task['items'][0]['asset_id']}", headers=AUTH).json()
        assert asset['classification'] == {'frame_class': 'subframe', 'frame_type': 'light'}
        assert asset['scientific_metadata']['observed_parameters']['file_classification_header']['value'] == 'Light Frame'
    finally:
        client.__exit__(None, None, None)

@pytest.mark.parametrize(('raw', 'rounded'), [(0.49, 0), (0.5, 1), (1.5, 2), (-0.49, 0), (-0.5, -1), (-1.5, -2)])
def test_temperature_rounding_uses_half_away_from_zero(raw, rounded):
    with sqlite3.connect(':memory:') as connection:
        assert connection.execute('SELECT round(?)', (raw,)).fetchone()[0] == rounded

def test_unclassified_folder_file_is_saved_without_creating_a_dataset(tmp_path):
    settings, app, client = make_client(tmp_path, ())
    try:
        buffer = BytesIO()
        Image.new('RGB', (12, 8), (80, 120, 200)).save(buffer, format='PNG')
        data = buffer.getvalue()
        created = client.post('/api/v1/uploads', headers=AUTH, json={'files': [{'name': 'first.png', 'size': len(data)}], 'create_dataset': True, 'dataset_name': 'source-folder'})
        assert created.status_code == 202, created.text
        task_id = created.json()['task_id']
        assert client.put(f'/api/v1/uploads/{task_id}/0', headers=AUTH, content=data).status_code == 200
        assert client.post(f'/api/v1/uploads/{task_id}/start', headers=AUTH, json={}).status_code == 202
        task = client.get(f'/api/v1/asset-tasks/{task_id}', headers=AUTH).json()
        assert task['status'] == 'completed_with_errors'
        assert task['dataset_id'] is None and task['dataset_name'] == 'source-folder'
        assert task['report']['dataset_exclusions'][0]['name'] == 'first.png'
        asset = client.get(f"/api/v1/library/assets/{task['items'][0]['asset_id']}", headers=AUTH).json()
        assert asset['classification'] == {'frame_class': None, 'frame_type': None}
        assert asset['parameters']['camera_id'] is None
        assert client.get('/api/v1/library/items', headers=AUTH).json()['items'][0]['entry_type'] == 'asset'
    finally:
        client.__exit__(None, None, None)

def test_dataset_member_parameter_update_is_atomic_and_creates_no_asset_versions(tmp_path):
    settings, app, client = make_client(tmp_path, ())
    try:
        data = []
        for color in ((220, 30, 30), (20, 210, 30)):
            buffer = BytesIO()
            Image.new('RGB', (12, 8), color).save(buffer, format='PNG')
            data.append(buffer.getvalue())
        created = client.post('/api/v1/uploads', headers=AUTH, json={'files': [{'name': 'one.png', 'size': len(data[0])}, {'name': 'two.png', 'size': len(data[1])}], 'classification': {'frame_class': 'subframe', 'frame_type': 'light'}})
        task_id = created.json()['task_id']
        for index, payload in enumerate(data):
            client.put(f'/api/v1/uploads/{task_id}/{index}', headers=AUTH, content=payload)
        client.post(f'/api/v1/uploads/{task_id}/start', headers=AUTH, json={})
        task = client.get(f'/api/v1/asset-tasks/{task_id}', headers=AUTH).json()
        dataset = client.get(f"/api/v1/datasets/{task['dataset_id']}", headers=AUTH).json()
        version = client.get(f"/api/v1/datasets/{dataset['id']}/members", headers=AUTH).json()
        members = version['items']
        body = {'base_revision': dataset['revision'], 'members': [{'asset_id': member['asset']['id'], 'revision': member['asset']['revision']} for member in members], 'parameters': {'exposure_seconds': 12.5}}
        updated = client.patch(f"/api/v1/datasets/{dataset['id']}/member-parameters", headers=AUTH, json=body)
        assert updated.status_code == 200, updated.text
        assert {asset['parameters']['exposure_seconds'] for asset in updated.json()['assets']} == {12.5}
        assert {asset['revision'] for asset in updated.json()['assets']} == {2}
        stale = {**body, 'parameters': {'gain': 50}}
        stale['members'][0]['revision'] = updated.json()['assets'][0]['revision']
        rejected = client.patch(f"/api/v1/datasets/{dataset['id']}/member-parameters", headers=AUTH, json=stale)
        assert rejected.status_code == 409
        current = [client.get(f"/api/v1/library/assets/{asset['id']}", headers=AUTH).json() for asset in updated.json()['assets']]
        assert {asset['parameters']['exposure_seconds'] for asset in current} == {12.5}
        assert all((asset['parameters']['gain'] is None for asset in current))
    finally:
        client.__exit__(None, None, None)

def test_backfill_records_missing_reference_and_continues_to_next_asset(tmp_path):
    root = tmp_path / 'science'
    for name, color in (('missing.png', 'red'), ('available.png', 'blue')):
        root.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (12, 8), color).save(root / name)
    settings, app, client = make_client(tmp_path, (ImportRoot('science', root),))
    try:
        start_import(client, 'missing.png')
        start_import(client, 'available.png')
        with app.state.database.write_session() as session:
            session.execute(__import__('sqlalchemy').delete(Preview))
        (root / 'missing.png').unlink()
        assert backfill_missing_previews(app.state.database, settings) == {'generated': 1, 'failed': 1}
    finally:
        client.__exit__(None, None, None)

def test_non_bayer_cfa_stays_registered_and_reports_preview_unsupported(tmp_path):
    root = tmp_path / 'science'
    root.mkdir()
    hdu = fits.PrimaryHDU(np.arange(64, dtype=np.uint16).reshape(8, 8))
    hdu.header['BAYERPAT'] = 'XTRANS'
    hdu.writeto(root / 'xtrans.fits')
    settings, app, client = make_client(tmp_path, (ImportRoot('science', root),))
    try:
        accepted = start_import(client, 'xtrans.fits', storage_mode='managed', classification={'frame_class': None, 'frame_type': None})
        task = client.get(f"/api/v1/asset-tasks/{accepted.json()['task_id']}", headers=AUTH).json()
        item = task['items'][0]
        asset = client.get(f"/api/v1/library/assets/{item['asset_id']}", headers=AUTH).json()
        assert task['status'] == 'completed_with_errors'
        assert asset['parameters']['cfa_pattern'] == 'XTRANS'
        assert item['preview_status'] == 'unsupported'
        assert item['error']['message'] == error_message('en', '', 'import_cfa_preview_unsupported', {'layout': 'xtrans'})
        video = client.patch(f"/api/v1/library/assets/{asset['id']}", headers=AUTH, json={'base_revision': asset['revision'], 'classification': {'frame_class': 'video'}})
        assert video.status_code == 200
        restored = client.patch(f"/api/v1/library/assets/{asset['id']}", headers=AUTH, json={'base_revision': video.json()['revision'], 'classification': {'frame_class': 'subframe'}})
        assert restored.status_code == 200
        assert restored.json()['classification'] == {'frame_class': 'subframe', 'frame_type': None}
    finally:
        client.__exit__(None, None, None)

def test_backfill_recognizes_previously_unsupported_pixinsight_rgb_without_reimport(tmp_path, monkeypatch):
    root = tmp_path / 'science'
    root.mkdir()
    path = root / 'color.fits'
    hdu = fits.PrimaryHDU(np.stack([np.full((20, 30), value, dtype=np.float32) for value in (0, 100, 200)]))
    hdu.header['PROGRAM'] = 'PixInsight 1.9.3'
    hdu.header['BAYERPAT'] = 'RGGB'
    hdu.header['EXPTIME'] = 60
    hdu.writeto(path)
    original = path.read_bytes()
    settings, app, client = make_client(tmp_path, (ImportRoot('science', root),))
    try:
        with monkeypatch.context() as legacy:
            legacy.setattr(codec_formats_layout, 'rgb_channel_first', lambda header: False)
            accepted = start_import(client, 'color.fits', storage_mode='managed')
        assert accepted.status_code == 202
        before = client.get('/api/v1/library/assets', headers=AUTH).json()['items'][0]
        asset_id, version_id = (before['id'], before['id'])
        endpoint = f'/api/v1/library/assets/{asset_id}/previews/thumbnail'
        assert client.get(endpoint, headers=AUTH).status_code == 404
        with app.state.database.read_session() as session:
            stored_hdu = session.scalar(select(FitsHduMetadata).where(FitsHduMetadata.asset_id == version_id))
            hdu_id = stored_hdu.id
            assert stored_hdu.supported_kind is None and (not stored_hdu.is_selected)
        assert backfill_missing_previews(app.state.database, settings) == {'generated': 1, 'failed': 0}
        after = client.get(f'/api/v1/library/assets/{asset_id}', headers=AUTH).json()
        for key in ('id', 'revision', 'parameters', 'classification', 'notes', 'value_sources'):
            assert after[key] == before[key]
        assert after['parameters']['exposure_seconds'] == 0
        response = client.get(endpoint, headers=AUTH)
        assert response.status_code == 200
        with Image.open(BytesIO(response.content)) as image:
            assert image.mode == 'RGB' and max(image.size) <= 100
        with app.state.database.read_session() as session:
            stored_hdu = session.get(FitsHduMetadata, hdu_id)
            assert stored_hdu.supported_kind == 'rgb' and stored_hdu.is_selected
            preview_id = session.scalar(select(Preview.id).where(Preview.asset_id == version_id))
        assert backfill_missing_previews(app.state.database, settings) == {'generated': 0, 'failed': 0}
        with app.state.database.read_session() as session:
            assert session.scalar(select(Preview.id).where(Preview.asset_id == version_id)) == preview_id
        assert path.read_bytes() == original
    finally:
        client.__exit__(None, None, None)

def test_ordinary_images_create_only_small_preview(tmp_path):
    root = tmp_path / 'science'
    source = root / 'portrait.png'
    source.parent.mkdir(parents=True)
    image = Image.new('RGB', (320, 180), (30, 120, 210))
    image.save(source)
    original = source.read_bytes()
    settings, app, client = make_client(tmp_path, (ImportRoot('science', root),))
    try:
        accepted = start_import(client, 'portrait.png', storage_mode='managed')
        assert accepted.status_code == 202
        asset = client.get('/api/v1/library/assets', headers=AUTH).json()['items'][0]
        version = asset
        response = client.get(f"/api/v1/library/assets/{asset['id']}/previews/thumbnail", headers=AUTH)
        assert response.status_code == 200
        with Image.open(BytesIO(response.content)) as preview:
            assert preview.size == (100, 56)
        assert client.get(f"/api/v1/library/assets/{asset['id']}/previews/detail", headers=AUTH).status_code == 404
        with app.state.database.read_session() as session:
            assert session.scalar(select(Preview).where(Preview.asset_id == version['id'], Preview.size == 'detail')) is None
            thumbnail = session.scalar(select(Preview).where(Preview.asset_id == version['id'], Preview.size == 'thumbnail'))
            thumbnail_id = thumbnail.id
        with app.state.database.write_session() as session:
            session.delete(session.get(Preview, thumbnail_id))
        assert backfill_missing_previews(app.state.database, settings) == {'generated': 1, 'failed': 0}
        with app.state.database.read_session() as session:
            assert session.scalar(select(Preview).where(Preview.asset_id == version['id'], Preview.size == 'detail')) is None
        assert source.read_bytes() == original
    finally:
        client.__exit__(None, None, None)

def test_fits_batch_stretches_each_photo_independently_and_restores_it_on_resume(tmp_path):
    root = tmp_path / 'science'
    root.mkdir()
    cases = (('a.fit', 0, 30, 'L'), ('b.fit', 1000, 30, 'L'), ('c.fit', 2000, 60, 'L'), ('d.fit', None, 30, 'Ha'), ('e.fit', 3000, 30, 'Ha'))
    for name, offset, exposure, filter_name in cases:
        pixels = np.arange(2400, dtype=np.float32).reshape(40, 60) + offset if offset is not None else np.full((40, 60), np.nan, dtype=np.float32)
        hdu = fits.PrimaryHDU(pixels)
        hdu.header['EXPTIME'] = exposure
        hdu.header['FILTER'] = filter_name
        hdu.writeto(root / name)
    settings, app, client = make_client(tmp_path, (ImportRoot('science', root),))
    try:
        created = client.post('/api/v1/imports', headers=AUTH, json={'sources': [{'root_id': 'science', 'path': name} for name, *_ in cases], 'storage_mode': 'reference', 'classification': {'frame_class': 'subframe', 'frame_type': 'light'}, 'parameters': {}, 'notes': ''})
        assert created.status_code == 202
        task_id = created.json()['task_id']
        task = client.get(f'/api/v1/asset-tasks/{task_id}', headers=AUTH).json()
        items = {Path(item['source_path']).name: item for item in task['items']}
        assert items['d.fit']['preview_status'] == 'failed'
        with app.state.database.read_session() as session:
            displays = {name: session.scalar(select(Preview).where(Preview.asset_id == items[name]['asset_id'], Preview.size == 'thumbnail')).display_parameters for name in ('a.fit', 'b.fit', 'c.fit', 'e.fit')}
            assert 'preview_stretch_groups' not in session.get(AssetTask, task_id).report
        for name, offset in (('b.fit', 1000), ('c.fit', 2000), ('e.fit', 3000)):
            assert displays[name]['auto_stretch']['highlights'] == pytest.approx(displays['a.fit']['auto_stretch']['highlights'] + offset)
            assert 'stretch_reference_asset_id' not in displays[name]
            assert 'stretch_group' not in displays[name]
        assert client.get(f"/api/v1/library/assets/{items['b.fit']['asset_id']}/previews/detail", headers=AUTH).status_code == 404
        assert len(list((settings.data_dir / 'previews' / items['b.fit']['asset_id']).glob('*.jpg'))) == 1
        with app.state.database.write_session() as session:
            session.delete(session.scalar(select(Preview).where(Preview.asset_id == items['b.fit']['asset_id'], Preview.size == 'thumbnail')))
            session.get(AssetTaskItem, items['b.fit']['id']).status = 'interrupted'
            session.get(AssetTaskItem, items['b.fit']['id']).preview_status = 'pending'
            session.get(AssetTask, task_id).status = 'running'
        run_import_task(app.state.database, settings, task_id)
        with app.state.database.read_session() as session:
            resumed = session.scalar(select(Preview).where(Preview.asset_id == items['b.fit']['asset_id'], Preview.size == 'thumbnail'))
            assert resumed.display_parameters == displays['b.fit']
        assert len(list((settings.data_dir / 'previews' / items['b.fit']['asset_id']).glob('*.jpg'))) == 1
    finally:
        client.__exit__(None, None, None)

def test_xisf_and_high_depth_images_stretch_each_photo_independently(tmp_path):
    root = tmp_path / 'science'
    root.mkdir()
    values = np.arange(2400, dtype=np.uint16).reshape(40, 60)
    for name, offset in (('a.xisf', 0), ('b.xisf', 1000)):
        XISF.write(str(root / name), (values + offset)[..., None])
    for name, offset in (('a.tif', 0), ('b.tif', 1000)):
        Image.fromarray(values + offset).save(root / name)
    settings, app, client = make_client(tmp_path, (ImportRoot('science', root),))
    try:
        created = client.post('/api/v1/imports', headers=AUTH, json={'sources': [{'root_id': 'science', 'path': name} for name in ('a.xisf', 'b.xisf', 'a.tif', 'b.tif')], 'storage_mode': 'reference', 'classification': {'frame_class': 'subframe', 'frame_type': 'light'}, 'parameters': {}, 'notes': ''})
        assert created.status_code == 202
        task = client.get(f"/api/v1/asset-tasks/{created.json()['task_id']}", headers=AUTH).json()
        assert task['status'] == 'completed', task
        items = {Path(item['source_path']).name: item for item in task['items']}
        with app.state.database.read_session() as session:
            displays = {name: session.scalar(select(Preview).where(Preview.asset_id == item['asset_id'], Preview.size == 'thumbnail')).display_parameters for name, item in items.items()}
            assert 'preview_stretch_groups' not in session.get(AssetTask, created.json()['task_id']).report
        for first, second in (('a.xisf', 'b.xisf'), ('a.tif', 'b.tif')):
            assert displays[second]['auto_stretch']['highlights'] == pytest.approx(displays[first]['auto_stretch']['highlights'] + 1000)
            assert 'stretch_reference_asset_id' not in displays[second]
            assert 'stretch_group' not in displays[second]
    finally:
        client.__exit__(None, None, None)

def test_xisf_and_heif_imports_create_slot_zero_previews_for_assets_and_references(tmp_path):
    root = tmp_path / 'science'
    root.mkdir()
    xisf_path = root / 'moon.xisf'
    xisf_pixels = np.arange(160 * 90, dtype=np.uint16).reshape(90, 160)
    XISF.write(str(xisf_path), xisf_pixels[..., None])
    heif_path = root / 'phone.heic'
    heif_paths = (heif_path, root / 'phone.heif', root / 'phone.hif')
    register_heif_opener(thumbnails=False)
    Image.new('RGB', (160, 90), (30, 120, 210)).save(heif_path, format='HEIF')
    for path in heif_paths[1:]:
        path.write_bytes(heif_path.read_bytes())
    import_paths = (xisf_path, *heif_paths)
    source_bytes = {path.name: path.read_bytes() for path in import_paths}
    settings, app, client = make_client(tmp_path, (ImportRoot('science', root),))
    try:
        created = client.post('/api/v1/imports', headers=AUTH, json={'sources': [{'root_id': 'science', 'path': path.name} for path in import_paths], 'storage_mode': 'managed', 'classification': {'frame_class': 'subframe', 'frame_type': 'light'}, 'parameters': {}, 'notes': ''})
        assert created.status_code == 202, created.text
        task = client.get(f"/api/v1/asset-tasks/{created.json()['task_id']}", headers=AUTH).json()
        assert task['status'] == 'completed', task
        assert [item['preview_status'] for item in task['items']] == ['available'] * 4
        assets = client.get('/api/v1/library/assets', headers=AUTH).json()['items']
        categorized = {category: [asset for asset in assets if asset['scientific_metadata']['format'] == category] for category in ('xisf', 'image')}
        assert len(categorized['xisf']) == 1 and len(categorized['image']) == 3
        by_format = {'xisf': categorized['xisf'][0], 'image': categorized['image'][0]}
        for asset in (by_format['xisf'], *categorized['image']):
            version = asset
            category = version['scientific_metadata']['format']
            for size in ('thumbnail',):
                response = client.get(f"/api/v1/library/assets/{asset['id']}/previews/{size}", headers=AUTH)
                assert response.status_code == 200
                assert response.headers['content-type'] == 'image/jpeg'
                with Image.open(BytesIO(response.content)) as preview:
                    assert preview.size == (100, 56)
            project = client.post('/api/v1/projects', headers=AUTH, json={'name': category}).json()
            reference = client.post(f"/api/v1/projects/{project['id']}/asset-references", headers=AUTH, json={'base_revision': 1, 'asset_id': version['id']})
            assert reference.status_code == 201, reference.text
            for size in ('thumbnail',):
                response = client.get(f"/api/v1/projects/{project['id']}/asset-references/{reference.json()['id']}/previews/{size}", headers=AUTH)
                assert response.status_code == 200
                assert response.headers['content-type'] == 'image/jpeg'
        xisf_version = by_format['xisf']
        with app.state.database.write_session() as session:
            thumbnail = session.scalar(select(Preview).where(Preview.asset_id == xisf_version['id'], Preview.size == 'thumbnail'))
            session.delete(thumbnail)
        assert backfill_missing_previews(app.state.database, settings) == {'generated': 1, 'failed': 0}
        rebuilt = client.get(f"/api/v1/library/assets/{by_format['xisf']['id']}/previews/thumbnail", headers=AUTH)
        assert rebuilt.status_code == 200 and rebuilt.headers['content-type'] == 'image/jpeg'
        assert {path.name: path.read_bytes() for path in import_paths} == source_bytes
    finally:
        client.__exit__(None, None, None)

def test_interrupted_unpublished_copy_is_removed_before_retry(tmp_path, monkeypatch):
    root = tmp_path / 'science'
    write_fits(root / 'partial.fits')
    _, app, client = make_client(tmp_path, (ImportRoot('science', root),))
    try:
        enumerate_source = owner_enumeration.enumerate_task

        def leave_partial_copy(database, settings, task_id, sources, **options):
            enumerate_source(database, settings, task_id, sources, **options)
            with database.read_session() as session:
                item_id = session.scalar(select(AssetTaskItem.id).where(AssetTaskItem.task_id == task_id))
            stage = settings.data_dir / 'staging' / task_id / f'{item_id}.part'
            stage.parent.mkdir(parents=True, exist_ok=True)
            stage.write_bytes(b'interrupted copy')
        monkeypatch.setattr(owner_enumeration, 'enumerate_task', leave_partial_copy)
        accepted = start_import(client, 'partial.fits', storage_mode='managed')
        task = client.get(f"/api/v1/asset-tasks/{accepted.json()['task_id']}", headers=AUTH).json()
        assert task['status'] == 'completed'
        assert task['items'][0]['content_status'] == 'available'
        assert not (app.state.settings.data_dir / 'staging' / task['id'] / f"{task['items'][0]['id']}.part").exists()
    finally:
        client.__exit__(None, None, None)

@pytest.mark.parametrize('kind', ['fits', 'image', 'video'])
def test_resume_finishes_preview_after_content_was_registered(tmp_path, monkeypatch, kind):
    root = tmp_path / 'science'
    path = root / {'fits': 'frame.fits', 'image': 'frame.png', 'video': 'frame.ser'}[kind]
    if kind == 'fits':
        write_fits(path)
    elif kind == 'image':
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (12, 8), (20, 100, 200)).save(path)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'test SER source')
        monkeypatch.setattr(owner_stages, 'first_video_frame', lambda *_args: (Image.new('RGB', (12, 8), (20, 100, 200)), {'video_frame_index': 0}))
    _, app, client = make_client(tmp_path, (ImportRoot('science', root),))
    try:
        task_id = str(uuid4())
        root_id = str(uuid4())
        parent_item_id = str(uuid4())
        child_item_id = str(uuid4())
        parameters = {'parameter_mode': 'standard', 'cfa_pattern': None}
        with app.state.database.write_session() as session:
            session.add(AssetTask(id=root_id, status='completed', sources=[], storage_mode='reference', classification={}, parameters=parameters, notes=None, dataset_name=None, target_dataset_id=None, dataset_base_revision=None, dataset_id=None, enumeration_completed=True, retry_of_task_id=None, report={}, error=None))
            session.add(AssetTask(id=task_id, status='running', sources=[], storage_mode='reference', classification={}, parameters=parameters, notes=None, dataset_name=None, target_dataset_id=None, dataset_base_revision=None, dataset_id=None, enumeration_completed=True, retry_of_task_id=root_id, report={}, error=None))
            session.flush()
            session.add(AssetTaskItem(id=child_item_id, task_id=task_id, root_item_id=parent_item_id, retry_of_item_id=None, root_id='science', source_path=path.name, source_identity='resume:' + kind, position=0, status='running', content_status='pending', metadata_status='pending', preview_status='pending'))
        from astrophotoflow.modules.data.imports.context import ImportTaskContext
        with app.state.database.read_session() as session:
            task_data = ImportTaskContext.from_task(session.get(AssetTask, task_id))
        task_data.parameters = parameters
        assert owner_stages.materialize_content(app.state.database, app.state.settings, task_data, child_item_id) is None
        with app.state.database.read_session() as session:
            interrupted_item = session.get(AssetTaskItem, child_item_id)
            asset_id = interrupted_item.asset_id
            assert interrupted_item.content_status == 'available'
            assert interrupted_item.status == 'running'
        assert mark_interrupted_tasks(app.state.database) == 1
        with app.state.database.write_session() as session:
            session.get(AssetTask, task_id).status = 'queued'
            session.get(AssetTaskItem, child_item_id).status = 'queued'
        run_import_task(app.state.database, app.state.settings, task_id)
        task = client.get(f'/api/v1/asset-tasks/{task_id}', headers=AUTH).json()
        assert task['status'] == 'completed'
        assert task['items_completed'] == 1
        assert task['items'][0]['content_status'] == 'available'
        assert task['items'][0]['preview_status'] == 'available'
        assert task['items'][0]['asset_id'] == asset_id
        assert client.get('/api/v1/library/assets', headers=AUTH).json()['total'] == 1
    finally:
        client.__exit__(None, None, None)

def test_dataset_filters_require_one_member_to_match_all_conditions(tmp_path):
    settings, app, client = make_client(tmp_path, ())
    try:
        cameras = []
        for name in ('Camera A', 'Camera B'):
            response = client.post('/api/v1/equipment', headers=AUTH, json={'kind': 'camera', 'name': name, 'specs': {}})
            assert response.status_code == 201
            cameras.append(response.json())
        files = []
        for color in ((200, 20, 20), (20, 200, 20)):
            buffer = BytesIO()
            Image.new('RGB', (8, 8), color).save(buffer, format='PNG')
            files.append(buffer.getvalue())
        created = client.post('/api/v1/uploads', headers=AUTH, json={'files': [{'name': 'low.png', 'size': len(files[0])}, {'name': 'high.png', 'size': len(files[1])}], 'classification': {'frame_class': 'subframe', 'frame_type': 'light'}})
        task_id = created.json()['task_id']
        for index, data in enumerate(files):
            client.put(f'/api/v1/uploads/{task_id}/{index}', headers=AUTH, content=data)
        client.post(f'/api/v1/uploads/{task_id}/start', headers=AUTH, json={})
        task = client.get(f'/api/v1/asset-tasks/{task_id}', headers=AUTH).json()
        members = task['items']
        for member, camera, gain, temperature in zip(members, cameras, (10, 100), (-0.5, 0.5)):
            updated = client.patch(f"/api/v1/library/assets/{member['asset_id']}", headers=AUTH, json={'base_revision': 1, 'parameters': {'camera_id': camera['id'], 'gain': gain, 'sensor_temperature_c': temperature}})
            assert updated.status_code == 200
        cross_match = client.get('/api/v1/library/items', headers=AUTH, params=[('camera_id', cameras[0]['id']), ('gain_min', '90')])
        assert cross_match.json()['total'] == 0
        actual_match = client.get('/api/v1/library/items', headers=AUTH, params=[('camera_id', cameras[1]['id']), ('gain_min', '90')])
        assert actual_match.json()['total'] == 1
        positive_temperature = client.get('/api/v1/library/items', headers=AUTH, params=[('camera_id', cameras[1]['id']), ('temperature_min', '1')])
        assert positive_temperature.json()['total'] == 1
        wrong_positive_temperature = client.get('/api/v1/library/items', headers=AUTH, params=[('camera_id', cameras[0]['id']), ('temperature_min', '1')])
        assert wrong_positive_temperature.json()['total'] == 0
        negative_temperature = client.get('/api/v1/library/items', headers=AUTH, params=[('camera_id', cameras[0]['id']), ('temperature_max', '-1')])
        assert negative_temperature.json()['total'] == 1
        facets = client.get('/api/v1/library/filter-options', headers=AUTH).json()
        assert {item['id'] for item in facets['equipment']['camera_id']} == {camera['id'] for camera in cameras}
    finally:
        client.__exit__(None, None, None)

def test_library_sort_runs_before_paging_and_uses_numeric_values(tmp_path):
    _, app, client = make_client(tmp_path, ())
    try:
        with app.state.database.write_session() as session:
            for exposure in range(55):
                session.add(Asset(id=str(uuid4()), name=f'asset-{54 - exposure:03d}', scope='shared', role='raw', **classification_columns({}), **parameter_columns({'exposure_seconds': exposure}), value_sources={}, status='active', revision=1, storage_mode='managed', storage_location='unused.fits'))
        first = client.get('/api/v1/library/items', headers=AUTH, params={'sort_by': 'exposure_seconds', 'order': 'asc', 'limit': 50, 'offset': 0}).json()
        second = client.get('/api/v1/library/items', headers=AUTH, params={'sort_by': 'exposure_seconds', 'order': 'asc', 'limit': 50, 'offset': 50}).json()
        assert first['total'] == second['total'] == 55
        assert first['items'][0]['name'] == 'asset-054'
        assert first['items'][-1]['name'] == 'asset-005'
        assert second['items'][0]['name'] == 'asset-004'
        assert second['items'][-1]['name'] == 'asset-000'
        filtered = client.get('/api/v1/library/items', headers=AUTH, params={'sort_by': 'exposure_seconds', 'order': 'desc', 'exposure_min': 52}).json()
        assert filtered['total'] == 3
        assert [item['summary']['parameters']['exposure_seconds']['value'] for item in filtered['items']] == [54, 53, 52]
    finally:
        client.__exit__(None, None, None)

def test_ser_import_previews_survive_decode_failure_and_backfill_each_item(tmp_path):
    root = tmp_path / 'science'
    root.mkdir()
    width, height = (120, 80)
    header = bytearray(178)
    header[:14] = b'LUCAM-RECORDER'
    struct.pack_into('<7I', header, 14, 0, 0, 1, width, height, 8, 1)
    original = bytes(header) + np.arange(width * height, dtype=np.uint8).tobytes()
    valid = root / 'valid.ser'
    valid.write_bytes(original)
    broken = root / 'broken.ser'
    broken.write_bytes(original[:178])
    settings, app, client = make_client(tmp_path, (ImportRoot('science', root),))
    try:
        accepted = start_import(client, '', sources=[{'root_id': 'science', 'path': 'valid.ser'}, {'root_id': 'science', 'path': 'broken.ser'}], classification={'frame_class': 'video'})
        assert accepted.status_code == 202
        task = client.get(f"/api/v1/asset-tasks/{accepted.json()['task_id']}", headers=AUTH).json()
        by_path = {item['source_path']: item for item in task['items']}
        assert task['status'] == 'completed_with_errors'
        assert by_path['valid.ser']['content_status'] == 'available'
        assert by_path['valid.ser']['preview_status'] == 'available'
        assert by_path['broken.ser']['content_status'] == 'available'
        assert by_path['broken.ser']['preview_status'] == 'failed'
        good_asset = client.get(f"/api/v1/library/assets/{by_path['valid.ser']['asset_id']}", headers=AUTH).json()
        good_version = good_asset
        for size, expected in (('thumbnail', (60, 40)),):
            response = client.get(f"/api/v1/library/assets/{good_asset['id']}/previews/{size}", headers=AUTH)
            assert response.status_code == 200
            assert response.headers['content-type'] == 'image/jpeg'
            with Image.open(BytesIO(response.content)) as preview:
                assert preview.size == expected
        project = client.post('/api/v1/projects', headers=AUTH, json={'name': 'Video project'}).json()
        reference = client.post(f"/api/v1/projects/{project['id']}/asset-references", headers=AUTH, json={'base_revision': project['revision'], 'asset_id': good_version['id']})
        assert reference.status_code == 201, reference.text
        project_preview = client.get(f"/api/v1/projects/{project['id']}/asset-references/{reference.json()['id']}/previews/thumbnail", headers=AUTH)
        assert project_preview.status_code == 200
        assert project_preview.headers['content-type'] == 'image/jpeg'
        assert client.get(f"/api/v1/projects/{project['id']}/asset-references/{reference.json()['id']}/previews/detail", headers=AUTH).status_code == 404
        with app.state.database.write_session() as session:
            thumbnail = session.scalar(select(Preview).where(Preview.asset_id == good_version['id'], Preview.size == 'thumbnail'))
            session.delete(thumbnail)
        assert backfill_missing_previews(app.state.database, settings) == {'generated': 1, 'failed': 1}
        assert client.get(f"/api/v1/library/assets/{good_asset['id']}/previews/thumbnail", headers=AUTH).status_code == 200
        assert valid.read_bytes() == original
        assert broken.read_bytes() == original[:178]
    finally:
        client.__exit__(None, None, None)

def test_queued_cancel_and_selected_retry_keep_task_lineage(tmp_path):
    root = tmp_path / 'science'
    root.mkdir()
    settings, app, client = make_client(tmp_path, (ImportRoot('science', root),))
    try:
        queued_id, failed_item_id = (str(uuid4()), str(uuid4()))
        with app.state.database.write_session() as session:
            session.add(AssetTask(id=queued_id, status='queued', sources=[{'root_id': 'science', 'path': '', 'kind': 'directory', 'enumeration_completed': False}], storage_mode='reference', classification={'frame_class': 'subframe', 'frame_type': 'light'}, parameters={}, notes=None, dataset_name=None, target_dataset_id=None, dataset_base_revision=None, dataset_id=None, enumeration_completed=False, retry_of_task_id=None, report={}, error=None))
            failed_task_id = str(uuid4())
            session.add(AssetTask(id=failed_task_id, status='failed', sources=[{'root_id': 'science', 'path': 'missing.fits', 'kind': 'file', 'enumeration_completed': True}], storage_mode='reference', classification={'frame_class': 'subframe', 'frame_type': 'light'}, parameters={}, notes=None, dataset_name=None, target_dataset_id=None, dataset_base_revision=None, dataset_id=None, enumeration_completed=True, retry_of_task_id=None, report={}, error=None))
            session.add(AssetTaskItem(id=failed_item_id, task_id=failed_task_id, root_item_id=str(uuid4()), retry_of_item_id=None, root_id='science', source_path='missing.fits', source_identity='missing.fits', position=0, status='failed', content_status='failed', metadata_status='unsupported', preview_status='unsupported', error={'code': 'SOURCE_UNAVAILABLE', 'message': 'missing'}))
        cancelled = client.post(f'/api/v1/asset-tasks/{queued_id}/cancel', headers=AUTH, json={})
        assert cancelled.status_code == 202
        assert cancelled.json()['status'] == 'cancelled'
        assert client.post(f'/api/v1/asset-tasks/{queued_id}/resume', headers=AUTH, json={}).status_code == 409
        assert client.get(f'/api/v1/asset-tasks/{queued_id}', headers=AUTH).json()['enumeration_completed'] is False
        assert client.get(f'/api/v1/asset-tasks/{queued_id}', headers=AUTH).json()['items_total'] == 0
        retried = client.post(f'/api/v1/asset-tasks/{failed_task_id}/retry', headers=AUTH, json={'item_ids': [failed_item_id]})
        assert retried.status_code == 202
        retry_id = retried.json()['task_id']
        retry = client.get(f'/api/v1/asset-tasks/{retry_id}', headers=AUTH).json()
        assert retry['retry_of_task_id'] == failed_task_id
        assert retry['items'][0]['retry_of_item_id'] == failed_item_id
        assert retry['items'][0]['status'] == 'failed'
        assert client.get(f'/api/v1/asset-tasks/{failed_task_id}', headers=AUTH).json()['status'] == 'failed'
    finally:
        client.__exit__(None, None, None)

def test_empty_folder_import_does_not_publish_dataset(tmp_path):
    root = tmp_path / 'science'
    (root / 'empty').mkdir(parents=True)
    _, app, client = make_client(tmp_path, (ImportRoot('science', root),))
    try:
        accepted = start_import(client, 'empty')
        task = client.get(f"/api/v1/asset-tasks/{accepted.json()['task_id']}", headers=AUTH).json()
        assert task['status'] == 'failed'
        assert task['dataset_id'] is None
        assert client.get('/api/v1/datasets', headers=AUTH).json()['total'] == 0
    finally:
        client.__exit__(None, None, None)

def test_import_records_persist_after_service_restart(tmp_path):
    root = tmp_path / 'science'
    write_fits(root / 'persist.fits')
    settings, app, client = make_client(tmp_path, (ImportRoot('science', root),))
    imported = start_import(client, 'persist.fits')
    task_id = imported.json()['task_id']
    task = client.get(f'/api/v1/asset-tasks/{task_id}', headers=AUTH).json()
    asset_id = task['items'][0]['asset_id']
    version_id = task['items'][0]['asset_id']
    client.__exit__(None, None, None)
    restarted_app = create_app(settings, TOKEN)
    with TestClient(restarted_app) as restarted:
        persisted_task = restarted.get(f'/api/v1/asset-tasks/{task_id}', headers=AUTH).json()
        persisted_asset = restarted.get(f'/api/v1/library/assets/{asset_id}', headers=AUTH).json()
        assert persisted_task['status'] == 'completed'
        assert persisted_task['items'][0]['asset_id'] == version_id
        assert persisted_asset['id'] == version_id
        assert persisted_asset['content_hash'].startswith('blake3:')

def test_service_restart_preserves_import_progress_for_resume(tmp_path):
    _, app, client = make_client(tmp_path, ())
    task_id = str(uuid4())
    completed_id = str(uuid4())
    running_id = str(uuid4())
    try:
        with app.state.database.write_session() as session:
            session.add(AssetTask(id=task_id, status='running', sources=[], storage_mode='reference', classification={'frame_class': 'subframe', 'frame_type': 'light'}, parameters={}, notes=None, dataset_name=None, target_dataset_id=None, dataset_base_revision=None, dataset_id=None, enumeration_completed=True, retry_of_task_id=None, report={}, error=None))
            session.flush()
            session.add_all([AssetTaskItem(id=completed_id, task_id=task_id, root_item_id=str(uuid4()), retry_of_item_id=None, root_id='science', source_path='completed.fits', source_identity='completed', position=0, status='completed', content_status='available', metadata_status='available', preview_status='available', error=None), AssetTaskItem(id=running_id, task_id=task_id, root_item_id=str(uuid4()), retry_of_item_id=None, root_id='science', source_path='running.fits', source_identity='running', position=1, status='running', content_status='pending', metadata_status='pending', preview_status='pending', error=None)])
        assert mark_interrupted_tasks(app.state.database) == 1
        task = client.get(f'/api/v1/asset-tasks/{task_id}', headers=AUTH).json()
        assert task['status'] == 'interrupted'
        assert task['items_total'] == 2
        assert task['items_completed'] == 1
        assert [item['status'] for item in task['items']] == ['completed', 'interrupted']
        assert task['error']['code'] == 'SERVICE_INTERRUPTED'
    finally:
        client.__exit__(None, None, None)

def test_resume_uses_interrupted_task_id(tmp_path):
    root = tmp_path / 'science'
    write_fits(root / 'resume.fits')
    _, app, client = make_client(tmp_path, (ImportRoot('science', root),))
    task_id = str(uuid4())
    try:
        with app.state.database.write_session() as session:
            session.add(AssetTask(id=task_id, status='interrupted', sources=[{'root_id': 'science', 'path': 'resume.fits', 'kind': 'file', 'enumeration_completed': False}], storage_mode='reference', classification={'frame_class': 'subframe', 'frame_type': 'light'}, parameters={}, notes=None, dataset_name=None, target_dataset_id=None, dataset_base_revision=None, dataset_id=None, enumeration_completed=False, retry_of_task_id=None, report={}, error=None))
        resumed = client.post(f'/api/v1/asset-tasks/{task_id}/resume', headers=AUTH, json={})
        assert resumed.status_code == 202
        assert resumed.json()['task_id'] == task_id
        result = client.get(f'/api/v1/asset-tasks/{task_id}', headers=AUTH).json()
        assert result['status'] == 'completed'
        assert len(result['items']) == 1
    finally:
        client.__exit__(None, None, None)

def test_cancel_during_enumeration_keeps_only_registered_items(tmp_path, monkeypatch):
    root = tmp_path / 'science'
    write_fits(root / 'batch' / 'a.fits', 1)
    write_fits(root / 'batch' / 'b.fits', 2)
    settings, app, client = make_client(tmp_path, (ImportRoot('science', root),))
    task_id = str(uuid4())
    with app.state.database.write_session() as session:
        session.add(AssetTask(id=task_id, status='queued', sources=[{'root_id': 'science', 'path': 'batch', 'kind': 'directory', 'enumeration_completed': False}], storage_mode='reference', classification={'frame_class': 'subframe', 'frame_type': 'light'}, parameters={}, notes=None, dataset_name='batch', target_dataset_id=str(uuid4()), dataset_base_revision=None, dataset_id=None, enumeration_completed=False, retry_of_task_id=None, report={}, error=None))
    original = owner_enumeration.register_source_item

    def register_then_cancel(database, current_task_id, entry, position, known, **kwargs):
        original(database, current_task_id, entry, position, known, **kwargs)
        with database.write_session() as session:
            session.get(AssetTask, current_task_id).status = 'cancelling'
    monkeypatch.setattr(owner_enumeration, 'register_source_item', register_then_cancel)
    try:
        run_import_task(app.state.database, settings, task_id)
        task = client.get(f'/api/v1/asset-tasks/{task_id}', headers=AUTH).json()
        assert task['status'] == 'cancelled'
        assert task['enumeration_completed'] is False
        assert len(task['items']) == 1
        assert task['items'][0]['status'] == 'cancelled'
        assert task['dataset_id'] is None
    finally:
        client.__exit__(None, None, None)

def test_metadata_failure_keeps_content_and_retry_does_not_recreate_asset(tmp_path, monkeypatch):
    root = tmp_path / 'science'
    original_bytes = write_fits(root / 'retry.fits')
    _, app, client = make_client(tmp_path, (ImportRoot('science', root),))
    try:
        original_inspect_fits = owner_stages.inspect_fits

        def fail_metadata(*_args, **_kwargs):
            raise ValueError('injected metadata failure')
        monkeypatch.setattr(owner_stages, 'inspect_fits', fail_metadata)
        accepted = start_import(client, 'retry.fits')
        monkeypatch.setattr(owner_stages, 'inspect_fits', original_inspect_fits)
        original = client.get(f"/api/v1/asset-tasks/{accepted.json()['task_id']}", headers=AUTH).json()
        original_item = original['items'][0]
        assert original['status'] == 'completed_with_errors'
        assert original_item['content_status'] == 'available'
        assert original_item['metadata_status'] == 'failed'
        asset_id = original_item['asset_id']
        assert client.get('/api/v1/library/assets', headers=AUTH).json()['total'] == 1
        (root / 'retry.fits').unlink()
        retried = client.post(f"/api/v1/asset-tasks/{original['id']}/retry", headers=AUTH, json={'item_ids': [original_item['id']]})
        assert retried.status_code == 202
        retry = client.get(f"/api/v1/asset-tasks/{retried.json()['task_id']}", headers=AUTH).json()
        assert retry['retry_of_task_id'] == original['id']
        assert retry['items'][0]['asset_id'] == asset_id
        assert retry['items'][0]['content_status'] == 'available'
        assert retry['items'][0]['metadata_status'] == 'failed'
        assert client.get('/api/v1/library/assets', headers=AUTH).json()['total'] == 1
        (root / 'retry.fits').write_bytes(original_bytes)
        retried_again = client.post(f"/api/v1/asset-tasks/{retry['id']}/retry", headers=AUTH, json={'item_ids': [retry['items'][0]['id']]})
        assert retried_again.status_code == 202
        completed = client.get(f"/api/v1/asset-tasks/{retried_again.json()['task_id']}", headers=AUTH).json()
        assert completed['items'][0]['asset_id'] == asset_id
        assert completed['items'][0]['content_status'] == 'available'
        assert completed['items'][0]['metadata_status'] == 'available'
        assert client.get('/api/v1/library/assets', headers=AUTH).json()['total'] == 1
    finally:
        client.__exit__(None, None, None)

def test_dataset_revision_conflict_keeps_assets_for_manual_append(tmp_path):
    root = tmp_path / 'science'
    write_fits(root / 'batch' / 'first.fits', 1)
    settings, app, client = make_client(tmp_path, (ImportRoot('science', root),))
    try:
        initial = start_import(client, 'batch')
        initial_task = client.get(f"/api/v1/asset-tasks/{initial.json()['task_id']}", headers=AUTH).json()
        dataset = client.get(f"/api/v1/datasets/{initial_task['dataset_id']}", headers=AUTH).json()
        before_version_id = dataset['id']
        write_fits(root / 'second.fits', 2)
        task_id = str(uuid4())
        with app.state.database.write_session() as session:
            session.add(AssetTask(id=task_id, status='queued', sources=[{'root_id': 'science', 'path': 'second.fits', 'kind': 'file', 'enumeration_completed': False}], storage_mode='reference', classification={'frame_class': 'subframe', 'frame_type': 'light'}, parameters={}, notes=None, dataset_name=dataset['name'], target_dataset_id=dataset['id'], dataset_base_revision=dataset['revision'] - 1, dataset_id=dataset['id'], enumeration_completed=False, retry_of_task_id=None, report={}, error=None))
        run_import_task(app.state.database, settings, task_id)
        failed_publication = client.get(f'/api/v1/asset-tasks/{task_id}', headers=AUTH).json()
        conflict = failed_publication['report']['dataset_publish_error']
        assert failed_publication['status'] == 'completed_with_errors'
        assert conflict['code'] == 'REVISION_CONFLICT'
        assert conflict['dataset_id'] == dataset['id']
        assert conflict['expected_revision'] == dataset['revision'] - 1
        assert conflict['observed_revision'] == dataset['revision']
        pending = conflict['pending_asset_ids']
        assert len(pending) == 1
        assert failed_publication['items'][0]['content_status'] == 'available'
        assert client.get(f"/api/v1/datasets/{dataset['id']}", headers=AUTH).json()['id'] == before_version_id
        current = client.get(f"/api/v1/datasets/{dataset['id']}/members", headers=AUTH).json()
        append = client.put(f"/api/v1/datasets/{dataset['id']}/members", headers=AUTH, json={'base_revision': dataset['revision'], 'asset_ids': [*[member['asset_id'] for member in current['items']], *pending]})
        assert append.status_code == 200
        report_after_append = client.get(f'/api/v1/asset-tasks/{task_id}', headers=AUTH).json()['report']
        assert report_after_append['dataset_publish_error'] == conflict
        appended_members = client.get(f"/api/v1/datasets/{dataset['id']}/members", headers=AUTH).json()['items']
        assert appended_members[-1]['asset_id'] == pending[0]
    finally:
        client.__exit__(None, None, None)

def test_library_removal_is_atomic_persistent_and_preserves_shared_data(tmp_path):
    root = tmp_path / 'science'
    paths = ['group-a/a.fits', 'group-a/b.fits', 'group-b/c.fits', 'group-b/d.fits', 'dark.fits']
    originals = {path: write_fits(root / path, index + 1) for index, path in enumerate(paths)}
    settings, app, client = make_client(tmp_path, (ImportRoot('science', root),))
    try:

        def import_group(paths_to_import):
            accepted = start_import(client, paths_to_import[0], 'managed', sources=[{'root_id': 'science', 'path': path} for path in paths_to_import])
            assert accepted.status_code == 202
            return client.get(f"/api/v1/asset-tasks/{accepted.json()['task_id']}", headers=AUTH).json()
        group_a = import_group(paths[:2])
        group_b = import_group(paths[2:4])
        dark_task = start_import(client, 'dark.fits', 'managed', classification={'frame_class': 'subframe', 'frame_type': 'dark'})
        dark_item = client.get(f"/api/v1/asset-tasks/{dark_task.json()['task_id']}", headers=AUTH).json()['items'][0]
        dataset_a = client.get(f"/api/v1/datasets/{group_a['dataset_id']}", headers=AUTH).json()
        dataset_b = client.get(f"/api/v1/datasets/{group_b['dataset_id']}", headers=AUTH).json()
        client.get(f"/api/v1/datasets/{dataset_a['id']}/members", headers=AUTH).json()
        version_b = client.get(f"/api/v1/datasets/{dataset_b['id']}/members", headers=AUTH).json()
        shared_asset = group_a['items'][0]
        shared_version_id = shared_asset['asset_id']
        extended_b = client.put(f"/api/v1/datasets/{dataset_b['id']}/members", headers=AUTH, json={'base_revision': dataset_b['revision'], 'asset_ids': [member['asset_id'] for member in version_b['items']] + [shared_version_id]})
        assert extended_b.status_code == 200
        dataset_b = client.get(f"/api/v1/datasets/{dataset_b['id']}", headers=AUTH).json()
        project = client.post('/api/v1/projects', headers=AUTH, json={'name': 'entry preservation'}).json()
        asset_reference = client.post(f"/api/v1/projects/{project['id']}/asset-references", headers=AUTH, json={'base_revision': 1, 'asset_id': shared_version_id}).json()
        dataset_reference = client.post(f"/api/v1/projects/{project['id']}/dataset-references", headers=AUTH, json={'base_revision': 2, 'dataset_id': dataset_a['id']}).json()
        options_before = client.get('/api/v1/library/filter-options', headers=AUTH).json()
        assert 'dark' in options_before['frame_types']
        dark_asset = client.get(f"/api/v1/library/assets/{dark_item['asset_id']}", headers=AUTH).json()
        dark_file = settings.data_dir / dark_asset['storage_location']
        dark_content_hash = dark_asset['content_hash']
        shared_before = client.get(f"/api/v1/library/assets/{shared_asset['asset_id']}", headers=AUTH).json()
        shared_content_hash = shared_before['content_hash']
        dark_entry = {'entry_type': 'asset', 'id': dark_asset['id'], 'revision': dark_asset['revision']}
        removed_dark = client.request('DELETE', '/api/v1/library/items', headers=AUTH, json={'items': [dark_entry]})
        assert removed_dark.status_code == 200 and removed_dark.json()['removed_count'] == 1
        repeated_dark = client.request('DELETE', '/api/v1/library/items', headers=AUTH, json={'items': [dark_entry]})
        assert repeated_dark.status_code == 200 and repeated_dark.json()['removed_count'] == 0
        assert 'dark' not in client.get('/api/v1/library/filter-options', headers=AUTH).json()['frame_types']
        assert dark_file.read_bytes() == originals['dark.fits']
        assert 'blake3:' + blake3.blake3(dark_file.read_bytes()).hexdigest() == dark_content_hash
        row_a = {'entry_type': 'dataset', 'id': dataset_a['id'], 'revision': dataset_a['revision']}
        removed_a = client.request('DELETE', '/api/v1/library/items', headers=AUTH, json={'items': [row_a]})
        assert removed_a.status_code == 200 and removed_a.json()['removed_count'] == 1
        visible = client.get('/api/v1/library/items', headers=AUTH).json()
        assert visible['total'] == 1 and visible['items'][0]['id'] == dataset_b['id']
        assert all((item['entry_type'] == 'dataset' for item in visible['items']))
        assert client.get(f"/api/v1/projects/{project['id']}/asset-references/{asset_reference['id']}", headers=AUTH).status_code == 200
        assert client.get(f"/api/v1/projects/{project['id']}/dataset-references/{dataset_reference['id']}", headers=AUTH).status_code == 200
        assert client.get(f"/api/v1/library/assets/{shared_asset['asset_id']}", headers=AUTH).status_code == 200
        assert client.get(f"/api/v1/datasets/{dataset_a['id']}", headers=AUTH).status_code == 200
        shared = client.get(f"/api/v1/library/assets/{shared_asset['asset_id']}", headers=AUTH).json()
        managed = settings.data_dir / shared['storage_location']
        assert managed.read_bytes() == originals[paths[0]]
        assert shared['content_hash'] == shared_content_hash
        assert 'blake3:' + blake3.blake3(managed.read_bytes()).hexdigest() == shared_content_hash
        assert all(((root / path).read_bytes() == content for path, content in originals.items()))
        assert 'light' in client.get('/api/v1/library/filter-options', headers=AUTH).json()['frame_types']
        extra_bytes = write_fits(root / 'extra.fits', 8)
        extra_task = start_import(client, 'extra.fits', 'managed')
        extra_item = client.get(f"/api/v1/asset-tasks/{extra_task.json()['task_id']}", headers=AUTH).json()['items'][0]
        extra_asset = client.get(f"/api/v1/library/assets/{extra_item['asset_id']}", headers=AUTH).json()
        row_b = {'entry_type': 'dataset', 'id': dataset_b['id'], 'revision': dataset_b['revision']}
        extra_entry = {'entry_type': 'asset', 'id': extra_asset['id'], 'revision': extra_asset['revision']}
        mixed = client.request('DELETE', '/api/v1/library/items', headers=AUTH, json={'items': [row_b, extra_entry]})
        assert mixed.status_code == 200 and mixed.json()['removed_count'] == 2
        assert client.get('/api/v1/library/items', headers=AUTH).json()['total'] == 0
        assert client.get(f"/api/v1/datasets/{dataset_b['id']}", headers=AUTH).status_code == 200
        extra_managed = settings.data_dir / extra_asset['storage_location']
        assert extra_managed.read_bytes() == extra_bytes
        assert 'blake3:' + blake3.blake3(extra_managed.read_bytes()).hexdigest() == extra_asset['content_hash']
        rollback_bytes = write_fits(root / 'rollback.fits', 9)
        rollback_task = start_import(client, 'rollback.fits', 'managed')
        rollback_item = client.get(f"/api/v1/asset-tasks/{rollback_task.json()['task_id']}", headers=AUTH).json()['items'][0]
        rollback_asset = client.get(f"/api/v1/library/assets/{rollback_item['asset_id']}", headers=AUTH).json()
        conflicting_group = {**row_b}
        conflict = client.request('DELETE', '/api/v1/library/items', headers=AUTH, json={'items': [{'entry_type': 'asset', 'id': rollback_asset['id'], 'revision': rollback_asset['revision']}, conflicting_group]})
        assert conflict.status_code == 409
        remaining = client.get('/api/v1/library/items', headers=AUTH).json()
        assert remaining['total'] == 1 and remaining['items'][0]['id'] == rollback_asset['id']
        assert (settings.data_dir / rollback_asset['storage_location']).read_bytes() == rollback_bytes
        client.__exit__(None, None, None)
        settings, app, client = make_client(tmp_path, (ImportRoot('science', root),))
        persisted = client.get('/api/v1/library/items', headers=AUTH).json()
        assert persisted['total'] == 1 and persisted['items'][0]['id'] == rollback_asset['id']
    finally:
        client.__exit__(None, None, None)
