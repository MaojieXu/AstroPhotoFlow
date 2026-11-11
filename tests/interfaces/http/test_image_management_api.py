"""Real HTTP serialization and routing of the image-management surface."""
from uuid import uuid4
import numpy as np
import pytest
from astropy.io import fits
from fastapi.testclient import TestClient
from astrophotoflow.contracts.datasets import DatasetCreate
from astrophotoflow.contracts.equipment import CameraCreate
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.database.schema import initialize_database
from astrophotoflow.interfaces.http.app import create_app
from astrophotoflow.modules.data.assets.image_metadata import record_import_image_metadata
from astrophotoflow.modules.data.assets.models import Asset, FitsHduMetadata
from astrophotoflow.modules.data.datasets.service import create_dataset
from astrophotoflow.modules.data.equipment.service import create_equipment
from astrophotoflow.modules.data.imports.models import AssetTask, AssetTaskItem
AUTH = {'Authorization': 'Bearer image-http-test'}

@pytest.fixture
def service(tmp_path):
    settings = Settings('127.0.0.1', 8190, tmp_path / 'workspace' / 'data', (), workspace=tmp_path / 'workspace')
    initialize_database(settings)
    app = create_app(settings, 'image-http-test')
    database = Database(settings.database_path)
    with database.write_session() as session:
        images = []
        for index, (name, target, frame, master) in enumerate((
            ('early', 'M31', 'light', False),
            ('late', 'M42', 'light', False),
            ('master', None, 'dark', True),
            ('single', 'M31', 'light', False),
        )):
            asset_id, = (str(uuid4()),)
            asset = Asset(id=asset_id, name=name, scope='shared', role='calibration' if master else 'raw', frame_class='masterframe' if master else 'subframe', frame_type=frame, status='active', revision=1, gain=10 + index, offset=5, exposure_seconds=30, parameter_mode='gain', binning_x=1, binning_y=1, storage_mode='managed', storage_location=f'objects/{asset_id}/source.fits', availability='available', byte_size=5, content_hash='blake3:' + '0' * 64, calibration_level='master' if master else 'individual', capture_snapshot={'parameters': {'gain': 10 + index}, 'classification': {'frame_class': 'masterframe' if master else 'subframe', 'frame_type': frame}}, scientific_metadata={'format': 'fits', 'export_provenance': {'actual_call': 'preserved'}})
            session.add(asset)
            session.flush()
            session.flush()
            record_import_image_metadata(session, asset_id, {'target_name': target, 'times': {'master_created_at' if master else 'capture_start': {'utc': f'2026-11-0{index + 1}T01:00:00Z'}}})
            session.add(FitsHduMetadata(id=str(uuid4()), asset_id=asset_id, hdu_index=0, hdu_type='PRIMARY', shape=[16, 16], parser_version='http-test', is_selected=True, supported_kind='mono', header_cards=[{'keyword': 'OBJECT', 'value': target, 'comment': ''}, {'keyword': 'GAIN', 'value': 10 + index, 'comment': ''}, {'keyword': 'EXPTIME', 'value': 30, 'comment': ''}]))
            images.append({'id': asset_id})
        mixed = create_dataset(session, DatasetCreate(name='Mixed objects', asset_ids=[row['id'] for row in images[:2]]))
        single = create_dataset(session, DatasetCreate(name='Only M31', asset_ids=[images[3]['id']]))
        camera = create_equipment(session, CameraCreate(kind='camera', name='HTTP camera'))
        task_id, request_id = (str(uuid4()), str(uuid4()))
        file_ids = [str(uuid4()), str(uuid4())]
        task = AssetTask(id=task_id, request_id=request_id, request_fingerprint='0' * 64, status='completed', sources=[], storage_mode='managed', classification={}, parameters={}, import_defaults_snapshot={}, target_dataset_id=str(mixed.id), dataset_id=str(mixed.id), enumeration_completed=True, report={}, image_import_plan={'root_task_id': task_id, 'files': {identity: {} for identity in file_ids}, 'publication': {'state': 'published', 'dataset_id': str(mixed.id), 'dataset_revision': mixed.revision, 'published_file_ids': file_ids, 'positions': {row['id']: index for index, row in enumerate(images[:2])}}})
        session.add(task)
        session.flush()
        for index, image in enumerate(images[:2]):
            session.add(AssetTaskItem(id=str(uuid4()), task_id=task_id, root_item_id=file_ids[index], root_id='', source_path=f'image-{index}.fits', source_identity=f'image-{index}.fits', position=index, status='completed', content_status='available', metadata_status='available', preview_status='available', asset_id=image['id']))
    database.close()
    with TestClient(app) as client:
        yield (client, images, mixed.model_dump(mode='json'), single.model_dump(mode='json'), camera.model_dump(mode='json'), task_id, file_ids)

def get(client, path, **params):
    response = client.get('/api/v1' + path, headers=AUTH, params=params)
    assert response.status_code == 200, response.text
    return response.json()

def test_asset_search_http_converts_uuid_dates_numbers_and_limits(service):
    client, images, _, _, camera, _, _ = service
    result = get(client, '/library/assets', image_query=True, target_name='m31', gain_min=10, gain_max=10, captured_from='2026-11-01T00:00:00Z', captured_to='2026-11-01T23:59:59Z', limit=1, offset=0)
    assert result['total'] == 1 and result['items'][0]['asset']['id'] == images[0]['id']
    assert result['limit'] == 1
    master = get(client, '/library/assets', image_query=True, frame_class='masterframe', master_created_from='2026-11-03T00:00:00Z')
    assert master['total'] == 1 and master['items'][0]['asset']['id'] == images[2]['id']
    assert get(client, '/library/assets', image_query=True, camera_id=camera['id'])['total'] == 0
    assert get(client, '/library/assets', image_query=True, exposure_min=31)['total'] == 0

@pytest.mark.parametrize('params', [{'camera_id': 'not-a-uuid'}, {'limit': '201'}, {'limit': '0'}, {'offset': '-1'}, {'captured_from': '2026-11-01T00:00:00'}, {'exposure_min': '-1'}, {'gain_min': 'nan'}, {'gain_min': '12', 'gain_max': '1'}])
def test_asset_search_rejects_invalid_wire_query_values(service, params):
    client, *_ = service
    response = client.get('/api/v1/library/assets', headers=AUTH, params={'image_query': 'true', **params})
    assert response.status_code == 422, response.text

def test_dataset_any_all_and_member_predicates_use_new_http_shape(service):
    client, images, mixed, single, _, _, _ = service
    any_match = get(client, '/datasets', image_query=True, target_name='M31', match='any')
    assert {item['dataset']['id'] for item in any_match['items']} == {mixed['id'], single['id']}
    mixed_result = next((item for item in any_match['items'] if item['dataset']['id'] == mixed['id']))
    assert mixed_result['member_count'] == 2 and mixed_result['matching_member_count'] == 1
    all_match = get(client, '/datasets', image_query=True, target_name='M31', match='all')
    assert [item['dataset']['id'] for item in all_match['items']] == [single['id']]
    members = get(client, f"/datasets/{mixed['id']}/members", image_query=True, target_name='M31', frame_type='light', gain_min=10, gain_max=10, limit=1)
    assert members['total'] == 1 and members['items'][0]['member']['asset_id'] == images[0]['id']
    assert members['items'][0]['metadata']['target_name'] == 'M31'
    detail = get(client, f"/datasets/{mixed['id']}/detail")
    assert detail['dataset']['id'] == mixed['id']
    archived = client.patch(f"/api/v1/library/assets/{images[1]['id']}", headers=AUTH, json={'expected_revision': 1, 'changes': {'status': 'archived'}})
    assert archived.status_code == 200, archived.text
    assert get(client, f"/datasets/{mixed['id']}/members", image_query=True)['total'] == 2
    assert get(client, '/datasets', image_query=True, target_name='M42')['total'] == 1

def test_metadata_batch_scientific_time_round_trip_and_atomic_revision_guard(service):
    client, images, *_ = service
    response = client.post('/api/v1/library/assets/metadata-updates', headers=AUTH, json={'items': [{'asset_id': images[0]['id'], 'expected_revision': 1, 'changes': {'target_name': None, 'parameters': {'gain': 0, 'offset': None}, 'times': {'capture_start': {'raw_value': 'local telescope clock', 'time_system': 'unknown'}, 'capture_end': {'utc': '2026-11-05T01:00:00Z'}}}}, {'asset_id': images[1]['id'], 'expected_revision': 1, 'changes': {'target_name': 'M31', 'times': {'capture_start': {'utc': '2026-11-04T01:00:00Z'}}}}]})
    assert response.status_code == 200, response.text
    first = response.json()['items'][0]
    assert first['asset']['parameters']['gain'] == 0 and first['asset']['parameters']['offset'] is None
    assert first['metadata']['target_name'] is None
    assert first['metadata']['times']['capture_start']['raw_value'] == 'local telescope clock'
    assert first['metadata']['times']['capture_start']['utc'] is None
    assert first['metadata']['times']['capture_end']['utc'] == '2026-11-05T01:00:00Z'
    rejected = client.post('/api/v1/library/assets/metadata-updates', headers=AUTH, json={'items': [{'asset_id': images[0]['id'], 'expected_revision': 2, 'changes': {'parameters': {'gain': 99}}}, {'asset_id': images[1]['id'], 'expected_revision': 1, 'changes': {'name': 'stale'}}]})
    assert rejected.status_code == 409
    assert get(client, f"/library/assets/{images[0]['id']}/detail")['asset']['parameters']['gain'] == 0
    invalid_time = client.patch(f"/api/v1/library/assets/{images[0]['id']}", headers=AUTH, json={'expected_revision': 2, 'changes': {'times': {'capture_start': {'utc': '2026-11-01T00:00:00'}}}})
    assert invalid_time.status_code == 422

def test_equipment_application_http_does_not_overwrite_capture_parameters(service):
    client, images, mixed, _, camera, _, _ = service
    response = client.post('/api/v1/library/assets/equipment-applications', headers=AUTH, json={'assets': [{'asset_id': image['id'], 'expected_revision': 1} for image in images[:2]], 'equipment': {'choice': {'source': 'devices', 'camera': {'equipment_id': camera['id'], 'expected_revision': camera['revision']}}, 'fields': ['camera']}})
    assert response.status_code == 200, response.text
    for index, item in enumerate(response.json()['items']):
        assert item['asset']['parameters']['camera_id'] == camera['id']
        assert item['asset']['parameters']['gain'] == 10 + index
        assert item['equipment_context']['selected_equipment']['camera_id']['name'] == 'HTTP camera'
    result = get(client, '/library/assets', image_query=True, camera_id=camera['id'], limit=1, offset=1)
    assert result['total'] == 2 and len(result['items']) == 1
    selected = get(client, f"/datasets/{mixed['id']}/members", image_query=True, camera_id=camera['id'], parameter_mode='gain', limit=1, offset=1)
    assert selected['total'] == 2 and len(selected['items']) == 1

def test_header_keywords_and_pagination_are_serialized_as_bounded_cards(service):
    client, images, *_ = service
    path = f"/library/assets/{images[0]['id']}/hdus/0/header"
    response = client.get('/api/v1' + path, headers=AUTH, params=[('keywords', 'object'), ('keywords', 'GAIN'), ('limit', '1'), ('offset', '1')])
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['total'] == 2 and result['limit'] == 1 and (result['offset'] == 1)
    assert result['cards'] == [{'keyword': 'GAIN', 'value': 10, 'comment': ''}]
    assert get(client, path, paged=True, limit=1)['total'] == 3
    assert 'total' not in get(client, path)

def test_master_provenance_http_preserves_platform_facts_and_current_declaration(service):
    client, images, *_ = service
    path = f"/library/assets/{images[2]['id']}/master-provenance"
    original = get(client, path)
    assert original['revision'] == 1 and original['platform_provenance'] == {'actual_call': 'preserved'}
    response = client.patch('/api/v1' + path, headers=AUTH, json={'expected_revision': 1, 'changes': {'sources': [{'kind': 'asset', 'asset_id': images[0]['id']}], 'made_at': {'utc': '2026-11-06T00:00:00Z'}, 'processing': {'software_name': 'External tool', 'software_version': '1.0', 'operation': 'user-declared stack', 'parameters': {'rejection': 'sigma', 'offset': 0}}, 'bias_state': 'removed', 'normalized': False, 'debayered': False, 'notes': None}})
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved['asset_revision'] == 2 and saved['revision'] == 2
    assert saved['declaration']['made_at']['utc'] == '2026-11-06T00:00:00Z'
    assert saved['declaration']['normalized'] is False
    assert saved['declaration']['processing']['parameters']['offset'] == 0
    assert saved['platform_provenance'] == original['platform_provenance']
    selected = get(client, path)
    assert selected['declaration'] == saved['declaration']
    stale = client.patch('/api/v1' + path, headers=AUTH, json={'expected_revision': 1, 'changes': {'notes': 'stale'}})
    assert stale.status_code == 409

def test_task_get_image_flag_selects_explicit_receipt_and_pages_stable_file_ids(service):
    client, images, _, _, _, task_id, file_ids = service
    result = get(client, f'/asset-tasks/{task_id}', image_query=True, items_limit=1, items_offset=1)
    assert result['task_id'] == task_id and result['items_total'] == 2
    assert result['items_limit'] == 1 and result['items_offset'] == 1
    assert result['items'][0]['file_id'] == file_ids[1]
    assert result['items'][0]['asset_id'] == images[1]['id']
    assert result['items'][0]['member_position'] == 1
    assert result['items'][0]['publication_status'] == 'published'
    assert result['items'][0]['calibration_status'] == 'Unknown'
    assert result['items'][0]['errors'] == []
    legacy = get(client, f'/asset-tasks/{task_id}', items_limit=1)
    assert legacy['id'] == task_id and 'task_id' not in legacy

def test_explicit_http_import_preserves_all_five_frame_types_and_both_frame_classes(service, tmp_path):
    client, *_ = service
    source = tmp_path / 'classification-matrix'
    source.mkdir()
    combinations = [(frame_type, frame_class) for frame_type in ('light', 'bias', 'dark', 'flat', 'dark_flat') for frame_class in ('subframe', 'masterframe')]
    paths = {}
    for index, (frame_type, frame_class) in enumerate(combinations):
        path = source / f'{frame_type}-{frame_class}.fits'
        fits.PrimaryHDU(np.full((8, 8), index, dtype=np.float32)).writeto(path)
        paths[path.name] = (frame_type, frame_class, path.read_bytes())
    scanned = client.post('/api/v1/import-inspections', headers=AUTH, json={'paths': [str(source)], 'file_facts_only': True})
    assert scanned.status_code == 200, scanned.text
    files = get(client, f"/import-inspections/{scanned.json()['scan_id']}/entries", file_facts_only=True)['items']
    assert len(files) == 10
    imported = set()
    for entry in files:
        from pathlib import Path
        name = Path(entry['path']).name
        frame_type, frame_class, original = paths[name]
        request_id = str(uuid4())
        accepted = client.post('/api/v1/imports', headers=AUTH, json={'request_id': request_id, 'scan_id': scanned.json()['scan_id'], 'files': [{'file_id': entry['file_id'], 'metadata': {'classification': {'frame_type': frame_type, 'frame_class': frame_class}}}], 'destination': {'mode': 'standalone'}})
        assert accepted.status_code == 202, accepted.text
        receipt = get(client, f'/imports/requests/{request_id}')
        assert receipt['status'] == 'completed', receipt
        assert receipt['items'][0]['publication_status'] == 'published'
        detail = get(client, f"/library/assets/{receipt['items'][0]['asset_id']}/detail")
        assert detail['asset']['classification'] == {'frame_type': frame_type, 'frame_class': frame_class}
        assert detail['asset']['capture_snapshot']['classification'] == {'frame_type': frame_type, 'frame_class': frame_class}
        assert (source / name).read_bytes() == original
        imported.add((detail['asset']['classification']['frame_type'], detail['asset']['classification']['frame_class']))
    assert imported == set(combinations)

def test_calibration_relationship_browsing_exposes_names_sources_and_whole_group_summary(service):
    client, images, mixed, *_ = service
    path = f"/datasets/{mixed['id']}/calibration"
    page = get(client, path)
    assert page['dataset_id'] == mixed['id']
    assert page['calibration']['flat'] == {'mode': 'unconfigured'}
    assert page['slots']['flat']['source'] == 'dataset'
    assert page['slots']['flat']['check_state'] == 'not_checked'
    assert 'items' not in page
    standalone = get(client, f"/library/assets/{images[0]['id']}/calibration")
    assert standalone['slots']['flat']['source'] == 'standalone'

def test_calibration_import_precheck_http_does_not_register_scanned_files(service, tmp_path):
    client, images, *_ = service
    source = tmp_path / 'unregistered-light.fits'
    hdu = fits.PrimaryHDU(np.zeros((16, 32), dtype=np.uint16))
    hdu.header['IMAGETYP'] = 'Light Frame'
    hdu.header['EXPTIME'] = 300
    hdu.writeto(source)
    before = get(client, '/library/assets', image_query=True)['total']
    scanned = client.post('/api/v1/import-inspections', headers=AUTH, json={'paths': [str(source)], 'file_facts_only': True})
    assert scanned.status_code == 200, scanned.text
    scan_id = scanned.json()['scan_id']
    entry = get(client, f'/import-inspections/{scan_id}/entries', file_facts_only=True)['items'][0]
    result = client.post('/api/v1/calibration/import-check', headers=AUTH, json={'scan_id': scan_id, 'files': [{'file_id': entry['file_id']}], 'calibration': {'dark': {'mode': 'target', 'target': {'kind': 'asset', 'id': images[2]['id']}}}})
    assert result.status_code == 200, result.text
    assert result.json()['state'] == 'conflict'
    assert result.json()['items'][0]['file_id'] == entry['file_id']
    assert any(
        item['field'] == 'dimensions' and item['severity'] == 'conflict'
        for item in result.json()['items'][0]['diagnostics']
    )
    assert get(client, '/library/assets', image_query=True)['total'] == before
