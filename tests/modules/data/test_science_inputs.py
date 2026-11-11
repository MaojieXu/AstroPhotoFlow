from __future__ import annotations
from pathlib import Path
from uuid import UUID, uuid4
import blake3
import numpy as np
import pytest
from astropy.io import fits
from fastapi.testclient import TestClient
from PIL import Image
from astrophotoflow.core.config import ImportRoot, Settings
from astrophotoflow.core.database.schema import database_lock, initialize_database
from astrophotoflow.core.errors import ApiError
from astrophotoflow.interfaces.http.app import create_app
from astrophotoflow.contracts.inputs import ResolveInputsRequest
from astrophotoflow.contracts.trash import LibraryEntriesRemove
from astrophotoflow.modules.data.science.outputs import check_output
from astrophotoflow.modules.data.science.outputs import get_output_registration
from astrophotoflow.modules.data.science.inputs import observe_reference_inputs
from astrophotoflow.modules.data.science.outputs import register_output
from astrophotoflow.modules.data.science.outputs import render_output_preview
from astrophotoflow.modules.data.science.inputs import resolve_inputs
from astrophotoflow.modules.data.trash.scope import preview_library_removal
from astrophotoflow.modules.data.imports.runner import run_import_task
from astrophotoflow.modules.data.science import inputs as science_input_service, outputs as science_output_service, files as science_files
TOKEN = 'test-token'
AUTH = {'Authorization': f'Bearer {TOKEN}'}

def _write_fits(path: Path, value: int) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    hdu = fits.PrimaryHDU(np.arange(48, dtype=np.int16).reshape(6, 8) + value)
    hdu.header['EXPTIME'] = 30 + value
    fits.HDUList([hdu, fits.ImageHDU(np.ones((3, 4), dtype=np.float32))]).writeto(path, overwrite=True)
    return path.read_bytes()

def _client(tmp_path: Path, root: Path):
    settings = Settings('127.0.0.1', 8190, tmp_path / 'data', ('http://127.0.0.1:8188',), (ImportRoot('science', root),), workspace=tmp_path)
    with database_lock(settings):
        initialize_database(settings)
    client = TestClient(create_app(settings, TOKEN))
    client.__enter__()
    return (settings, client)

def _import(client: TestClient, sources: list[str], storage_mode: str='reference'):
    response = client.post('/api/v1/imports', headers=AUTH, json={'sources': [{'root_id': 'science', 'path': source} for source in sources], 'storage_mode': storage_mode, 'classification': {'frame_class': 'subframe', 'frame_type': 'light'}, 'parameters': {'gain': 42, 'parameter_mode': 'gain'}})
    assert response.status_code == 202, response.text
    task = client.get(f"/api/v1/asset-tasks/{response.json()['task_id']}", headers=AUTH).json()
    assert task['status'] == 'completed', task
    return task

def test_resolve_fixed_asset_copies_reference_and_preserves_fits_selection(tmp_path):
    root = tmp_path / 'science'
    content = _write_fits(root / 'one.fits', 1)
    settings, client = _client(tmp_path, root)
    try:
        task = _import(client, ['one.fits'])
        item = task['items'][0]
        asset = client.get(f"/api/v1/library/assets/{item['asset_id']}", headers=AUTH).json()
        project = client.post('/api/v1/projects', headers=AUTH, json={'name': 'M31'}).json()
        linked = client.post(f"/api/v1/projects/{project['id']}/asset-references", headers=AUTH, json={'base_revision': 1, 'asset_id': item['asset_id']})
        assert linked.status_code == 201, linked.text
        request = ResolveInputsRequest.model_validate({'project_id': project['id'], 'input_mode': 'reproducible', 'references': [{'kind': 'asset', 'asset_id': item['asset_id'], 'selection': {'kind': 'fits_hdu', 'hdu_index': 1}}]})
        resolved = resolve_inputs(client.app.state.database, settings, request, run_directory=tmp_path / 'run')
        assert resolved.required_copy_bytes == len(content)
        assert resolved.copied_bytes == len(content)
        assert resolved.items[0].selection.hdu_index == 1
        assert resolved.items[0].read_path.read_bytes() == content
        assert resolved.items[0].read_path != root / 'one.fits'
        assert resolved.items[0].parameters['gain'] == asset['parameters']['gain']
        reference_request = request.model_copy(update={'input_mode': 'reference'})
        reference_inputs = resolve_inputs(client.app.state.database, settings, reference_request, run_directory=tmp_path / 'reference-run')
        assert reference_inputs.required_copy_bytes == 0
        assert reference_inputs.copied_bytes == 0
        assert reference_inputs.items[0].preparation == 'reference'
        assert reference_inputs.items[0].read_path == root / 'one.fits'
        assert observe_reference_inputs(settings, reference_inputs)[0].state == 'unchanged'
    finally:
        client.__exit__(None, None, None)

def test_content_accept_rejects_restored_original_and_observation_reports_missing_managed_file(tmp_path):
    root = tmp_path / 'science'
    source = root / 'reference.fits'
    original = _write_fits(source, 1)
    settings, client = _client(tmp_path, root)
    try:
        task = _import(client, ['reference.fits'])
        item = task['items'][0]
        changed = _write_fits(source, 2)
        observation = client.post(f"/api/v1/library/assets/{item['asset_id']}/content-observation", headers=AUTH).json()
        assert observation['state'] == 'changed'
        source.write_bytes(original)
        unchanged = client.post(f"/api/v1/library/assets/{item['asset_id']}/content-accept", headers=AUTH, json={'base_revision': observation['base_revision'], 'expected_observed_hash': 'blake3:' + blake3.blake3(original).hexdigest()})
        assert unchanged.status_code == 422
        managed_source = root / 'managed.fits'
        _write_fits(managed_source, 4)
        managed_task = _import(client, ['managed.fits'], storage_mode='managed')
        managed_asset = client.get(f"/api/v1/library/assets/{managed_task['items'][0]['asset_id']}", headers=AUTH).json()
        managed_path = settings.data_dir / managed_asset['storage_location']
        managed_path.unlink()
        missing = client.post(f"/api/v1/library/assets/{managed_asset['id']}/content-observation", headers=AUTH)
        assert missing.status_code == 200
        assert missing.json()['state'] == 'missing'
        assert missing.json()['error']['code'] == 'SOURCE_UNAVAILABLE'
        assert changed != original
    finally:
        client.__exit__(None, None, None)

def test_fixed_dataset_selection_keeps_member_order_and_original_positions(tmp_path):
    root = tmp_path / 'science'
    _write_fits(root / 'a.fits', 1)
    _write_fits(root / 'b.fits', 2)
    settings, client = _client(tmp_path, root)
    try:
        task = _import(client, ['b.fits', 'a.fits'])
        dataset = client.get(f"/api/v1/datasets/{task['dataset_id']}", headers=AUTH).json()
        version = client.get(f"/api/v1/datasets/{dataset['id']}/members", headers=AUTH).json()
        project = client.post('/api/v1/projects', headers=AUTH, json={'name': 'M31'}).json()
        linked = client.post(f"/api/v1/projects/{project['id']}/dataset-references", headers=AUTH, json={'base_revision': 1, 'dataset_id': dataset['id']})
        assert linked.status_code == 201, linked.text
        request = ResolveInputsRequest.model_validate({'project_id': project['id'], 'references': [{'kind': 'dataset', 'dataset_id': dataset['id'], 'asset_ids': [member['asset_id'] for member in version['items']]}]})
        resolved = resolve_inputs(client.app.state.database, settings, request, run_directory=tmp_path / 'dataset-run')
        assert [item.asset_id for item in resolved.items] == [UUID(item['asset_id']) for item in version['items']]
        assert [item.member_index for item in resolved.items] == [0, 1]
        reversed_request = request.model_copy(update={'references': [request.references[0].model_copy(update={'asset_ids': list(reversed(request.references[0].asset_ids))})]})
        reordered = resolve_inputs(client.app.state.database, settings, reversed_request, run_directory=tmp_path / 'reordered-run')
        assert [item.asset_id for item in reordered.items] == [item.asset_id for item in resolved.items]
    finally:
        client.__exit__(None, None, None)

def test_output_registration_accepts_other_extension_and_removal_scope_is_read_only(tmp_path):
    root = tmp_path / 'science'
    settings, client = _client(tmp_path, root)
    try:
        run_directory = tmp_path / 'runs' / 'r2'
        run_directory.mkdir(parents=True)
        output_path = run_directory / 'selected.dat'
        output_path.write_bytes(b'checked output bytes')
        checked = check_output(settings, run_directory=run_directory, path=output_path, expected_format='other')
        task_id = uuid4()
        registered = register_output(client.app.state.database, settings, task_id=task_id, output=checked, name='selected')
        assert registered.created
        run_import_task(client.app.state.database, settings, str(task_id))
        result = get_output_registration(client.app.state.database, settings, task_id)
        assert result.content_status == 'available'
        assert result.metadata_status == 'unsupported'
        assert result.preview_status == 'unsupported'
        output_path.unlink()
        assert get_output_registration(client.app.state.database, settings, task_id).asset_id == result.asset_id
        asset = client.get(f'/api/v1/library/assets/{result.asset_id}', headers=AUTH).json()
        selection = LibraryEntriesRemove.model_validate({'items': [{'entry_type': 'asset', 'id': asset['id'], 'revision': asset['revision']}]})
        scope = preview_library_removal(client.app.state.database, selection)
        assert scope.asset_ids == [UUID(asset['id'])]
        assert scope.asset_ids == [UUID(asset['id'])]
        assert scope.data_token
        assert client.get(f"/api/v1/library/assets/{asset['id']}", headers=AUTH).status_code == 200
    finally:
        client.__exit__(None, None, None)

def test_checked_output_preview_and_registration_reuse_asset_task(tmp_path):
    root = tmp_path / 'science'
    root.mkdir()
    settings, client = _client(tmp_path, root)
    try:
        run_directory = tmp_path / 'runs' / 'r1'
        run_directory.mkdir(parents=True)
        output_path = run_directory / 'stacked.fits'
        original = _write_fits(output_path, 7)
        checked = check_output(settings, run_directory=run_directory, path=output_path, expected_format='fits')
        preview_path = run_directory / 'previews' / 'out.jpg'
        render_output_preview(checked, preview_path, max_edge=4)
        with Image.open(preview_path) as preview:
            assert max(preview.size) <= 4
        assert output_path.read_bytes() == original
        task_id = uuid4()
        result = register_output(client.app.state.database, settings, task_id=task_id, output=checked, name=None)
        assert result.created is True
        assert result.task_status == 'queued'
        run_import_task(client.app.state.database, settings, str(task_id))
        completed = get_output_registration(client.app.state.database, settings, task_id)
        assert completed.created is False
        assert completed.task_status == 'completed'
        assert completed.asset_id is not None and completed.asset_id is not None
        assert completed.content_status == 'available'
        repeated = register_output(client.app.state.database, settings, task_id=task_id, output=checked, name=None)
        assert repeated.created is False
        assert repeated.asset_id == completed.asset_id
    finally:
        client.__exit__(None, None, None)

@pytest.mark.parametrize('category', ['image', 'xisf'])
def test_high_depth_output_preview_keeps_requested_size_above_thumbnail(tmp_path, category):
    from xisf import XISF
    run_directory = tmp_path / 'runs' / 'preview-size'
    run_directory.mkdir(parents=True)
    settings = Settings('127.0.0.1', 8190, tmp_path / 'data', (), workspace=tmp_path)
    values = np.arange(240 * 320, dtype=np.uint16).reshape(240, 320)
    source = run_directory / ('out.xisf' if category == 'xisf' else 'out.tif')
    if category == 'xisf':
        XISF.write(str(source), values[..., None])
    else:
        Image.fromarray(values).save(source)
    original = source.read_bytes()
    checked = check_output(settings, run_directory=run_directory, path=source, expected_format=category)
    destination = run_directory / 'preview.jpg'
    render_output_preview(checked, destination, max_edge=320)
    with Image.open(destination) as preview:
        assert preview.size == (320, 240)
    assert source.read_bytes() == original

def test_output_preview_reports_missing_dependency_and_decode_failure(tmp_path, monkeypatch):
    run_directory = tmp_path / 'runs' / 'preview-errors'
    run_directory.mkdir(parents=True)
    settings = Settings('127.0.0.1', 8190, tmp_path / 'data', (), workspace=tmp_path)
    video = run_directory / 'video.mp4'
    video.write_bytes(b'video bytes')
    checked_video = check_output(settings, run_directory=run_directory, path=video, expected_format='video')
    monkeypatch.setattr(science_input_service.shutil, 'which', lambda _name: None)
    with pytest.raises(ApiError) as dependency:
        render_output_preview(checked_video, run_directory / 'video.jpg', max_edge=100)
    assert dependency.value.code == 'PREVIEW_DEPENDENCY_UNAVAILABLE'
    image_file = run_directory / 'broken.png'
    image_file.write_bytes(b'not an image')
    checked_image = check_output(settings, run_directory=run_directory, path=image_file, expected_format='image')
    with pytest.raises(ApiError) as failure:
        render_output_preview(checked_image, run_directory / 'broken.jpg', max_edge=100)
    assert failure.value.code == 'PREVIEW_FAILED'
    assert image_file.read_bytes() == b'not an image'
