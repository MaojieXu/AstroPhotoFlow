from __future__ import annotations
import asyncio
import json
import os
import re
from pathlib import Path
import socket
import subprocess
import sys
import time
from uuid import uuid4
import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from astrophotoflow.contracts.common import ErrorEnvelope
from PIL import Image
import pytest
ROOT = Path(__file__).resolve().parents[2]
FINAL_TASK_STATUSES = {'completed', 'completed_with_errors', 'failed', 'cancelled', 'interrupted'}

def _entrypoint(name: str) -> str:
    suffix = '.exe' if os.name == 'nt' else ''
    return str(Path(sys.executable).with_name(name + suffix))

def _write_png(path: Path) -> None:
    Image.new('RGB', (16, 16), color=(32, 64, 96)).save(path, format='PNG')

def _service_logs(service: dict) -> str:
    return service['log_path'].read_text(encoding='utf-8', errors='replace')

@pytest.fixture(scope='module')
def service(tmp_path_factory):
    workspace = tmp_path_factory.mktemp('apf-integration')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    data_dir = workspace / 'data'
    sources = workspace / 'sources'
    sources.mkdir()
    config_path = workspace / 'config.toml'
    config_path.write_text(f'[server]\nhost = "127.0.0.1"\nport = {port}\n\n[storage]\ndata_dir = "{data_dir.as_posix()}"\n\n[comfyui]\nallowed_origins = ["http://127.0.0.1:8188"]\n\n[[imports.roots]]\nid = "science"\npath = "{sources.as_posix()}"\n', encoding='utf-8')
    env = os.environ.copy()
    env['ASTROPHOTOFLOW_CONFIG'] = str(config_path)
    env['PYTHONUTF8'] = '1'
    log_path = workspace / 'service.log'
    with log_path.open('w', encoding='utf-8') as log:
        process = subprocess.Popen([_entrypoint('apf-service'), 'serve'], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    service = {'sources': sources, 'config_path': config_path, 'data_dir': data_dir, 'env': env, 'log_path': log_path, 'port': port, 'process': process}
    try:
        deadline = time.monotonic() + 30
        token_path = data_dir / 'service.token'
        while time.monotonic() < deadline and process.poll() is None:
            if token_path.is_file():
                token = token_path.read_text(encoding='utf-8').strip()
                try:
                    response = httpx.get(f'http://127.0.0.1:{port}/api/v1/health', headers={'Authorization': f'Bearer {token}'}, timeout=1, trust_env=False)
                except httpx.ConnectError:
                    time.sleep(0.1)
                    continue
                if response.status_code == 200:
                    service['token'] = token
                    break
            time.sleep(0.1)
        else:
            pytest.fail(f'apf-service did not become healthy.\nService log:\n{_service_logs(service)}')
        yield service
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

def _cli_json(service: dict, tool: str, **arguments) -> dict:
    args = ['call-tool', tool]
    for name, value in arguments.items():
        flag = '--' + name.replace('_', '-')
        if name in {'members', 'files', 'add', 'items', 'assets'}:
            args.extend([flag, json.dumps(value)])
        elif isinstance(value, bool):
            args.append(flag if value else '--no-' + name.replace('_', '-'))
        elif isinstance(value, list):
            for item in value:
                args.extend([flag, json.dumps(item) if isinstance(item, (dict, list)) else str(item)])
        else:
            args.extend([flag, json.dumps(value) if isinstance(value, dict) or value is None else str(value)])
    result = subprocess.run([_entrypoint('apf'), *args], cwd=ROOT, env=service['env'], capture_output=True, text=True, encoding='utf-8', check=False, timeout=30)
    assert result.returncode == 0, f'CLI {tool} failed: {result.stdout} {result.stderr}'
    value = json.loads(result.stdout)
    return value['result'] if isinstance(value, dict) and set(value) == {'result'} else value

def _wait_cli_task(service: dict, task_id: str) -> dict:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        task = _cli_json(service, 'data_tasks_get', task_id=task_id)
        if task['status'] in FINAL_TASK_STATUSES:
            assert task['status'] == 'completed', f'Import task failed: {task}\nService log:\n{_service_logs(service)}'
            return task
        time.sleep(0.2)
    pytest.fail(f'Import task {task_id} did not finish within 30 seconds.\nService log:\n{_service_logs(service)}')

def test_apf_cli_imports_and_queries_parameters(service, tmp_path):
    help_result = subprocess.run([_entrypoint('apf'), '--help'], cwd=ROOT, env=service['env'], capture_output=True, text=True, encoding='utf-8', check=False)
    assert help_result.returncode == 0
    assert 'call-tool' in help_result.stdout
    photo = tmp_path / 'cli-synthetic.png'
    _write_png(photo)
    accepted = _cli_json(service, 'data_imports_upload_one', path=str(photo))
    task = _wait_cli_task(service, accepted['task_id'])
    assert task['items'][0]['asset_id']
    listed = _cli_json(service, 'data_assets_search', query={'limit': 200})
    asset_id = str(task['items'][0]['asset_id'])
    assert asset_id in {str(item['asset']['id']) for item in listed['items']}
    asset = _cli_json(service, 'data_assets_get', asset_id=asset_id)['asset']
    assert asset['parameters']['exposure_seconds'] is None
    updated = _cli_json(service, 'data_assets_update', asset_id=asset_id, expected_revision=asset['revision'], changes={'parameters': {'exposure_seconds': 0}})['asset']
    assert updated['parameters']['exposure_seconds'] == 0
    assert _cli_json(service, 'data_assets_get', asset_id=asset_id)['asset']['parameters']['exposure_seconds'] == 0

def _result_text(result) -> str:
    return '\n'.join((block.text for block in result.content if hasattr(block, 'text')))

def _tool_data(result, service: dict) -> dict:
    assert not result.is_error, f'MCP tool failed: {_result_text(result)}\nService log:\n{_service_logs(service)}'
    assert result.structured_content is not None, f'MCP tool omitted structured output: {_result_text(result)}'
    value = result.structured_content
    return value['result'] if isinstance(value, dict) and set(value) == {'result'} else value

async def _call_operation(session, name, arguments, **kwargs):
    return await session.call_tool(name, arguments, **kwargs)

async def _wait_mcp_task(session: ClientSession, service: dict, task_id: str) -> dict:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            result = await _call_operation(session, 'data_tasks_get', {'task_id': task_id}, read_timeout_seconds=5)
        except TimeoutError as exc:
            pytest.fail(f'Reading import task {task_id} timed out: {exc}\nService log:\n{_service_logs(service)}')
        task = _tool_data(result, service)
        if task['status'] in FINAL_TASK_STATUSES:
            assert task['status'] == 'completed', f'Import task failed: {task}\nService log:\n{_service_logs(service)}'
            return task
        await asyncio.sleep(0.2)
    pytest.fail(f'Import task {task_id} did not finish within 30 seconds.\nService log:\n{_service_logs(service)}')

def test_apf_mcp_stdio_tools_and_parameter_patch_protocol(service, tmp_path):

    async def exercise_protocol():
        params = StdioServerParameters(command=_entrypoint('apf'), args=['mcp'], env=service['env'], cwd=str(ROOT))
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                listed_tools = await session.list_tools()
                assert {tool.name for tool in listed_tools.tools} == {'search_tools', 'call_tool'}
                assert all(('$defs' not in tool.input_schema for tool in listed_tools.tools))
                definition = json.loads(_result_text(await session.call_tool('search_tools', {'query': 'graph_canvas_edit'})))
                assert 'control_token' not in json.dumps(definition)
                assert 'delete_node' in json.dumps(definition)
                photo = tmp_path / 'mcp-synthetic.png'
                _write_png(photo)
                accepted = _tool_data(await _call_operation(session, 'data_imports_upload_one', {'path': str(photo)}, read_timeout_seconds=10), service)
                task = await _wait_mcp_task(session, service, accepted['task_id'])
                asset_id = str(task['items'][0]['asset_id'])
                assets = _tool_data(await _call_operation(session, 'data_assets_search', {'query': {'limit': 200, 'offset': 0}}, read_timeout_seconds=5), service)
                assert asset_id in {str(item['asset']['id']) for item in assets['items']}
                asset = _tool_data(await _call_operation(session, 'data_assets_get', {'asset_id': asset_id}, read_timeout_seconds=5), service)['asset']
                assert asset['revision'] == 1
                prepared = _tool_data(await _call_operation(session, 'data_assets_prepare_canvas_data', {'body': {'entry_type': 'asset', 'id': asset_id}}, read_timeout_seconds=5), service)
                assert prepared['native_type'] == 'APF_DATA_REFERENCE'
                assert prepared['reference']['asset_id'] == asset['id']
                first = _tool_data(await _call_operation(session, 'data_assets_update', {'asset_id': asset_id, 'expected_revision': 1, 'changes': {'parameters': {'gain': 0, 'exposure_seconds': 0}}}, read_timeout_seconds=5), service)['asset']
                assert first['parameters']['gain'] == 0
                assert first['parameters']['exposure_seconds'] == 0
                cleared = _tool_data(await _call_operation(session, 'data_assets_update', {'asset_id': asset_id, 'expected_revision': 2, 'changes': {'parameters': {'gain': None}}}, read_timeout_seconds=5), service)['asset']
                assert cleared['parameters']['gain'] is None
                assert cleared['parameters']['exposure_seconds'] == 0
                stale = await _call_operation(session, 'data_assets_update', {'asset_id': asset_id, 'expected_revision': 2, 'changes': {'parameters': {'exposure_seconds': 12}}}, read_timeout_seconds=5)
                assert stale.is_error
                assert 'REVISION_CONFLICT' in _result_text(stale)
                current = _tool_data(await _call_operation(session, 'data_assets_get', {'asset_id': asset_id}, read_timeout_seconds=5), service)['asset']
                assert current['revision'] == 3
                assert current['parameters']['exposure_seconds'] == 0
    asyncio.run(exercise_protocol())

def test_apf_mcp_business_domains_protocol(service, tmp_path):
    import numpy as np
    from astropy.io import fits

    async def exercise_protocol():
        params = StdioServerParameters(command=_entrypoint('apf'), args=['mcp'], env=service['env'], cwd=str(ROOT))
        async with stdio_client(params) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()

                async def call(tool_name, **arguments):
                    return _tool_data(await _call_operation(session, tool_name, arguments, read_timeout_seconds=10), service)
                equipment = {}
                for kind in ('camera', 'telescope', 'filter'):
                    created = await call('data_equipment_register_' + kind, name='SDK ' + kind)
                    equipment[kind] = created
                    assert (await call('data_equipment_get', equipment_id=created['id']))['kind'] == kind
                assert (await call('data_equipment_search', query={'equipment_type': 'camera', 'limit': 1}))['total'] >= 1
                setup = await call('data_setups_create', name='SDK setup', members=[{'source': 'registered', 'equipment_id': equipment['camera']['id']}, {'source': 'inline', 'equipment': {'kind': 'telescope', 'name': 'Inline only'}}])
                assert (await call('data_equipment_search', query={'text': 'Inline only'}))['total'] == 0
                assert (await call('data_setups_get', setup_id=setup['id']))['components'] == setup['components']
                assert (await call('data_setups_search', query={'text': 'SDK setup'}))['total'] == 1
                paths = [tmp_path / 'night-one.fits', tmp_path / 'night-two.fits']
                for path in paths:
                    fits.writeto(path, np.arange(256, dtype=np.float32).reshape(16, 16))
                scan = await call('data_imports_inspect', paths=[str(path) for path in paths])
                files = (await call('data_imports_entries', scan_id=scan['scan_id']))['items']
                accepted = await call('data_imports_import_dataset', request_id=str(uuid4()), scan_id=scan['scan_id'], name='SDK night batch', files=[{'file_id': row['file_id']} for row in files], defaults={'metadata': {'classification': {'frame_class': 'subframe', 'frame_type': 'light'}, 'parameters': {'parameter_mode': 'gain', 'gain': 0, 'exposure_seconds': 30}}, 'equipment': {'choice': {'source': 'setup', 'setup_id': setup['id'], 'expected_revision': setup['revision']}, 'fields': ['camera']}})
                task = await _wait_mcp_task(session, service, accepted['task_id'])
                assert len(task['items']) == 2 and task['stages']['registration']['registered'] == 2
                assert (await call('data_tasks_get', task_id=task['task_id'], items_limit=1, items_offset=1))['items'][0]['task_item_id'] == task['items'][1]['task_item_id']
                assert (await call('data_tasks_list', limit=1))['items']
                asset_ids = [item['asset_id'] for item in task['items']]
                asset = (await call('data_assets_get', asset_id=asset_ids[0]))['asset']
                assert asset['classification']['frame_type'] == 'light'
                assert asset['parameters']['gain'] == 0
                assert (await call('data_assets_get', asset_id=asset_ids[0]))['asset']['parameters']['gain'] == 0
                asset = (await call('data_assets_update', asset_id=asset_ids[0], expected_revision=asset['revision'], changes={'notes': 'temporary', 'parameters': {'exposure_seconds': 0}}))['asset']
                asset = (await call('data_assets_update', asset_id=asset_ids[0], expected_revision=asset['revision'], changes={'notes': None, 'classification': {'frame_class': 'subframe', 'frame_type': 'light'}}))['asset']
                assert asset['notes'] is None and asset['parameters']['exposure_seconds'] == 0
                assert (await call('data_assets_get', asset_id=asset_ids[0]))['asset']['availability'] == 'available'
                assert (await call('data_library_search', query={'q': 'SDK night batch'}))['items']
                master_path = tmp_path / 'master-dark.fits'
                hdu = fits.PrimaryHDU(np.arange(256, dtype=np.float32).reshape(16, 16))
                hdu.header['IMAGETYP'] = 'Master Dark'
                hdu.writeto(master_path)
                master_scan = await call('data_imports_inspect', paths=[str(master_path)])
                master_file = (await call('data_imports_entries', scan_id=master_scan['scan_id']))['items'][0]
                master_task = await _wait_mcp_task(session, service, (await call('data_imports_import_asset', request_id=str(uuid4()), scan_id=master_scan['scan_id'], file={'file_id': master_file['file_id'], 'metadata': {'parameters': {'parameter_mode': 'gain', 'gain': 0}}}))['task_id'])
                master = (await call('data_assets_get', asset_id=master_task['items'][0]['asset_id']))['asset']
                assert master['classification'] == {'frame_class': 'masterframe', 'frame_type': 'dark'}
                targets = await call('data_calibration_search', slot='dark', query={'limit': 1, 'offset': 0})
                assert targets['items'][0]['target'] == {'kind': 'asset', 'id': master['id']}
                duplicate = await _call_operation(session, 'data_datasets_create', {
                    'request_id': str(uuid4()), 'name': 'SDK duplicate group',
                    'members': [{'asset_id': identity} for identity in asset_ids],
                })
                assert duplicate.is_error
                assert ErrorEnvelope.model_validate_json(_result_text(duplicate)).error.code == 'ASSET_DATASET_OWNERSHIP'
                group = (await call('data_datasets_get', dataset_id=task['stages']['publication']['dataset_id']))['dataset']
                assert (await call('data_datasets_search', query={'text': group['name']}))['total'] == 1
                bound = await call('data_calibration_update_dataset', request_id=str(uuid4()), dataset_id=group['id'], expected_revision=group['revision'], changes={'dark': {'mode': 'target', 'target': targets['items'][0]['target']}}, accept_unknown=True)
                group = (await call('data_datasets_get', dataset_id=group['id']))['dataset']
                bindings = await call('data_calibration_get_dataset', dataset_id=group['id'])
                assert bindings['calibration']['dark']['target']['id'] == master['id']
                assert (await call('data_datasets_get', dataset_id=group['id']))['dataset']['id'] == bound['result']['dataset_id']
                revisions = [(await call('data_assets_get', asset_id=identity))['asset']['revision'] for identity in asset_ids]
                edited = await call('data_assets_update_metadata_batch', items=[{'asset_id': identity, 'expected_revision': revision, 'changes': {'parameters': {'gain': 0}}} for identity, revision in zip(asset_ids, revisions)])
                assert len(edited['items']) == 2 and all((item['asset']['parameters']['gain'] == 0 for item in edited['items']))
                project = await call('data_projects_create', body={'name': 'SDK M31', 'target_name': 'M31'})
                assert (await call('data_projects_list', query={'q': 'SDK M31'}))['total'] == 1
                asset_ref = await call('data_projects_add_asset', project_id=project['id'], body={'base_revision': 1, 'asset_id': asset_ids[0]})
                group_now = (await call('data_datasets_get', dataset_id=group['id']))['dataset']
                dataset_ref = await call('data_projects_add_dataset', project_id=project['id'], body={'base_revision': 2, 'dataset_id': group['id']})
                assert (await call('data_projects_list_assets', project_id=project['id']))['items'][0]['id'] == asset_ref['id']
                assert (await call('data_projects_get_asset', project_id=project['id'], reference_id=asset_ref['id']))['asset_id'] == asset_ids[0]
                assert (await call('data_projects_list_datasets', project_id=project['id']))['total'] == 1
                assert (await call('data_projects_get_dataset', project_id=project['id'], reference_id=dataset_ref['id']))['dataset_id'] == group_now['id']
                await call('data_projects_remove_asset', project_id=project['id'], reference_id=asset_ref['id'], body={'base_revision': 3})
                await call('data_projects_remove_dataset', project_id=project['id'], reference_id=dataset_ref['id'], body={'base_revision': 4})
                assert (await call('data_projects_get', project_id=project['id']))['revision'] == 5
                assert (await call('data_projects_update', project_id=project['id'], body={'base_revision': 5, 'status': 'archived'}))['status'] == 'archived'
                night = service['sources'] / 'sdk-night'
                night.mkdir()
                _write_png(night / 'good.png')
                (night / 'broken.fits').write_bytes(b'invalid FITS')
                assert (await call('data_imports_roots'))['items'][0]['id'] == 'science'
                assert (await call('data_imports_browse', root_id='science', path='sdk-night'))['total'] == 2
                local = await call('data_imports_local', body={'sources': [{'root_id': 'science', 'path': 'sdk-night'}], 'storage_mode': 'managed'})
                for _ in range(100):
                    local_task = await call('data_tasks_get', task_id=local['task_id'])
                    if local_task['status'] in FINAL_TASK_STATUSES:
                        break
                    await asyncio.sleep(0.1)
                assert local_task['status'] == 'completed_with_errors'
                broken = next((item for item in local_task['items'] if item['source_path'].endswith('broken.fits')))
                hdu.writeto(night / 'broken.fits', overwrite=True)
                retry = await call('data_tasks_retry', task_id=local_task['id'], item_ids=[broken['id']])
                repaired = await _wait_mcp_task(session, service, retry['task_id'])
                assert repaired['items'][0]['retry_of_item_id'] == broken['id']
                if broken['asset_id']:
                    assert repaired['items'][0]['asset_id'] == broken['asset_id']
                assert (night / 'good.png').is_file()
                for tool_name in ('data_tasks_cancel', 'data_tasks_resume'):
                    rejected = await _call_operation(session, tool_name, {'task_id': task['task_id']})
                    assert rejected.is_error
                    failure = ErrorEnvelope.model_validate_json(_result_text(rejected))
                    assert failure.error.code == 'TASK_STATE_CONFLICT'
                    assert failure.request_id
                disposable = tmp_path / 'disposable.png'
                _write_png(disposable)
                disposable_task = await _wait_mcp_task(session, service, (await call('data_imports_upload_one', path=str(disposable)))['task_id'])
                disposable_asset = (await call('data_assets_get', asset_id=disposable_task['items'][0]['asset_id']))['asset']
                assert disposable_asset['classification'] == {'frame_class': None, 'frame_type': None}
                remove = {'items': [{'entry_type': 'asset', 'id': disposable_asset['id'], 'revision': disposable_asset['revision']}]}
                await call('data_trash_remove', body=remove)
                trash = await call('data_trash_list')
                entry = next((item for item in trash['items'] if item['id'] == disposable_asset['id']))
                selection = {'items': [{key: entry[key] for key in ('entry_type', 'id', 'removed_at', 'revision', 'source_dataset_id')}]}
                await call('data_trash_restore', body=selection)
                await call('data_trash_remove', body=remove)
                entry = next((item for item in (await call('data_trash_list'))['items'] if item['id'] == disposable_asset['id']))
                selection = {'items': [{key: entry[key] for key in ('entry_type', 'id', 'removed_at', 'revision', 'source_dataset_id')}]}
                preview = await call('data_trash_preview_delete', body=selection)
                assert preview['photo_count'] == 1 and preview['managed_file_count'] >= 1 and (not preview['references'])
                deleted = await call('data_trash_delete', body={**selection, 'preview_fingerprint': preview['preview_fingerprint']})
                assert deleted['deleted_file_count'] == preview['managed_file_count'] and (not deleted['failed'])
                assert disposable.is_file()
                for kind, item in equipment.items():
                    assert (await call('data_equipment_update_' + kind, equipment_id=item['id'], expected_revision=1, changes={'status': 'archived'}))['status'] == 'archived'
                assert (await call('data_setups_update', setup_id=setup['id'], expected_revision=1, changes={'status': 'archived'}))['status'] == 'archived'
                assert (await call('data_datasets_update', dataset_id=group['id'], expected_revision=group_now['revision'], changes={'status': 'archived'}))['dataset']['status'] == 'archived'
    asyncio.run(exercise_protocol())

def test_apf_cli_structured_domain_workflow(service, tmp_path):

    def command(tool, **arguments):
        return _cli_json(service, tool, **arguments)
    camera = command('data_equipment_register_camera', name='CLI Camera')
    candidates = command('data_equipment_search', query={'equipment_type': 'camera', 'text': 'CLI Camera'})
    assert camera['id'] in {item['id'] for item in candidates['items']}
    setup = command('data_setups_create', name='CLI setup', members=[{'source': 'registered', 'equipment_id': camera['id']}])
    paths = [tmp_path / 'cli-bulk-a.png', tmp_path / 'cli-bulk-b.png']
    for path in paths:
        _write_png(path)
    task = _wait_cli_task(service, command('data_imports_upload', paths=list(map(str, paths)), options={'parameters': {'parameter_mode': 'gain', 'gain': 0}, 'dataset_name': 'CLI batch', 'classification': {'frame_class': 'subframe', 'frame_type': 'light'}})['task_id'])
    assert command('data_tasks_get', task_id=task['id'], items_limit=1, items_offset=1)['items'][0]['id'] == task['items'][1]['id']
    assert command('data_assets_get', asset_id=task['items'][0]['asset_id'])['asset']['parameters']['gain'] == 0
    versions = [item['asset_id'] for item in task['items']]
    created = command('data_datasets_create', request_id=str(uuid4()), name='CLI logical group', members=[{'asset_id': identity} for identity in versions])
    group = command('data_datasets_get', dataset_id=created['result']['dataset_id'])['dataset']
    command('data_calibration_update_dataset', request_id=str(uuid4()), dataset_id=group['id'], expected_revision=group['revision'], changes={'dark': {'mode': 'disabled'}})
    bindings = command('data_calibration_get_dataset', dataset_id=group['id'])
    assert bindings['calibration']['dark'] == {'mode': 'disabled'}
    project = command('data_projects_create', body={'name': 'CLI project'})
    reference = command('data_projects_add_dataset', project_id=project['id'], body={'base_revision': project['revision'], 'dataset_id': group['id']})
    assert command('data_projects_list_datasets', project_id=project['id'])['items'][0]['id'] == reference['id']
    command('data_projects_remove_dataset', project_id=project['id'], reference_id=reference['id'], body={'base_revision': 2})
    assert command('data_projects_update', project_id=project['id'], body={'base_revision': 3, 'status': 'archived'})['status'] == 'archived'
    assert command('data_setups_update', setup_id=setup['id'], expected_revision=1, changes={'status': 'archived'})['status'] == 'archived'
    assert command('data_equipment_update_camera', equipment_id=camera['id'], expected_revision=1, changes={'status': 'archived'})['status'] == 'archived'
    rejected = subprocess.run([_entrypoint('apf'), 'call-tool', 'data_assets_update', '--asset-id', task['items'][0]['asset_id'], '--expected-revision', '0', '--changes', '{}'], cwd=ROOT, env=service['env'], capture_output=True, text=True, check=False, encoding='utf-8')
    assert rejected.returncode != 0 and 'expected_revision' in rejected.stdout + rejected.stderr

def test_apf_cli_saves_current_image_calibration_with_revision(service, tmp_path):
    import numpy as np
    from astropy.io import fits
    source = tmp_path / 'first-binding.fits'
    hdu = fits.PrimaryHDU(np.arange(256, dtype=np.float32).reshape(16, 16))
    hdu.header['IMAGETYP'] = 'Light Frame'
    hdu.writeto(source)
    accepted = _cli_json(service, 'data_imports_upload_one', path=str(source))
    item = _wait_cli_task(service, accepted['task_id'])['items'][0]
    image = _cli_json(service, 'data_assets_get', asset_id=item['asset_id'])
    arguments = {'request_id': str(uuid4()), 'asset_id': image['asset']['id'], 'expected_revision': image['asset']['revision'], 'changes': {'dark': {'mode': 'disabled'}}}
    tool = 'data_calibration_update_image'
    operation = _cli_json(service, tool, **arguments)
    assert operation['result']['asset_revision'] == arguments['expected_revision'] + 1
    assert operation['result']['bindings']['dark'] == {'mode': 'disabled'}

def test_chat_equipment_registration_and_configuration_v2(service):
    """Exercise chat-selected tools through real stdio, HTTP and generated CLI."""

    async def exercise():
        params = StdioServerParameters(command=_entrypoint('apf'), args=['mcp'], env=service['env'], cwd=str(ROOT))
        async with stdio_client(params) as streams, ClientSession(*streams) as session:
            await session.initialize()
            assert {tool.name for tool in (await session.list_tools()).tools} == {'search_tools', 'call_tool'}

            async def call(tool_name, **arguments):
                return _tool_data(await session.call_tool(tool_name, arguments), service)
            for query, expected in (('登记 相机 camera', 'data_equipment_register_camera'), ('登记 望远镜 telescope 附件', 'data_equipment_register_telescope'), ('登记 滤镜 Channel 带宽', 'data_equipment_register_filter'), ('删除 设备组合 setup', 'data_equipment_management_preview_delete')):
                discovered = await session.call_tool('search_tools', {'query': query})
                assert not discovered.is_error, _result_text(discovered)
                definitions = json.loads(_result_text(discovered))
                assert expected in {item['name'] for item in definitions}, (query, definitions)
                assert len(definitions) <= 10
            camera = await call('data_equipment_register_camera', name='CHAT camera unknown specs')
            assert camera['kind'] == 'camera' and camera['specs']['pixel_size_um'] is None
            duplicate = await call('data_equipment_register_camera', name=camera['name'])
            assert duplicate['id'] != camera['id']
            found = await call('data_equipment_search', query={'text': camera['name'], 'status': 'all'})
            assert {camera['id'], duplicate['id']} <= {item['id'] for item in found['items']}
            scope = await call('data_equipment_register_telescope', name='CHAT 600mm scope', specs={'native_focal_length_mm': 600, 'optical_accessories': [{'name': 'CHAT 0.8x reducer', 'factor': 0.8}]})
            ha = await call('data_equipment_register_filter', name='CHAT Ha', specs={'channel': 'Ha', 'bandwidth_nm': 7})
            unknown = await call('data_equipment_register_filter', name='CHAT Unknown filter')
            assert unknown['specs']['channel'] is None
            bad = await session.call_tool('data_equipment_register_telescope', {'name': 'CHAT invalid scope', 'specs': {'native_focal_length_mm': -600}})
            assert bad.is_error
            assert (await call('data_equipment_search', query={'text': 'CHAT invalid scope'}))['total'] == 0
            assert (await call('data_equipment_get', equipment_id=camera['id']))['name'] == camera['name']
            setup = await call('data_setups_create', name='CHAT setup', members=[{'source': 'registered', 'equipment_id': camera['id']}, {'source': 'registered', 'equipment_id': scope['id'], 'optical_accessory_id': scope['specs']['optical_accessories'][0]['id']}, {'source': 'registered', 'equipment_id': ha['id']}, {'source': 'registered', 'equipment_id': unknown['id']}])
            telescope = next((member for member in setup['components'] if member.get('equipment_id') == scope['id']))
            assert telescope['effective_focal_length_mm'] == 480
            changed = await call('data_equipment_update_camera', equipment_id=duplicate['id'], expected_revision=duplicate['revision'], changes={'notes': 'updated'})
            stale = await session.call_tool('data_equipment_update_camera', {'equipment_id': duplicate['id'], 'expected_revision': duplicate['revision'], 'changes': {'status': 'archived'}})
            assert stale.is_error and 'REVISION_CONFLICT' in _result_text(stale)
            targets = {'equipment': [{'id': changed['id'], 'revision': changed['revision']}]}
            preview = await call('data_equipment_management_preview_delete', targets=targets)
            removed = await call('data_equipment_management_delete', targets=targets, preview_fingerprint=preview['preview_fingerprint'])
            assert removed['deleted_count'] == 1
            assert (await call('data_equipment_get', equipment_id=ha['id']))['specs']['channel'] == 'Ha'
    asyncio.run(exercise())
    cli_camera = _cli_json(service, 'data_equipment_register_camera', name='CHAT standalone generator probe')
    assert _cli_json(service, 'data_equipment_get', equipment_id=cli_camera['id'])['kind'] == 'camera'

def test_equipment_unknown_after_commit_is_queryable_without_replay(service, monkeypatch):
    """Inject a lost MCP result after the real HTTP service committed a device."""
    from fastmcp import Client
    from astrophotoflow.client import AssetClient
    from astrophotoflow.interfaces.mcp.server import create_server
    monkeypatch.setenv('ASTROPHOTOFLOW_CONFIG', str(service['config_path']))
    create = AssetClient.create_equipment
    committed = []

    def lose_result(client, body):
        result = create(client, body)
        committed.append(str(result.id))
        raise httpx.ReadTimeout('Synthetic result loss after successful service commit')
    monkeypatch.setattr(AssetClient, 'create_equipment', lose_result)

    async def exercise():
        async with Client(create_server()) as client:
            result = await client.call_tool('data_equipment_register_camera', {'name': 'CHAT unknown result probe'}, raise_on_error=False)
            assert result.is_error and 'TRANSPORT_TIMEOUT' in _result_text(result)
            assert len(committed) == 1
            observed = await client.call_tool('data_equipment_search', {'query': {'text': 'CHAT unknown result probe', 'status': 'all'}})
            assert observed.structured_content['total'] == 1
            assert observed.structured_content['items'][0]['id'] == committed[0]
            assert len(committed) == 1
    asyncio.run(exercise())

def test_apf_display_preview_stdio_image_and_cli_export(service, tmp_path):
    from base64 import b64decode
    from io import BytesIO
    photo = tmp_path / 'preview-source.png'
    Image.new('RGB', (1600, 800), color=(32, 64, 96)).save(photo, format='PNG')
    original = photo.read_bytes()
    task = _wait_cli_task(service, _cli_json(service, 'data_imports_upload_one', path=str(photo))['task_id'])
    asset_id = task['items'][0]['asset_id']

    async def exercise_preview():
        params = StdioServerParameters(command=_entrypoint('apf'), args=['mcp'], env=service['env'], cwd=str(ROOT))
        async with stdio_client(params) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                initial = _tool_data(await _call_operation(session, 'data_media_status', {'asset_id': asset_id}), service)
                assert initial['status'] == 'not_ready' and initial['error']['code'] == 'DISPLAY_NOT_GENERATED'
                scheduled = _tool_data(await _call_operation(session, 'data_media_schedule', {'asset_id': asset_id}), service)
                assert scheduled['status'] in {'generating', 'available'}
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    state = _tool_data(await _call_operation(session, 'data_media_status', {'asset_id': asset_id}), service)
                    if state['status'] != 'generating':
                        break
                    await asyncio.sleep(0.1)
                assert state['status'] == 'available' and (state['width'], state['height']) == (1080, 540), state
                result = await _call_operation(session, 'data_media_read', {'asset_id': asset_id})
                assert not result.is_error and result.structured_content is None
                assert len(result.content) == 1 and result.content[0].type == 'image'
                assert result.content[0].mime_type == 'image/jpeg'
                jpeg = b64decode(result.content[0].data)
                with Image.open(BytesIO(jpeg)) as image:
                    assert image.format == 'JPEG' and image.size == (1080, 540)
                assert _tool_data(await _call_operation(session, 'data_media_schedule', {'asset_id': asset_id}), service)['status'] == 'available'
                return jpeg
    jpeg = asyncio.run(exercise_preview())
    assert _cli_json(service, 'data_media_status', asset_id=asset_id)['status'] == 'available'
    output = tmp_path / 'display.jpg'
    exported = _cli_json(service, 'data_media_export', asset_id=asset_id, output=str(output))
    assert exported == {'path': str(output.resolve()), 'byte_size': len(jpeg)}
    assert output.read_bytes() == jpeg
    collision = subprocess.run([_entrypoint('apf'), 'call-tool', 'data_media_export', '--asset-id', asset_id, '--output', str(photo)], cwd=ROOT, env=service['env'], capture_output=True, text=True, check=False, encoding='utf-8')
    assert collision.returncode == 1 and photo.name in re.sub('\\s+', '', collision.stdout + collision.stderr)
    assert photo.read_bytes() == original

def test_apf_mcp_confirmed_recursive_batch_and_fixed_project_links(service, tmp_path, record_property):
    import numpy as np
    from astropy.io import fits
    root = tmp_path / 'synthetic-night'
    (root / 'nested').mkdir(parents=True)
    for path in [root / 'first.fits', root / 'nested/second.fits']:
        fits.writeto(path, np.arange(64, dtype=np.float32).reshape(8, 8), fits.Header({'OBJECT': 'M31', 'IMAGETYP': 'Light Frame', 'EXPTIME': 0, 'GAIN': 0}))

    async def exercise():
        params = StdioServerParameters(command=_entrypoint('apf'), args=['mcp'], env=service['env'], cwd=str(ROOT))
        async with stdio_client(params) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                advertised = (await session.list_tools()).tools
                assert {tool.name for tool in advertised} == {'search_tools', 'call_tool'}
                record_property('advertised_schema_bytes', len(json.dumps([tool.input_schema for tool in advertised]).encode()))

                async def call(operation, arguments):
                    start = time.perf_counter()
                    result = _tool_data(await session.call_tool(operation, arguments), service)
                    record_property(operation + '_seconds', time.perf_counter() - start)
                    return result
                baseline = await call('data_assets_search', {'query': {'limit': 50}})
                scan = await call('data_imports_inspect', {'paths': [str(root)]})
                assert scan['file_count'] == 2 and 'groups' not in scan
                before = await call('data_assets_search', {'query': {'limit': 50}})
                assert before['total'] == baseline['total']
                for tool_name, query in (
                    ('data_imports_import_dataset', 'import dataset scan_id files calibration'),
                    ('data_tasks_wait', 'wait import task request_id wait_seconds'),
                ):
                    discovered = await session.call_tool('search_tools', {'query': query})
                    definitions = json.loads(_result_text(discovered))
                    assert tool_name in {row['name'] for row in definitions}
                    assert len(definitions) <= 10
                project = await call('data_projects_create', {'body': {'name': 'Confirmed night'}})
                entries = await call('data_imports_entries', {'scan_id': scan['scan_id']})
                arguments = {'scan_id': scan['scan_id'], 'request_id': str(uuid4()), 'name': 'Confirmed M31', 'files': [{'file_id': row['file_id']} for row in entries['items']]}
                accepted = await call('data_imports_import_dataset', arguments)
                completed = await call('data_tasks_wait', {'request_id': arguments['request_id'], 'wait_seconds': 20})
                assert completed['state'] == 'completed', completed
                assert completed['items_total'] == 2
                publication = completed['stages']['publication']
                link = await call('data_projects_add_dataset', {'project_id': project['id'], 'body': {'base_revision': project['revision'], 'dataset_id': publication['dataset_id']}})
                repeated = await call('data_imports_import_dataset', arguments)
                assert repeated['task_id'] == accepted['task_id']
                assets = await call('data_assets_search', {'query': {'limit': 50}})
                assert assets['total'] == baseline['total'] + 2
                references = await call('data_projects_list_datasets', {'project_id': project['id'], 'limit': 50})
                assert references['total'] == 1
                assert references['items'][0]['dataset_id'] == link['dataset_id']
    asyncio.run(exercise())
