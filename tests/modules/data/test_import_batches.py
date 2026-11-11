import astrophotoflow.modules.data.imports.stages as owner_stages
import astrophotoflow.modules.data.imports.enumeration as owner_enumeration
from uuid import uuid4
import numpy as np
import pytest
from astropy.io import fits
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.schema import database_lock, initialize_database
from astrophotoflow.interfaces.http.app import create_app
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.imports.models import AssetTask
AUTH = {'Authorization': 'Bearer test-token'}

@pytest.fixture
def environment(tmp_path):
    workspace = tmp_path / 'workspace'
    settings = Settings('127.0.0.1', 8190, workspace / 'data', (), workspace=workspace)
    with database_lock(settings):
        initialize_database(settings)
    app = create_app(settings, 'test-token')
    source = tmp_path / 'night'
    source.mkdir()
    with TestClient(app) as client:
        yield (source, client, app.state.database)

def write_fits(path, *, target='M31', frame='Light Frame', filt='L'):
    path.parent.mkdir(parents=True, exist_ok=True)
    hdu = fits.PrimaryHDU(np.arange(256, dtype=np.float32).reshape(16, 16))
    hdu.header['OBJECT'], hdu.header['IMAGETYP'], hdu.header['FILTER'] = (target, frame, filt)
    hdu.header['EXPTIME'], hdu.header['GAIN'], hdu.header['DATE-OBS'] = (0, 0, '2026-10-30T23:00:00')
    hdu.writeto(path)

def inspect(client, path):
    result = client.post('/api/v1/import-inspections', headers=AUTH, json={'paths': [str(path)]})
    assert result.status_code == 200, result.text
    return result.json()

def submission(scan, **overrides):
    return {'scan_id': scan['scan_id'], 'request_id': str(uuid4()), 'groups': [{'name': 'Confirmed group', 'group_id': group['id']} for group in scan['groups']], **overrides}

def test_recursive_inspection_is_non_ingesting_header_first_and_paged(environment):
    source, client, db = environment
    write_fits(source / 'M42_Dark_R_120s.fits')
    write_fits(source / 'sub' / 'second.fits', filt='R')
    (source / 'notes.txt').write_text('not scientific data')
    scan = inspect(client, source)
    assert scan['file_count'] == 2 and scan['excluded_count'] == 1 and (scan['groups_total'] == 2)
    page = client.get(f"/api/v1/import-inspections/{scan['scan_id']}/entries?limit=1", headers=AUTH).json()
    assert page['total'] == 2 and len(page['items']) == 1
    entry = page['items'][0]
    assert entry['suggested']['target_name'] == {'value': 'M31', 'source': 'header'}
    assert entry['suggested']['exposure_seconds']['value'] == 0
    assert any((issue['code'] == 'HEADER_NAME_CONFLICT' for issue in entry['issues']))
    with db.read_session() as session:
        assert session.scalar(select(func.count()).select_from(Asset)) == 0
        assert session.scalar(select(func.count()).select_from(AssetTask)) == 0

def test_submit_groups_once_preserves_order_values_and_project_versions(environment):
    source, client, db = environment
    write_fits(source / 'a.fits')
    write_fits(source / 'b.fits')
    scan = inspect(client, source)
    project = client.post('/api/v1/projects', headers=AUTH, json={'name': 'Confirmed project'}).json()
    members = client.get(f"/api/v1/import-inspections/{scan['scan_id']}/entries", headers=AUTH).json()['items']
    body = submission(scan, groups=[{'name': 'Reverse order', 'member_ids': [item['id'] for item in reversed(members)], 'options': {'parameters': {'gain': 0}, 'notes': None}}], project_id=project['id'], project_revision=project['revision'])
    accepted = client.post('/api/v1/import-batches', headers=AUTH, json=body)
    assert accepted.status_code == 202, accepted.text
    status = client.post('/api/v1/import-batches/wait', headers=AUTH, json={'request_id': body['request_id'], 'wait_seconds': 0}).json()
    assert status['state'] == 'completed', status
    assert status['groups'][0]['project_link']['state'] == 'linked'
    duplicate = client.post('/api/v1/import-batches', headers=AUTH, json=body)
    assert duplicate.status_code == 202 and duplicate.json()['groups'][0]['task_id'] == accepted.json()['groups'][0]['task_id']
    task_id = status['groups'][0]['task_id']
    task = client.get(f'/api/v1/asset-tasks/{task_id}', headers=AUTH).json()
    assert [item['source_path'] for item in task['items']] == [str(source / 'b.fits'), str(source / 'a.fits')]
    links = client.get(f"/api/v1/projects/{project['id']}/dataset-references", headers=AUTH).json()
    assert links['total'] == 1
    with db.read_session() as session:
        assert session.scalar(select(func.count()).select_from(AssetTask)) == 1
    body['groups'][0]['name'] = 'Different content'
    assert client.post('/api/v1/import-batches', headers=AUTH, json=body).status_code == 409

def test_all_groups_validate_before_any_acceptance_and_new_files_do_not_expand_scope(environment):
    source, client, db = environment
    write_fits(source / 'one.fits')
    write_fits(source / 'two.fits', filt='R')
    scan = inspect(client, source)
    body = submission(scan)
    with (source / 'two.fits').open('ab') as stream:
        stream.write(b'changed')
    rejected = client.post('/api/v1/import-batches', headers=AUTH, json=body)
    assert rejected.status_code == 409 and rejected.json()['error']['code'] == 'SOURCE_CHANGED'
    with db.read_session() as session:
        assert session.scalar(select(func.count()).select_from(AssetTask)) == 0
    scan = inspect(client, source / 'one.fits')
    write_fits(source / 'new.fits')
    accepted = client.post('/api/v1/import-batches', headers=AUTH, json=submission(scan))
    assert accepted.status_code == 202, accepted.text
    with db.read_session() as session:
        assert session.scalar(select(func.count()).select_from(Asset)) == 1

def test_duplicate_members_and_unknown_groups_fail_without_tasks(environment):
    source, client, db = environment
    write_fits(source / 'one.fits')
    scan = inspect(client, source)
    body = submission(scan)
    body['groups'] *= 2
    assert client.post('/api/v1/import-batches', headers=AUTH, json=body).status_code == 422
    body = submission(scan, groups=[{'name': 'Unknown', 'group_id': str(uuid4())}])
    assert client.post('/api/v1/import-batches', headers=AUTH, json=body).status_code == 422
    with db.read_session() as session:
        assert session.scalar(select(func.count()).select_from(AssetTask)) == 0

def test_partial_failure_is_reported_and_does_not_link_an_incomplete_group(environment):
    source, client, db = environment
    write_fits(source / 'good.fits')
    (source / 'bad.fits').write_text('broken FITS')
    scan = inspect(client, source)
    project = client.post('/api/v1/projects', headers=AUTH, json={'name': 'Target'}).json()
    body = submission(scan, project_id=project['id'], project_revision=project['revision'])
    assert client.post('/api/v1/import-batches', headers=AUTH, json=body).status_code == 202
    result = client.get(f"/api/v1/import-batches/{body['request_id']}", headers=AUTH).json()
    assert result['state'] == 'needs_attention' and result['errors_total'] > 0
    assert all((group['project_link']['state'] in {'linked', 'skipped'} for group in result['groups']))

def test_wait_bounds_interrupted_tasks_and_manifest_survives_reopening(environment):
    source, client, db = environment
    write_fits(source / 'one.fits')
    scan = inspect(client, source)
    body = submission(scan)
    accepted = client.post('/api/v1/import-batches', headers=AUTH, json=body)
    task_id = accepted.json()['groups'][0]['task_id']
    with db.write_session() as session:
        session.get(AssetTask, task_id).status = 'interrupted'
    result = client.post('/api/v1/import-batches/wait', headers=AUTH, json={'request_id': body['request_id'], 'wait_seconds': 20})
    assert result.json()['state'] == 'needs_attention' and result.json()['next_poll_seconds'] is None
    assert client.get(f"/api/v1/import-inspections/{scan['scan_id']}", headers=AUTH).json()['file_count'] == 1
    assert client.post('/api/v1/import-batches/wait', headers=AUTH, json={'request_id': body['request_id'], 'wait_seconds': 21}).status_code == 422

def test_project_conflict_retries_linking_without_ingesting_again(environment, monkeypatch):
    from astrophotoflow.modules.data.imports import batches as import_batches
    source, client, db = environment
    write_fits(source / 'one.fits')
    scan = inspect(client, source)
    project = client.post('/api/v1/projects', headers=AUTH, json={'name': 'Target'}).json()
    finalize = import_batches.finalize_project_links
    monkeypatch.setattr(import_batches, 'finalize_project_links', lambda *args: None)
    body = submission(scan, project_id=project['id'], project_revision=project['revision'])
    client.post('/api/v1/import-batches', headers=AUTH, json=body)
    edited = client.patch(f"/api/v1/projects/{project['id']}", headers=AUTH, json={'base_revision': 1, 'notes': 'Manual change'}).json()
    monkeypatch.setattr(import_batches, 'finalize_project_links', finalize)
    finalize(db, body['request_id'])
    status = client.get(f"/api/v1/import-batches/{body['request_id']}", headers=AUTH).json()
    assert status['groups'][0]['project_link']['code'] == 'REVISION_CONFLICT'
    retried = client.post(f"/api/v1/import-batches/{body['request_id']}/project-references", headers=AUTH, json={'base_revision': edited['revision']})
    assert retried.status_code == 200, retried.text
    status = client.get(f"/api/v1/import-batches/{body['request_id']}", headers=AUTH).json()
    assert status['groups'][0]['project_link']['state'] == 'linked'
    with db.read_session() as session:
        assert session.scalar(select(func.count()).select_from(AssetTask)) == 1

def test_aggregate_wait_cancel_and_resume_preserve_accepted_batch(environment, monkeypatch):
    import astrophotoflow.modules.data.public as imports
    source, client, db = environment
    write_fits(source / 'one.fits')
    scan = inspect(client, source)
    process = imports.run_import_task
    monkeypatch.setattr('astrophotoflow.modules.data.public.run_import_task', lambda *args: None)
    body = submission(scan)
    accepted = client.post('/api/v1/import-batches', headers=AUTH, json=body).json()
    task_id = accepted['groups'][0]['task_id']
    pending = client.post('/api/v1/import-batches/wait', headers=AUTH, json={'request_id': body['request_id'], 'wait_seconds': 0}).json()
    assert pending['state'] == 'running' and pending['next_poll_seconds'] == 5
    assert client.post(f'/api/v1/asset-tasks/{task_id}/cancel', headers=AUTH).json()['status'] == 'cancelled'
    cancelled = client.get(f"/api/v1/import-batches/{body['request_id']}", headers=AUTH).json()
    assert cancelled['state'] == 'needs_attention'
    assert client.post(f'/api/v1/asset-tasks/{task_id}/resume', headers=AUTH).status_code == 409
    with db.write_session() as session:
        session.get(AssetTask, task_id).status = 'interrupted'
    monkeypatch.setattr('astrophotoflow.modules.data.public.run_import_task', process)
    assert client.post(f'/api/v1/asset-tasks/{task_id}/resume', headers=AUTH).status_code == 202
    completed = client.get(f"/api/v1/import-batches/{body['request_id']}", headers=AUTH).json()
    assert completed['state'] == 'completed' and completed['groups'][0]['task_id'] == task_id

def test_large_inspection_summary_does_not_expand_all_members(environment):
    source, client, _ = environment
    for index in range(25):
        write_fits(source / f'{index:03}.fits', target=f'Target {index}')
    scan = inspect(client, source)
    assert scan['file_count'] == 25 and scan['groups_total'] == 25 and (len(scan['groups']) == 10)
    assert all(('member_ids' not in group and group['capture_dates']['earliest'] for group in scan['groups']))
    page = client.get(f"/api/v1/import-inspections/{scan['scan_id']}/entries?kind=groups&offset=10&limit=10", headers=AUTH).json()
    assert len(page['items']) == 10 and page['total'] == 25
    assert not {group['id'] for group in scan['groups']} & {group['id'] for group in page['items']}

@pytest.mark.parametrize('archive', [False, True])
def test_project_link_retry_rejects_a_changed_or_archived_publication(environment, monkeypatch, archive):
    from astrophotoflow.modules.data.imports import batches as import_batches
    source, client, db = environment
    write_fits(source / 'one.fits')
    write_fits(source / 'two.fits')
    scan = inspect(client, source)
    project = client.post('/api/v1/projects', headers=AUTH, json={'name': 'Target'}).json()
    finalize = import_batches.finalize_project_links
    monkeypatch.setattr(import_batches, 'finalize_project_links', lambda *args: None)
    body = submission(scan, project_id=project['id'], project_revision=project['revision'])
    accepted = client.post('/api/v1/import-batches', headers=AUTH, json=body).json()
    task_id = accepted['groups'][0]['task_id']
    edited = client.patch(f"/api/v1/projects/{project['id']}", headers=AUTH, json={'base_revision': 1, 'notes': 'Manual change'}).json()
    monkeypatch.setattr(import_batches, 'finalize_project_links', finalize)
    finalize(db, body['request_id'])
    with db.read_session() as session:
        task = session.get(AssetTask, task_id)
        dataset_id = task.dataset_id
    dataset = client.get(f'/api/v1/datasets/{dataset_id}', headers=AUTH).json()
    if archive:
        changed = client.patch(f'/api/v1/datasets/{dataset_id}', headers=AUTH, json={'base_revision': dataset['revision'], 'status': 'archived'})
    else:
        version = client.get(f'/api/v1/datasets/{dataset_id}/members', headers=AUTH).json()
        changed = client.put(f'/api/v1/datasets/{dataset_id}/members', headers=AUTH, json={'base_revision': dataset['revision'], 'asset_ids': [version['items'][0]['asset_id']]})
    assert changed.status_code in {200, 201}, changed.text
    response = client.post(f"/api/v1/import-batches/{body['request_id']}/project-references", headers=AUTH, json={'base_revision': edited['revision']})
    assert response.status_code == 200, response.text
    status = client.get(f"/api/v1/import-batches/{body['request_id']}", headers=AUTH).json()
    link = status['groups'][0]['project_link']
    assert status['state'] != 'running', status
    assert link['state'] == ('failed' if archive else 'skipped'), status
    assert link['code'] == ('INVALID_REFERENCE' if archive else 'IMPORT_NOT_READY')
    assert (client.get(f"/api/v1/projects/{project['id']}/datasets", headers=AUTH).json())['total'] == 0
    with db.read_session() as session:
        assert session.scalar(select(func.count()).select_from(AssetTask)) == 1

def test_retry_of_first_failed_member_links_actual_published_order(environment, monkeypatch):
    source, client, db = environment
    write_fits(source / 'a.fits')
    write_fits(source / 'b.fits')
    scan = inspect(client, source)
    project = client.post('/api/v1/projects', headers=AUTH, json={'name': 'Recovery'}).json()
    original = owner_enumeration.register_source_item

    def fail_first(database, task_id, entry, position, known, **kwargs):
        if Path(entry['path']).name == 'a.fits':
            entry = {**entry, 'error': {'code': 'SOURCE_UNAVAILABLE', 'message': 'Transient registration failure'}}
        original(database, task_id, entry, position, known, **kwargs)
    from pathlib import Path
    monkeypatch.setattr(owner_enumeration, 'register_source_item', fail_first)
    body = submission(scan, project_id=project['id'], project_revision=project['revision'])
    response = client.post('/api/v1/import-batches', headers=AUTH, json=body)
    assert response.status_code == 202, response.text
    root_id = response.json()['groups'][0]['task_id']
    task = client.get(f'/api/v1/asset-tasks/{root_id}', headers=AUTH).json()
    failed = next((item for item in task['items'] if Path(item['source_path']).name == 'a.fits'))
    monkeypatch.setattr(owner_enumeration, 'register_source_item', original)
    retried = client.post(f'/api/v1/asset-tasks/{root_id}/retry', headers=AUTH, json={'item_ids': [failed['id']]})
    assert retried.status_code == 202, retried.text
    retry_id = retried.json()['task_id']
    with db.read_session() as session:
        published = session.get(AssetTask, retry_id).report['dataset_id']
    response = client.post(f"/api/v1/import-batches/{body['request_id']}/project-references", headers=AUTH, json={'base_revision': project['revision']})
    assert response.status_code == 200, response.text
    status = client.get(f"/api/v1/import-batches/{body['request_id']}", headers=AUTH).json()
    assert status['groups'][0]['project_link']['state'] == 'linked', status
    assert status['groups'][0]['project_link']['dataset_id'] == published
