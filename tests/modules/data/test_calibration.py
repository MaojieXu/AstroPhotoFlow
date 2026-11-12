from pathlib import Path
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.schema import initialize_database
from astrophotoflow.interfaces.http.app import create_app
from astrophotoflow.modules.data.assets.metadata import classification_columns, set_asset_classification
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetCalibration, DatasetMember
from astrophotoflow.modules.data.imports.completion import publish_dataset
from astrophotoflow.modules.data.imports.models import AssetTask, AssetTaskItem
AUTH = {'Authorization': 'Bearer calibration-test'}

@pytest.fixture
def service(tmp_path):
    settings = Settings('127.0.0.1', 8190, tmp_path / 'data', (), workspace=tmp_path)
    initialize_database(settings)
    app = create_app(settings, 'calibration-test')
    with TestClient(app) as client:
        yield (client, app.state.database, settings)

def photo(service, frame_type, master=False, *, version_type=None, scope='shared', project_id=None):
    _, database, settings = service
    asset_id, = (str(uuid4()),)
    path = settings.data_dir / 'library' / 'objects' / asset_id / 'source.fits'
    path.parent.mkdir(parents=True)
    path.write_bytes(b'synthetic calibration input')
    classification = {'frame_class': 'masterframe' if master else 'subframe', 'frame_type': frame_type if version_type is None else version_type}
    with database.write_session() as session:
        asset = Asset(id=asset_id, name=f'{frame_type}-{asset_id[:4]}', scope=scope, owner_project_id=project_id, role='calibration' if frame_type in {'bias', 'dark', 'flat', 'dark_flat'} else 'raw', **classification_columns(classification), storage_mode='managed', storage_location=path.relative_to(settings.data_dir).as_posix(), availability='available', calibration_level='master' if master else 'individual', capture_snapshot={'parameters': {'gain': 0}, 'classification': classification})
        session.add(asset)
        session.flush()
        session.flush()
    return (asset_id, path)

def group(client, name, ids, notes=None):
    response = client.post('/api/v1/datasets', headers=AUTH, json={'name': name, 'asset_ids': ids, 'notes': notes})
    assert response.status_code == 201, response.text
    return response.json()

def current_dataset(client, dataset):
    current = client.get(f"/api/v1/datasets/{dataset['id']}", headers=AUTH).json()
    members = client.get(f"/api/v1/datasets/{dataset['id']}/members", headers=AUTH).json()['items']
    return {**current, 'members': members}

def publish(client, dataset, ids, **changes):
    return client.put(f"/api/v1/datasets/{dataset['id']}/members", headers=AUTH, json={'base_revision': dataset['revision'], 'asset_ids': ids, 'accept_unknown': True, **changes})

def selection(client, entries):
    existing = client.get('/api/v1/library/trash', headers=AUTH).json()['items']
    keys = {(row['entry_type'], row['id']) for row in existing}
    missing = [entry for entry in entries if (entry['entry_type'], entry['id']) not in keys]
    if missing:
        assert client.request('DELETE', '/api/v1/library/items', headers=AUTH, json={'items': missing}).status_code == 200
    rows = client.get('/api/v1/library/trash', headers=AUTH).json()['items']
    return [{key: next((row for row in rows if row['entry_type'] == entry['entry_type'] and row['id'] == entry['id']))[key] for key in ('entry_type', 'id', 'removed_at', 'revision')} for entry in entries]

def clean(client, items):
    preview = client.post('/api/v1/library/trash/delete-preview', headers=AUTH, json={'items': items})
    assert preview.status_code == 200, preview.text
    return (preview.json(), client.post('/api/v1/library/trash/delete', headers=AUTH, json={'items': items, 'preview_fingerprint': preview.json()['preview_fingerprint']}))

def test_groups_enforce_single_membership_and_preserve_original_and_notes(service):
    client, database, _ = service
    light, _ = photo(service, 'light')
    dark, path = photo(service, 'dark')
    original = group(client, 'mixed import', [light, dark])
    rejected = client.post('/api/v1/datasets', headers=AUTH, json={'name': 'duplicate', 'asset_ids': [dark]})
    assert rejected.status_code == 409
    assert rejected.json()['error']['code'] == 'ASSET_DATASET_OWNERSHIP'
    assert [row['asset_id'] for row in current_dataset(client, original)['members']] == [light, dark]
    targets = client.get('/api/v1/calibration/targets', headers=AUTH).json()['items']
    assert targets == []
    light_items = client.get('/api/v1/library/items', headers=AUTH, params={'frame_type': 'light'}).json()['items']
    mixed = next((item for item in light_items if item['id'] == original['id']))
    assert mixed['member_count'] == 2
    assert client.get(f"/api/v1/datasets/{mixed['id']}/members", headers=AUTH).json()['total'] == 2
    assert mixed['matching_member_count'] == 1
    assert publish(client, original, [light]).status_code == 200
    moved = group(client, 'cold night calibration', [dark], '-10 C / gain 0')
    assert moved['notes'] == '-10 C / gain 0' and moved['revision'] == 1
    assert [row['asset_id'] for row in current_dataset(client, moved)['members']] == [dark]
    with database.read_session() as session:
        assert session.scalar(select(func.count()).select_from(Asset)) == 2
    assert path.read_bytes() == b'synthetic calibration input'

def test_target_scope_current_type_and_sparse_validation(service):
    client, database, _ = service
    asset_id, _ = photo(service, 'dark', True)
    light, _ = photo(service, 'light')
    consumer = group(client, 'light inputs', [light])
    newer = str(uuid4())
    assert publish(client, consumer, [light], calibration={'dark': {'kind': 'asset', 'id': asset_id}}).status_code == 200
    consumer = client.get(f"/api/v1/datasets/{consumer['id']}", headers=AUTH).json()
    with database.write_session() as session:
        set_asset_classification(session.get(Asset, asset_id), {'frame_class': 'masterframe', 'frame_type': 'light'})
    assert publish(client, consumer, [light], calibration={'dark': {'kind': 'asset', 'id': asset_id}}).status_code == 422
    missing = publish(client, consumer, [light], calibration={'dark': {'kind': 'asset', 'id': newer}})
    assert missing.status_code == 409 and missing.json()['error']['code'] == 'REFERENCE_UNAVAILABLE'
    assert publish(client, consumer, [light], member_calibration_overrides={str(uuid4()): {'dark': None}}).status_code == 422
    assert publish(client, consumer, [light], calibration=None).status_code == 422
    project = client.post('/api/v1/projects', headers=AUTH, json={'name': 'private'}).json()
    private, _ = photo(service, 'dark', True, scope='project', project_id=project['id'])
    assert publish(client, consumer, [light], calibration={'dark': {'kind': 'asset', 'id': private}}).status_code == 422

def test_surviving_dataset_binding_protects_target_before_unlink(service):
    client, _, _ = service
    light, _ = photo(service, 'light')
    target_id, path = photo(service, 'dark', True)
    consumer = group(client, 'protected consumer', [light])
    assert publish(client, consumer, [light], calibration={'dark': {'kind': 'asset', 'id': target_id}}).status_code == 200
    entry = {'entry_type': 'asset', 'id': target_id, 'revision': 1}
    items = selection(client, [entry])
    preview, deleted = clean(client, items)
    assert any((ref['kind'] == 'calibration' for ref in preview['references']))
    assert deleted.status_code == 409 and deleted.json()['error']['code'] == 'REFERENCES_EXIST'
    assert path.is_file()
    consumer = client.get(f"/api/v1/datasets/{consumer['id']}", headers=AUTH).json()
    assert publish(client, consumer, [light], calibration={}).status_code == 200
    next_preview, removed = clean(client, items)
    assert next_preview['references'] == []
    assert removed.status_code == 200 and not path.exists()

@pytest.mark.parametrize('reverse', [False, True])
def test_selected_consumer_and_target_retention_can_complete_on_retry(service, reverse):
    client, database, _ = service
    light, _ = photo(service, 'light')
    target_id, target_path = photo(service, 'dark', True)
    ids = [light]
    consumer = group(client, 'selected consumer', ids)
    bound = publish(client, consumer, ids, calibration={'dark': {'kind': 'asset', 'id': target_id}})
    assert bound.status_code == 200
    consumer = client.get(f"/api/v1/datasets/{consumer['id']}", headers=AUTH).json()
    entries = [{'entry_type': 'dataset', 'id': consumer['id'], 'revision': consumer['revision']}, {'entry_type': 'asset', 'id': target_id, 'revision': 1}]
    if reverse:
        entries.reverse()
    preview, first = clean(client, selection(client, entries))
    assert first.status_code == 200, first.text
    assert not any((ref['kind'] == 'calibration' for ref in preview['references']))
    with database.read_session() as session:
        assert session.get(Dataset, consumer['id']) is None
        assert session.get(Asset, target_id) is not None
    assert target_path.is_file()
    retry = selection(client, [entries[0] if entries[0]['entry_type'] == 'asset' else entries[1]])
    _, second = clean(client, retry)
    assert second.status_code == 200 and second.json()['deleted_count'] == 1
    assert not target_path.exists()

def test_consumer_file_failure_retains_target_until_consumer_can_finish(service, monkeypatch):
    client, database, _ = service
    light, light_path = photo(service, 'light')
    target_id, path = photo(service, 'dark', True)
    consumer = group(client, 'locked consumer', [light])
    assert publish(client, consumer, [light], calibration={'dark': {'kind': 'asset', 'id': target_id}}).status_code == 200
    consumer = client.get(f"/api/v1/datasets/{consumer['id']}", headers=AUTH).json()
    entries = [{'entry_type': 'dataset', 'id': consumer['id'], 'revision': consumer['revision']}, {'entry_type': 'asset', 'id': target_id, 'revision': 1}]
    original = Path.unlink

    def locked(selected_path, *args, **kwargs):
        if selected_path == light_path:
            raise PermissionError('controlled consumer file lock')
        return original(selected_path, *args, **kwargs)
    monkeypatch.setattr(Path, 'unlink', locked)
    _, first = clean(client, selection(client, entries))
    assert first.status_code == 200 and first.json()['failed']
    with database.read_session() as session:
        assert session.get(Dataset, consumer['id']) is not None
        assert session.get(Asset, target_id) is not None
    assert path.is_file()
    monkeypatch.setattr(Path, 'unlink', original)
    _, resumed = clean(client, selection(client, entries))
    assert resumed.status_code == 200
    with database.read_session() as session:
        assert session.get(Dataset, consumer['id']) is None
    target_entry = next((entry for entry in entries if entry['entry_type'] == 'asset'))
    assert clean(client, selection(client, [target_entry]))[1].json()['deleted_count'] == 1

@pytest.mark.parametrize('frame_type', ['bias', 'dark', 'flat', 'dark_flat'])
def test_all_calibration_types_accept_only_fixed_master_targets(service, frame_type):
    client, _, _ = service
    consumer_frame, _ = photo(service, 'flat' if frame_type == 'dark_flat' else 'light')
    raw, _ = photo(service, frame_type)
    master, _ = photo(service, frame_type, True)
    target_group = group(client, frame_type + ' raw group', [raw])
    consumer = group(client, 'consumer', [consumer_frame])
    for rejected in ({'kind': 'dataset', 'id': target_group['id']}, {'kind': 'asset', 'id': raw}):
        assert publish(client, consumer, [consumer_frame], calibration={frame_type: rejected}).status_code == 422
    assert publish(client, consumer, [consumer_frame], calibration={frame_type: {'kind': 'asset', 'id': master}}).status_code == 200
    options = client.get('/api/v1/calibration/targets', headers=AUTH, params={'frame_type': frame_type}).json()['items']
    assert {item['target']['id'] for item in options} == {master}

@pytest.mark.parametrize('reverse', [False, True])
def test_raw_group_cannot_be_bound_and_remains_independently_removable(service, reverse):
    client, database, _ = service
    light, _ = photo(service, 'light')
    raw, target_path = photo(service, 'flat')
    target_group = group(client, 'flat inputs', [raw])
    consumer = group(client, 'light consumer', [light])
    assert publish(client, consumer, [light], calibration={'flat': {'kind': 'dataset', 'id': target_group['id']}}).status_code == 422
    entries = [{'entry_type': 'dataset', 'id': target_group['id'], 'revision': target_group['revision']}, {'entry_type': 'dataset', 'id': consumer['id'], 'revision': consumer['revision']}]
    if reverse:
        entries.reverse()
    assert clean(client, selection(client, entries))[1].status_code == 200
    with database.read_session() as session:
        assert session.get(Dataset, consumer['id']) is None
        assert session.get(Dataset, target_group['id']) is None
    assert not target_path.exists()

def test_removed_master_cannot_gain_a_calibration_reference(service):
    client, _, _ = service
    light, _ = photo(service, 'light')
    asset_id, path = photo(service, 'dark', True)
    consumer = group(client, 'new external consumer', [light])
    items = selection(client, [{'entry_type': 'asset', 'id': asset_id, 'revision': 1}])
    initial = client.post('/api/v1/library/trash/delete-preview', headers=AUTH, json={'items': items}).json()
    rejected = publish(client, consumer, [light], calibration={'dark': {'kind': 'asset', 'id': asset_id}})
    assert rejected.status_code == 409 and rejected.json()['error']['code'] == 'REFERENCE_UNAVAILABLE'
    assert current_dataset(client, consumer)['calibration'] == {}
    deleted = client.post('/api/v1/library/trash/delete', headers=AUTH, json={'items': items, 'preview_fingerprint': initial['preview_fingerprint']})
    assert deleted.status_code == 200 and not path.exists()

def test_selected_protected_target_retains_shared_managed_path_until_retry(service):
    client, database, settings = service
    light, _ = photo(service, 'light')
    target_id, path = photo(service, 'dark', True)
    with database.write_session() as session:
        session.get(Asset, light).storage_location = path.relative_to(settings.data_dir).as_posix()
    consumer = group(client, 'shared path consumer', [light])
    assert publish(client, consumer, [light], calibration={'dark': {'kind': 'asset', 'id': target_id}}).status_code == 200
    consumer = client.get(f"/api/v1/datasets/{consumer['id']}", headers=AUTH).json()
    entries = [{'entry_type': 'dataset', 'id': consumer['id'], 'revision': consumer['revision']}, {'entry_type': 'asset', 'id': target_id, 'revision': 1}]
    manifest = settings.data_dir / 'library' / consumer['library_directory'] / 'dataset.json'
    assert manifest.is_file()
    first = clean(client, selection(client, entries))[1]
    assert first.status_code == 200 and first.json()['deleted_file_count'] == 1
    assert not manifest.exists()
    assert path.read_bytes() == b'synthetic calibration input'
    with database.read_session() as session:
        assert session.get(Dataset, consumer['id']) is None
    remaining = client.get('/api/v1/library/trash', headers=AUTH).json()['items']
    retry = [{key: row[key] for key in ('entry_type', 'id', 'removed_at', 'revision')} for row in remaining]
    resumed = clean(client, retry)[1]
    assert resumed.json()['deleted_file_count'] == 1, resumed.text
    assert not path.exists()

def test_import_append_uses_dataset_calibration(service):
    client, database, _ = service
    light, _ = photo(service, 'light')
    added_asset, _ = photo(service, 'light')
    target, _ = photo(service, 'dark', True)
    consumer = group(client, 'append scene', [light])
    defaults = {'dark': None}
    assert publish(client, consumer, [light], calibration=defaults).status_code == 200
    consumer = client.get(f"/api/v1/datasets/{consumer['id']}", headers=AUTH).json()
    task_id = str(uuid4())
    with database.write_session() as session:
        session.add(AssetTask(id=task_id, status='running', sources=[], storage_mode='reference', classification={}, parameters={}, target_dataset_id=consumer['id'], dataset_base_revision=consumer['revision'], enumeration_completed=True, report={}))
        session.flush()
        session.add(AssetTaskItem(id=str(uuid4()), task_id=task_id, root_item_id=str(uuid4()), root_id='test', source_path='added.fit', source_identity='append-added', position=0, status='completed', content_status='available', metadata_status='available', preview_status='available', asset_id=added_asset))
    from astrophotoflow.modules.data.imports.context import ImportTaskContext
    with database.read_session() as session:
        context = ImportTaskContext.from_task(session.get(AssetTask, task_id))
    assert publish_dataset(database, context, task_id)
    current = client.get(f"/api/v1/datasets/{consumer['id']}", headers=AUTH).json()
    appended = current_dataset(client, current)
    assert appended['calibration'] == defaults
    assert [member['asset_id'] for member in appended['members']] == [light, added_asset]

@pytest.mark.parametrize('both', [False, True])
def test_database_requires_one_target_or_explicit_disable(service, both):
    client, database, _ = service
    light, _ = photo(service, 'light')
    dark, _ = photo(service, 'dark', True)
    consumer = group(client, 'invalid relation', [light])
    fixed = current_dataset(client, consumer)
    with pytest.raises(IntegrityError, match='_target'), database.write_session() as session:
        values = {'frame_type': 'dark', 'disabled': both, 'asset_id': dark if both else None}
        record = DatasetCalibration(dataset_id=fixed['id'], **values)
        session.add(record)
        session.flush()

@pytest.mark.parametrize('consumer_type,slot,accepted', [('light', 'dark_flat', False), ('flat', 'flat', False), ('flat', 'dark_flat', True), ('dark', 'bias', True), ('dark_flat', 'bias', True), ('bias', 'bias', False)])
def test_complete_publication_checks_consumer_slot_purpose_without_science_requirements(service, consumer_type, slot, accepted):
    client, _, _ = service
    consumer_version, _ = photo(service, consumer_type)
    master, _ = photo(service, slot, True)
    consumer = group(client, 'purpose consumer', [consumer_version])
    result = publish(client, consumer, [consumer_version], calibration={slot: {'kind': 'asset', 'id': master}})
    assert result.status_code == (200 if accepted else 422), result.text
    if not accepted:
        assert current_dataset(client, consumer)['calibration'] == {}
