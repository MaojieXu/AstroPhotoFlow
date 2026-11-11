"""Chat image management over real FastMCP stdio and an isolated HTTP service."""
from __future__ import annotations
import asyncio
import json
import os
import socket
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Event, Thread
from uuid import uuid4
import httpx
import numpy as np
import pytest
import uvicorn
from astropy.io import fits
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from astrophotoflow.core.config import load_settings
from astrophotoflow.core.database.schema import database_lock, initialize_database
from astrophotoflow.interfaces.http.app import create_app
ROOT = Path(__file__).resolve().parents[2]

@pytest.fixture
def image_service(tmp_path):
    """Keep HTTP in this process so failures can be injected at real IO boundaries."""
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    sources = tmp_path / 'sources'
    sources.mkdir()
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen()
    port = listener.getsockname()[1]
    data_dir = workspace / 'data'
    config_path = workspace / 'config.toml'
    config_path.write_text(f'[server]\nhost = "127.0.0.1"\nport = {port}\n\n[storage]\ndata_dir = "{data_dir.as_posix()}"\n\n[comfyui]\nallowed_origins = ["http://127.0.0.1:8188"]\n\n[[imports.roots]]\nid = "science"\npath = "{sources.as_posix()}"\n', encoding='utf-8')
    settings = load_settings(config_path)
    with database_lock(settings):
        initialize_database(settings)
    settings.token_path.write_text('image-integration-token', encoding='utf-8')
    app = create_app(settings, 'image-integration-token')
    server = uvicorn.Server(uvicorn.Config(app, log_level='error', access_log=False))
    thread = Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    env = {**os.environ, 'ASTROPHOTOFLOW_CONFIG': str(config_path), 'PYTHONUTF8': '1'}
    env['NO_PROXY'] = '127.0.0.1,localhost'
    try:
        deadline = time.monotonic() + 30
        with httpx.Client(base_url=f'http://127.0.0.1:{port}/api/v1', headers={'Authorization': 'Bearer image-integration-token'}, trust_env=False) as client:
            while time.monotonic() < deadline and thread.is_alive():
                try:
                    if client.get('/health', timeout=1).status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                time.sleep(0.05)
            else:
                pytest.fail('Isolated image HTTP service did not become healthy')
            yield {'app': app, 'settings': settings, 'sources': sources, 'env': env, 'http': client, 'log': workspace / 'mcp.log'}
    finally:
        server.should_exit = True
        thread.join(timeout=20)
        listener.close()
        assert not thread.is_alive(), 'Isolated image HTTP service did not stop'

def write_fits(path: Path, *, frame='Light Frame', target='M31', exposure=300, observed='2026-11-01T23:00:00', gain=0, temperature=-10, seed=1, shape=(16, 16)):
    """Only authored, small FITS files are used; zeros and absent fields stay distinct."""
    hdu = fits.PrimaryHDU(np.arange(np.prod(shape), dtype=np.float32).reshape(shape) + seed)
    for key, value in {'IMAGETYP': frame, 'OBJECT': target, 'EXPTIME': exposure, 'DATE-OBS': observed, 'GAIN': gain, 'OFFSET': 0, 'CCD-TEMP': temperature, 'XBINNING': 1, 'YBINNING': 1, 'FILTER': 'L'}.items():
        if value is not None:
            hdu.header[key] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    hdu.writeto(path)
    return path

def result_text(result):
    return '\n'.join((block.text for block in result.content if hasattr(block, 'text')))

def tool_data(result):
    assert not result.is_error, result_text(result)
    assert result.structured_content is not None, result_text(result)
    value = result.structured_content
    return value['result'] if isinstance(value, dict) and set(value) == {'result'} else value

@asynccontextmanager
async def image_session(service):
    suffix = '.exe' if os.name == 'nt' else ''
    params = StdioServerParameters(command=str(Path(sys.executable).with_name('apf' + suffix)), args=['mcp'], env=service['env'], cwd=str(ROOT))
    with service['log'].open('w', encoding='utf-8') as log:
        async with stdio_client(params, errlog=log) as streams, ClientSession(*streams) as session:
            await session.initialize()
            assert {tool.name for tool in (await session.list_tools()).tools} == {'search_tools', 'call_tool'}
            yield session

async def call(session, tool_name, **arguments):
    return tool_data(await session.call_tool(tool_name, arguments, read_timeout_seconds=30))

async def inspected(session, paths):
    scan = await call(session, 'data_imports_inspect', paths=[str(path) for path in paths])
    assert 'groups' not in scan
    page = await call(session, 'data_imports_entries', scan_id=scan['scan_id'], query={'limit': 200})
    assert page['total'] == len(paths)
    assert all(('suggested' not in row for row in page['items']))
    return (scan['scan_id'], [{'file_id': row['file_id']} for row in page['items']])

async def wait_import(session, request_id):
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        receipt = await call(session, 'data_tasks_status', request_id=request_id)
        if receipt['state'] != 'running':
            return receipt
        await asyncio.sleep(0.05)
    pytest.fail(f'Import {request_id} did not settle')

async def import_asset(session, path, **options):
    scan_id, files = await inspected(session, [path])
    request_id = str(uuid4())
    await call(session, 'data_imports_import_asset', request_id=request_id, scan_id=scan_id, file=files[0], **options)
    receipt = await wait_import(session, request_id)
    assert receipt['state'] == 'completed', receipt
    task = await call(session, 'data_tasks_get', task_id=receipt['task_id'])
    assert len(task['items']) == 1
    item = task['items'][0]
    detail = await call(session, 'data_assets_get', asset_id=item['asset_id'])
    return (detail['asset'], item, receipt)

def test_thumbnail_batch_via_real_mcp_and_http(image_service):

    async def exercise():
        async with image_session(image_service) as session:
            root = image_service['sources']
            first = write_fits(root / 'thumb-a.fits', seed=11)
            second = write_fits(root / 'thumb-b.fits', seed=21)
            scan, files = await inspected(session, [first, second])
            import_id = str(uuid4())
            await call(session, 'data_imports_import_dataset', request_id=import_id, scan_id=scan, name='Thumbnail group', files=files)
            receipt = await wait_import(session, import_id)
            assert receipt['state'] == 'completed', receipt
            publication = receipt['stages']['publication']
            dataset_id = publication['dataset_id']
            request_id = str(uuid4())
            target = {'kind': 'dataset', 'dataset_id': dataset_id}
            accepted = await call(session, 'data_media_thumbnails_generate', request_id=request_id, target=target)
            assert accepted['total'] == 2
            repeated = await call(session, 'data_media_thumbnails_generate', request_id=request_id, target=target)
            assert repeated['request_id'] == request_id
            deadline = time.monotonic() + 30
            while True:
                status = await call(session, 'data_media_thumbnails_status', request_id=request_id)
                if status['state'] != 'running':
                    break
                assert time.monotonic() < deadline, status
                await asyncio.sleep(0.1)
            assert status['state'] == 'completed' and status['available'] == 2, status
            member_id = status['items'][1]['asset_id']
            result = image_service['http'].get(f'/datasets/{dataset_id}/members/{member_id}/thumbnail')
            assert result.status_code == 200 and result.headers['content-type'] == 'image/jpeg'
            from io import BytesIO
            from PIL import Image
            with Image.open(BytesIO(result.content)) as image:
                assert max(image.size) <= 100
    asyncio.run(exercise())

def target(item):
    return {'mode': 'target', 'target': {'kind': 'asset', 'id': item['asset_id']}}

def fixed_members(page):
    return [{key: row['member'][key] for key in ('id', 'dataset_id', 'asset_id', 'position', 'relative_path')} for row in page['items']]

def test_cross_night_m31_keeps_group_calibration_and_updates_current_members(image_service):
    """Two compatible nights share the group flat and current ordered membership."""

    async def exercise():
        async with image_session(image_service) as session:
            camera = await call(session, 'data_equipment_register_camera', name='Synthetic M31 camera')
            equipment = {'choice': {'source': 'devices', 'camera': {'equipment_id': camera['id'], 'expected_revision': camera['revision']}}, 'fields': ['camera']}
            defaults = {'equipment': equipment}
            root = image_service['sources']
            flat_a = write_fits(root / 'flat-a.fits', frame='Master Flat', target='', exposure=1, seed=10)
            flat_b = write_fits(root / 'flat-b.fits', frame='Master Flat', target='', exposure=1, seed=20)
            _, a, _ = await import_asset(session, flat_a, defaults=defaults)
            _, b, _ = await import_asset(session, flat_b, defaults=defaults)
            night_one = write_fits(root / 'm31-night-one.fits', seed=30)
            scan_id, files = await inspected(session, [night_one])
            before_count = (await call(session, 'data_assets_search'))['total']
            preflight = await call(session, 'data_calibration_check_import', scan_id=scan_id, files=files, defaults=defaults, calibration={'flat': target(a)})
            assert preflight['checked_files'] == 1
            assert preflight['conflict_count'] == 0 and preflight['unknown_count'] > 0
            assert (await call(session, 'data_assets_search'))['total'] == before_count
            first_id = str(uuid4())
            await call(session, 'data_imports_import_dataset', request_id=first_id, scan_id=scan_id, name='M31 across nights', files=files, defaults=defaults, calibration={'flat': target(a)}, accept_unknown=True)
            first = await wait_import(session, first_id)
            assert first['state'] == 'completed', first
            dataset_id = first['stages']['publication']['dataset_id']
            old_members = await call(session, 'data_datasets_members', dataset_id=dataset_id)
            old_calibration = await call(session, 'data_calibration_get_dataset', dataset_id=dataset_id)
            first_member = old_members['items'][0]['member']['asset_id']
            assert old_calibration['calibration']['flat'] == target(a)
            first_asset = (await call(session, 'data_assets_get', asset_id=first['items'][0]['asset_id']))['asset']
            assert first_asset['parameters']['gain'] == 0
            assert first_asset['parameters']['exposure_seconds'] == 300
            for invalid_target in ({'kind': 'dataset', 'id': dataset_id}, {'kind': 'asset', 'id': first_member}):
                refused = await session.call_tool('data_calibration_update_image', {'request_id': str(uuid4()), 'asset_id': first_asset['id'], 'expected_revision': first_asset['revision'], 'changes': {'flat': {'mode': 'target', 'target': invalid_target}}, 'accept_unknown': True})
                assert refused.is_error, result_text(refused)
            unknown = await session.call_tool('data_calibration_update_image', {'request_id': str(uuid4()), 'asset_id': first_asset['id'], 'expected_revision': first_asset['revision'], 'changes': {'flat': target(b)}})
            assert unknown.is_error and 'UNKNOWN' in result_text(unknown).upper()
            await call(session, 'data_calibration_update_image', request_id=str(uuid4()), asset_id=first_asset['id'], expected_revision=first_asset['revision'], changes={'flat': target(b)}, accept_unknown=True)
            unchanged_group = await call(session, 'data_calibration_get_dataset', dataset_id=dataset_id)
            for key in ('dataset_id', 'revision', 'calibration', 'slots'):
                assert unchanged_group[key] == old_calibration[key]
            group = (await call(session, 'data_datasets_get', dataset_id=dataset_id))['dataset']
            night_two = write_fits(root / 'm31-night-two.fits', exposure=180, observed='2026-11-02T23:00:00', seed=40)
            scan_id, files = await inspected(session, [night_two])
            append_id = str(uuid4())
            await call(session, 'data_imports_append_dataset', request_id=append_id, scan_id=scan_id, dataset_id=dataset_id, expected_revision=group['revision'], files=files, defaults=defaults, accept_unknown=True)
            appended = await wait_import(session, append_id)
            assert appended['state'] == 'completed', appended
            assert appended['stages']['publication']['dataset_id'] == dataset_id
            members = await call(session, 'data_datasets_members', dataset_id=dataset_id)
            assert members['total'] == 2
            resolved = await call(session, 'data_calibration_get_dataset', dataset_id=dataset_id)
            assert resolved['calibration']['flat'] == target(a)
            assert resolved['slots']['flat']['target_detail']['name']
            assert resolved['slots']['flat']['source'] == 'dataset'
            assert resolved['slots']['flat']['check_state'] == 'not_checked'
            assert members['items'][0]['member']['asset_id'] == first_member
            assert resolved['calibration'] == old_calibration['calibration']
            assert (await call(session, 'data_datasets_search', query={'target_name': 'M31'}))['total'] == 1
            current_group = (await call(session, 'data_datasets_get', dataset_id=dataset_id))['dataset']
            assert current_group['exposure_summary']['total_seconds'] == 480
            assert current_group['exposure_summary']['known_count'] == 2
            library = await call(session, 'data_library_search', query={'limit': 200})
            group_row = next((row for row in library['items'] if row['id'] == dataset_id))
            assert group_row['exposure_summary']['total_seconds'] == 480
            assert group_row['calibration_projection']['slots']['flat']['status'] == 'target'
            first_now = (await call(session, 'data_assets_get', asset_id=first_asset['id']))['asset']
            await call(session, 'data_assets_update', asset_id=first_asset['id'], expected_revision=first_now['revision'], changes={'parameters': {'exposure_seconds': 600}})
            updated_group = (await call(session, 'data_datasets_get', dataset_id=dataset_id))['dataset']
            assert updated_group['exposure_summary']['total_seconds'] == 780
            assert updated_group['id'] == dataset_id
            assert night_one.is_file() and night_two.is_file() and flat_a.is_file() and flat_b.is_file()
    asyncio.run(exercise())

def test_explicit_import_request_replay_and_unknown_classification(image_service):

    async def exercise():
        async with image_session(image_service) as session:
            path = write_fits(image_service['sources'] / 'unknown.fits', frame=None, exposure=None, target=None, observed=None, gain=None, temperature=None)
            scan_id, files = await inspected(session, [path])
            write_fits(image_service['sources'] / 'not-in-confirmed-list.fits', seed=99)
            request_id = str(uuid4())
            arguments = {'request_id': request_id, 'scan_id': scan_id, 'file': files[0]}
            accepted = await call(session, 'data_imports_import_asset', **arguments)
            replayed = await call(session, 'data_imports_import_asset', **arguments)
            assert replayed['task_id'] == accepted['task_id']
            settled = await wait_import(session, request_id)
            assert settled['state'] == 'completed', settled
            task = await call(session, 'data_tasks_get', task_id=accepted['task_id'])
            assert len(task['items']) == 1 and task['items'][0]['asset_id']
            asset = (await call(session, 'data_assets_get', asset_id=task['items'][0]['asset_id']))['asset']
            assert asset['classification']['frame_type'] is None
            assert asset['parameters']['gain'] is None
            conflict = await session.call_tool('data_imports_import_asset', {**arguments, 'file': {**files[0], 'notes': 'different submitted content'}})
            assert conflict.is_error and 'CONFLICT' in result_text(conflict)
            assert (await call(session, 'data_assets_search'))['total'] == 1
    asyncio.run(exercise())

def test_known_calibration_conflict_is_rejected_even_when_unknowns_accepted(image_service):

    async def exercise():
        async with image_session(image_service) as session:
            root = image_service['sources']
            camera = await call(session, 'data_equipment_register_camera', name='Conflict test camera')
            defaults = {'metadata': {'parameters': {'parameter_mode': 'gain'}}, 'equipment': {'choice': {'source': 'devices', 'camera': {'equipment_id': camera['id'], 'expected_revision': camera['revision']}}, 'fields': ['camera']}}
            light, item, _ = await import_asset(session, write_fits(root / 'light.fits'), defaults=defaults)
            _, bad_dark, _ = await import_asset(session, write_fits(root / 'wrong-size.fits', frame='Master Dark', shape=(16, 32)), defaults=defaults)
            before = await call(session, 'data_calibration_get_image', asset_id=light['id'])
            request_id = str(uuid4())
            result = await session.call_tool('data_calibration_update_image', {'request_id': request_id, 'asset_id': light['id'], 'expected_revision': light['revision'], 'changes': {'dark': target(bad_dark)}, 'accept_unknown': True})
            assert result.is_error, result_text(result)
            assert 'CALIBRATION_CONFLICT' in result_text(result)
            assert await call(session, 'data_calibration_get_image', asset_id=light['id']) == before
            assert (await call(session, 'data_assets_get', asset_id=light['id']))['asset']['revision'] == light['revision']
    asyncio.run(exercise())

def test_original_copy_failure_retry_preserves_registered_identity(image_service, monkeypatch):
    from astrophotoflow.modules.data.imports import stages
    original_copy = stages.read_hash_and_copy
    failed = False

    def fail_once(source, *args, **kwargs):
        nonlocal failed
        if Path(source).name == 'copy-failure.fits' and (not failed):
            failed = True
            raise OSError('Authored integration failure before original copy')
        return original_copy(source, *args, **kwargs)
    monkeypatch.setattr(stages, 'read_hash_and_copy', fail_once)

    async def exercise():
        async with image_session(image_service) as session:
            path = write_fits(image_service['sources'] / 'copy-failure.fits')
            original_bytes = path.read_bytes()
            scan_id, files = await inspected(session, [path])
            request_id = str(uuid4())
            accepted = await call(session, 'data_imports_import_dataset', request_id=request_id, scan_id=scan_id, name='Recover original', files=files)
            settled = await wait_import(session, request_id)
            assert settled['state'] == 'needs_attention', settled
            task = await call(session, 'data_tasks_get', task_id=accepted['task_id'])
            item = task['items'][0]
            assert failed and item['asset_id'] and item['asset_id']
            assert item['originals'] == 'failed'
            assert (await call(session, 'data_datasets_search', query={'text': 'Recover original'}))['total'] == 0
            retried = await call(session, 'data_tasks_retry', task_id=accepted['task_id'], item_ids=[item['task_item_id']])
            deadline = time.monotonic() + 40
            while time.monotonic() < deadline:
                retry_task = await call(session, 'data_tasks_get', task_id=retried['task_id'])
                if retry_task['status'] not in {'queued', 'running', 'cancelling'}:
                    break
                await asyncio.sleep(0.05)
            assert retry_task['items'][0]['asset_id'] == item['asset_id']
            assert retry_task['items'][0]['asset_id'] == item['asset_id']
            assert retry_task['items'][0]['originals'] == 'available'
            recovered = await wait_import(session, request_id)
            assert recovered['state'] == 'completed', recovered
            assert recovered['items_total'] == 1
            assert recovered['items'][0]['asset_id'] == item['asset_id']
            dataset_id = recovered['stages']['publication']['dataset_id']
            members = await call(session, 'data_datasets_members', dataset_id=dataset_id)
            assert members['total'] == 1
            assert path.read_bytes() == original_bytes
            assert (await call(session, 'data_assets_search'))['total'] == 1
    asyncio.run(exercise())

def test_append_publication_conflict_can_recover_without_reimport(image_service, monkeypatch):
    from astrophotoflow.modules.data.imports import stages
    original_copy = stages.read_hash_and_copy
    copying, release = (Event(), Event())

    def hold_append(source, *args, **kwargs):
        if Path(source).name == 'append-race.fits':
            copying.set()
            assert release.wait(20), 'Append publication test did not release original copy'
        return original_copy(source, *args, **kwargs)
    monkeypatch.setattr(stages, 'read_hash_and_copy', hold_append)

    async def exercise():
        async with image_session(image_service) as session:
            root = image_service['sources']
            scan_id, files = await inspected(session, [write_fits(root / 'first.fits')])
            request_id = str(uuid4())
            await call(session, 'data_imports_import_dataset', request_id=request_id, scan_id=scan_id, name='M31 publication recovery', files=files)
            first = await wait_import(session, request_id)
            assert first['state'] == 'completed', first
            dataset_id = first['stages']['publication']['dataset_id']
            dataset = (await call(session, 'data_datasets_get', dataset_id=dataset_id))['dataset']
            scan_id, files = await inspected(session, [write_fits(root / 'append-race.fits', seed=2)])
            append_id = str(uuid4())
            accepted = await call(session, 'data_imports_append_dataset', request_id=append_id, scan_id=scan_id, dataset_id=dataset_id, expected_revision=dataset['revision'], files=files)
            assert await asyncio.to_thread(copying.wait, 10), 'Append never reached original copy'
            try:
                changed = (await call(session, 'data_datasets_update', dataset_id=dataset_id, expected_revision=dataset['revision'], changes={'notes': 'Concurrent user edit'}))['dataset']
            finally:
                release.set()
            failed = await wait_import(session, append_id)
            assert failed['state'] == 'needs_attention', failed
            assert (await call(session, 'data_datasets_get', dataset_id=dataset_id))['dataset']['id'] == dataset_id
            assert (await call(session, 'data_assets_search'))['total'] == 2
            await call(session, 'data_imports_retry_publication', request_id=append_id, task_id=accepted['task_id'], expected_revision=changed['revision'])
            recovered = await wait_import(session, append_id)
            assert recovered['state'] == 'completed', recovered
            members = await call(session, 'data_datasets_members', dataset_id=dataset_id)
            assert members['total'] == 2
            assert (await call(session, 'data_assets_search'))['total'] == 2
            assert (await call(session, 'data_datasets_members', dataset_id=dataset_id))['total'] == 2
    try:
        asyncio.run(exercise())
    finally:
        release.set()

def test_mount_management_and_channel_guidance_over_real_mcp(image_service):
    """Manage a mount through stdio/HTTP and freeze it without changing capture facts."""

    async def exercise():
        async with image_session(image_service) as session:
            discovery = await session.call_tool('search_tools', {'query': 'register_filter channel'})
            definitions = json.loads(discovery.content[0].text)
            filter_tool = next((tool for tool in definitions if tool['name'] == 'data_equipment_register_filter'))
            assert 'Few-shot' in filter_tool['description']
            assert 'Ir875nm' in json.dumps(filter_tool['inputSchema'])
            no_presets = await session.call_tool('search_tools', {'query': 'data_presets_create'})
            assert all((not tool['name'].startswith('data_presets_') for tool in json.loads(no_presets.content[0].text)))
            mount = await call(session, 'data_equipment_register_mount', name='Synthetic AP1100')
            assert mount['kind'] == 'mount' and 'specs' not in mount
            camera = await call(session, 'data_equipment_register_camera', name='Synthetic mount camera')
            rig = await call(session, 'data_setups_create', name='Synthetic mount rig', members=[{'source': 'registered', 'equipment_id': camera['id']}, {'source': 'registered', 'equipment_id': mount['id']}])
            path = write_fits(image_service['sources'] / 'mount-frame.fits')
            asset, item, _ = await import_asset(session, path, defaults={'equipment': {'choice': {'source': 'setup', 'setup_id': rig['id'], 'expected_revision': rig['revision']}, 'fields': ['camera', 'mount']}})
            detail = await call(session, 'data_assets_get', asset_id=asset['id'])
            frozen = detail['equipment_context']['selected_equipment']['mount_id']
            assert frozen['id'] == mount['id'] and frozen['name'] == mount['name']
            assert detail['asset']['parameters']['gain'] == 0
            assert detail['asset']['parameters']['sensor_temperature_c'] == -10
            assert item['previews'] == 'not_requested'
            scheduled = await call(session, 'data_media_schedule', asset_id=asset['id'])
            deadline = time.monotonic() + 20
            while scheduled['status'] == 'generating' and time.monotonic() < deadline:
                await asyncio.sleep(0.05)
                scheduled = await call(session, 'data_media_status', asset_id=asset['id'])
            assert scheduled['status'] == 'available', scheduled
            rendered = await session.call_tool('data_media_read', {'asset_id': asset['id']})
            assert any((block.type == 'image' for block in rendered.content))
            changed = await call(session, 'data_equipment_update_mount', equipment_id=mount['id'], expected_revision=mount['revision'], changes={'name': 'Renamed mount'})
            old = await call(session, 'data_assets_get', asset_id=asset['id'])
            assert old['equipment_context']['selected_equipment']['mount_id']['name'] == mount['name']
            await call(session, 'data_assets_apply_equipment', assets=[{'asset_id': asset['id'], 'expected_revision': old['asset']['revision']}], equipment={'choice': {'source': 'devices', 'mount': None}, 'fields': ['mount']})
            cleared = await call(session, 'data_assets_get', asset_id=asset['id'])
            assert cleared['equipment_context']['selected_equipment']['mount_id'] is None
            for key in ('gain', 'offset', 'exposure_seconds', 'sensor_temperature_c'):
                assert cleared['asset']['parameters'][key] == old['asset']['parameters'][key]
            assert cleared['asset']['id'] == item['asset_id']
            found = await call(session, 'data_equipment_search', query={'equipment_type': 'mount'})
            assert found['total'] == 1 and found['items'][0]['id'] == changed['id']
            for label in ('H', 'O', 'S', 'RGB', 'SHO', 'Ir875nm'):
                filt = await call(session, 'data_equipment_register_filter', name='Synthetic ' + label, specs={'channel': label})
                assert filt['specs']['channel'] == label
                assert filt['specs']['central_wavelength_nm'] is None
                assert filt['specs']['bandwidth_nm'] is None
    asyncio.run(exercise())
