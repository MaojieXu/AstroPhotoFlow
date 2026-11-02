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
        if isinstance(value, list):
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
    listed = _cli_json(service, 'data_assets_list', query={'limit': 10})
    asset_id = str(task['items'][0]['asset_id'])
    assert asset_id in {str(item['id']) for item in listed['items']}
    asset = _cli_json(service, 'data_assets_get', asset_id=asset_id)
    assert asset['parameters']['exposure_seconds'] is None
    updated = _cli_json(service, 'data_assets_update_parameters', asset_id=asset_id, base_revision=asset['revision'], parameters={'exposure_seconds': 0})
    assert updated['parameters']['exposure_seconds'] == 0
    assert _cli_json(service, 'data_assets_get', asset_id=asset_id)['parameters']['exposure_seconds'] == 0

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
                assets = _tool_data(await _call_operation(session, 'data_assets_list', {'query': {'limit': 50, 'offset': 0}}, read_timeout_seconds=5), service)
                assert asset_id in {str(item['id']) for item in assets['items']}
                asset = _tool_data(await _call_operation(session, 'data_assets_get', {'asset_id': asset_id}, read_timeout_seconds=5), service)
                assert asset['revision'] == 1
                prepared = _tool_data(await _call_operation(session, 'data_assets_prepare_canvas_data', {'body': {'entry_type': 'asset', 'id': asset_id, 'version_id': asset['current_version_id']}}, read_timeout_seconds=5), service)
                assert prepared['native_type'] == 'APF_DATA_REFERENCE'
                assert prepared['reference']['asset_version_id'] == asset['current_version_id']
                first = _tool_data(await _call_operation(session, 'data_assets_update_parameters', {'asset_id': asset_id, 'base_revision': 1, 'parameters': {'gain': 0, 'exposure_seconds': 0}}, read_timeout_seconds=5), service)
                assert first['parameters']['gain'] == 0
                assert first['parameters']['exposure_seconds'] == 0
                cleared = _tool_data(await _call_operation(session, 'data_assets_update_parameters', {'asset_id': asset_id, 'base_revision': 2, 'parameters': {'gain': None}}, read_timeout_seconds=5), service)
                assert cleared['parameters']['gain'] is None
                assert cleared['parameters']['exposure_seconds'] == 0
                stale = await _call_operation(session, 'data_assets_update_parameters', {'asset_id': asset_id, 'base_revision': 2, 'parameters': {'exposure_seconds': 12}}, read_timeout_seconds=5)
                assert stale.is_error
                assert 'REVISION_CONFLICT' in _result_text(stale)
                current = _tool_data(await _call_operation(session, 'data_assets_get', {'asset_id': asset_id}, read_timeout_seconds=5), service)
                assert current['revision'] == 3
                assert current['parameters']['exposure_seconds'] == 0
    asyncio.run(exercise_protocol())

def test_apf_mcp_business_domains_protocol(service, tmp_path):

    async def exercise_protocol():
        params = StdioServerParameters(command=_entrypoint('apf'), args=['mcp'], env=service['env'], cwd=str(ROOT))
        async with stdio_client(params) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()

                async def call(name, **arguments):
                    return _tool_data(await _call_operation(session, name, arguments, read_timeout_seconds=10), service)
                equipment = {}
                for kind in ('camera', 'telescope', 'filter'):
                    created = await call('data_equipment_create_item', body={'kind': kind, 'name': 'SDK ' + kind})
                    equipment[kind] = created
                    assert (await call('data_equipment_get_item', equipment_id=created['id']))['kind'] == kind
                assert (await call('data_equipment_list_items', query={'kind': 'camera', 'limit': 1}))['total'] >= 1
                setup = await call('data_setups_create', body={'name': 'SDK setup', 'components': [{'source': 'registered', 'equipment_id': equipment['camera']['id']}, {'source': 'inline', 'equipment': {'kind': 'telescope', 'name': 'Inline only'}}]})
                assert (await call('data_equipment_list_items', query={'q': 'Inline only'}))['total'] == 0
                assert (await call('data_setups_get', setup_id=setup['id']))['components'] == setup['components']
                assert (await call('data_setups_list', query={'q': 'SDK setup'}))['total'] == 1
                preset = await call('data_presets_create', setup_id=setup['id'], body={'parameters': {'parameter_mode': 'gain', 'gain': 0, 'exposure_seconds': 30}})
                assert (await call('data_presets_get', preset_id=preset['id']))['equipment_setup_id'] == setup['id']
                assert (await call('data_presets_list', query={'equipment_setup_id': setup['id']}))['total'] == 1
                paths = [tmp_path / 'night-one.png', tmp_path / 'night-two.png']
                for path in paths:
                    _write_png(path)
                accepted = await call('data_imports_upload', paths=[str(path) for path in paths], options={'capture_preset_id': preset['id'], 'classification': {'frame_class': 'subframe', 'frame_type': 'light'}, 'dataset_name': 'SDK night batch'})
                task = await _wait_mcp_task(session, service, accepted['task_id'])
                assert len(task['items']) == 2 and task['report']['registration']['completed']
                assert (await call('data_tasks_get', task_id=task['id'], items_limit=1, items_offset=1))['items'][0]['id'] == task['items'][1]['id']
                assert (await call('data_tasks_list', limit=1))['items']
                asset_ids = [item['asset_id'] for item in task['items']]
                version_ids = [item['asset_version_id'] for item in task['items']]
                asset = await call('data_assets_get', asset_id=asset_ids[0])
                assert asset['classification']['frame_type'] == 'light'
                assert asset['parameters']['gain'] == 0
                await call('data_presets_update', preset_id=preset['id'], body={'base_revision': 1, 'parameters': {'gain': 88}})
                assert (await call('data_assets_get', asset_id=asset_ids[0]))['parameters']['gain'] == 0
                asset = await call('data_assets_update', asset_id=asset_ids[0], body={'base_revision': asset['revision'], 'notes': 'temporary', 'parameters': {'exposure_seconds': 0}})
                asset = await call('data_assets_update', asset_id=asset_ids[0], body={'base_revision': asset['revision'], 'notes': None, 'classification': {'frame_class': 'subframe', 'frame_type': 'light'}})
                assert asset['notes'] is None and asset['parameters']['exposure_seconds'] == 0
                assert (await call('data_assets_get_version', asset_id=asset_ids[0], version_id=version_ids[0]))['availability'] == 'available'
                assert (await call('data_assets_list_versions', asset_id=asset_ids[0]))['total'] == 1
                assert (await call('data_library_search', query={'q': 'SDK night batch'}))['items']
                import numpy as np
                from astropy.io import fits
                master_path = tmp_path / 'master-dark.fits'
                hdu = fits.PrimaryHDU(np.arange(256, dtype=np.float32).reshape(16, 16))
                hdu.header['IMAGETYP'] = 'Master Dark'
                hdu.writeto(master_path)
                master_task = await _wait_mcp_task(session, service, (await call('data_imports_upload_one', path=str(master_path), options={'capture_preset_id': preset['id']}))['task_id'])
                master = await call('data_assets_get', asset_id=master_task['items'][0]['asset_id'])
                assert master['classification'] == {'frame_class': 'masterframe', 'frame_type': 'dark'}
                targets = await call('data_calibration_targets', frame_type='dark', limit=1, offset=0)
                assert targets['items'][0]['target'] == {'kind': 'asset_version', 'id': master['current_version_id']}
                group = await call('data_datasets_create', body={'name': 'SDK logical group', 'asset_version_ids': version_ids})
                assert (await call('data_datasets_list', query={'q': group['name']}))['total'] == 1
                bound = await call('data_datasets_publish_version', dataset_id=group['id'], body={'base_revision': group['revision'], 'asset_version_ids': version_ids, 'calibration_defaults': {'dark': targets['items'][0]['target']}, 'member_calibration_overrides': {version_ids[0]: {'dark': None}}})
                assert bound['calibration_defaults']['dark']['id'] == master['current_version_id']
                assert bound['members'][0]['calibration_overrides'] == {'dark': None}
                assert await call('data_datasets_get_version', dataset_id=group['id'], version_id=bound['id']) == bound
                assert (await call('data_datasets_list_versions', dataset_id=group['id']))['total'] == 2
                group = await call('data_datasets_get', dataset_id=group['id'])
                revisions = [(await call('data_assets_get', asset_id=identity))['revision'] for identity in asset_ids]
                edited = await call('data_datasets_update_members', dataset_id=group['id'], body={'base_revision': group['revision'], 'base_version_id': bound['id'], 'members': [{'asset_id': identity, 'revision': revision} for identity, revision in zip(asset_ids, revisions)], 'parameters': {'gain': 0}})
                assert len(edited['assets']) == 2 and all((item['parameters']['gain'] == 0 for item in edited['assets']))
                project = await call('data_projects_create', body={'name': 'SDK M31', 'target_name': 'M31'})
                assert (await call('data_projects_list', query={'q': 'SDK M31'}))['total'] == 1
                asset_ref = await call('data_projects_add_asset', project_id=project['id'], body={'base_revision': 1, 'asset_version_id': version_ids[0]})
                group_now = await call('data_datasets_get', dataset_id=group['id'])
                dataset_ref = await call('data_projects_add_dataset', project_id=project['id'], body={'base_revision': 2, 'dataset_id': group['id'], 'dataset_version_id': group_now['current_version_id']})
                assert (await call('data_projects_list_assets', project_id=project['id']))['items'][0]['id'] == asset_ref['id']
                assert (await call('data_projects_get_asset', project_id=project['id'], reference_id=asset_ref['id']))['asset_version_id'] == version_ids[0]
                assert (await call('data_projects_list_datasets', project_id=project['id']))['total'] == 1
                assert (await call('data_projects_get_dataset', project_id=project['id'], reference_id=dataset_ref['id']))['dataset_version_id'] == group_now['current_version_id']
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
                local = await call('data_imports_local', body={'sources': [{'root_id': 'science', 'path': 'sdk-night'}], 'storage_mode': 'reference'})
                for _ in range(100):
                    local_task = await call('data_tasks_get', task_id=local['task_id'])
                    if local_task['status'] in FINAL_TASK_STATUSES:
                        break
                    await asyncio.sleep(0.1)
                assert local_task['status'] == 'completed_with_errors'
                broken = next((item for item in local_task['items'] if item['source_path'].endswith('broken.fits')))
                hdu.writeto(night / 'broken.fits', overwrite=True)
                retry = await call('data_tasks_retry', task_id=local_task['id'], body={'item_ids': [broken['id']]})
                repaired = await _wait_mcp_task(session, service, retry['task_id'])
                assert repaired['items'][0]['retry_of_item_id'] == broken['id']
                if broken['asset_id']:
                    assert repaired['items'][0]['asset_id'] == broken['asset_id']
                assert (night / 'good.png').is_file()
                for tool_name in ('data_tasks_cancel', 'data_tasks_resume'):
                    rejected = await _call_operation(session, tool_name, {'task_id': task['id']})
                    assert rejected.is_error
                    failure = ErrorEnvelope.model_validate_json(_result_text(rejected))
                    assert failure.error.code == 'TASK_STATE_CONFLICT'
                    assert failure.request_id
                disposable = tmp_path / 'disposable.png'
                _write_png(disposable)
                disposable_task = await _wait_mcp_task(session, service, (await call('data_imports_upload_one', path=str(disposable)))['task_id'])
                disposable_asset = await call('data_assets_get', asset_id=disposable_task['items'][0]['asset_id'])
                assert disposable_asset['classification'] == {'frame_class': None, 'frame_type': None}
                remove = {'items': [{'entry_type': 'asset', 'id': disposable_asset['id'], 'revision': disposable_asset['revision'], 'current_version_id': disposable_asset['current_version_id']}]}
                await call('data_trash_remove', body=remove)
                trash = await call('data_trash_list')
                entry = next((item for item in trash['items'] if item['id'] == disposable_asset['id']))
                selection = {'items': [{key: entry[key] for key in ('entry_type', 'id', 'removed_at', 'revision', 'current_version_id', 'source_dataset_id')}]}
                await call('data_trash_restore', body=selection)
                await call('data_trash_remove', body=remove)
                entry = next((item for item in (await call('data_trash_list'))['items'] if item['id'] == disposable_asset['id']))
                selection = {'items': [{key: entry[key] for key in ('entry_type', 'id', 'removed_at', 'revision', 'current_version_id', 'source_dataset_id')}]}
                preview = await call('data_trash_preview_delete', body=selection)
                assert preview['photo_count'] == 1 and preview['managed_file_count'] >= 1 and (not preview['references'])
                deleted = await call('data_trash_delete', body={**selection, 'preview_fingerprint': preview['preview_fingerprint']})
                assert deleted['deleted_file_count'] == preview['managed_file_count'] and (not deleted['failed'])
                assert disposable.is_file()
                for kind, item in equipment.items():
                    assert (await call('data_equipment_update_item', equipment_id=item['id'], body={'kind': kind, 'base_revision': 1, 'status': 'archived'}))['status'] == 'archived'
                assert (await call('data_setups_update', setup_id=setup['id'], body={'base_revision': 1, 'status': 'archived'}))['status'] == 'archived'
                assert (await call('data_presets_update', preset_id=preset['id'], body={'base_revision': 2, 'status': 'archived'}))['status'] == 'archived'
                assert (await call('data_datasets_update', dataset_id=group['id'], body={'base_revision': group_now['revision'], 'status': 'archived'}))['status'] == 'archived'
    asyncio.run(exercise_protocol())

def test_apf_cli_structured_domain_workflow(service, tmp_path):

    def command(tool, **arguments):
        return _cli_json(service, tool, **arguments)
    camera = command('data_equipment_create_item', body={'kind': 'camera', 'name': 'CLI Camera'})
    assert command('data_equipment_list_items', query={'kind': 'camera', 'q': 'CLI Camera'})['total'] == 1
    setup = command('data_setups_create', body={'name': 'CLI setup', 'components': [{'source': 'registered', 'equipment_id': camera['id']}]})
    preset = command('data_presets_create', setup_id=setup['id'], body={'parameters': {'parameter_mode': 'gain', 'gain': 0}})
    assert command('data_presets_list', query={'equipment_setup_id': setup['id']})['total'] == 1
    paths = [tmp_path / 'cli-bulk-a.png', tmp_path / 'cli-bulk-b.png']
    for path in paths:
        _write_png(path)
    task = _wait_cli_task(service, command('data_imports_upload', paths=list(map(str, paths)), options={'capture_preset_id': preset['id'], 'dataset_name': 'CLI batch'})['task_id'])
    assert command('data_tasks_get', task_id=task['id'], items_limit=1, items_offset=1)['items'][0]['id'] == task['items'][1]['id']
    assert command('data_assets_get', asset_id=task['items'][0]['asset_id'])['parameters']['gain'] == 0
    versions = [item['asset_version_id'] for item in task['items']]
    group = command('data_datasets_create', body={'name': 'CLI logical group', 'asset_version_ids': versions})
    publication = command('data_datasets_publish_version', dataset_id=group['id'], body={'base_revision': group['revision'], 'asset_version_ids': versions, 'calibration_defaults': {}, 'member_calibration_overrides': {versions[0]: {'dark': None}}})
    assert command('data_datasets_get_version', dataset_id=group['id'], version_id=publication['id'])['members'][0]['calibration_overrides'] == {'dark': None}
    project = command('data_projects_create', body={'name': 'CLI project'})
    reference = command('data_projects_add_dataset', project_id=project['id'], body={'base_revision': project['revision'], 'dataset_id': group['id'], 'dataset_version_id': publication['id']})
    assert command('data_projects_list_datasets', project_id=project['id'])['items'][0]['id'] == reference['id']
    command('data_projects_remove_dataset', project_id=project['id'], reference_id=reference['id'], body={'base_revision': 2})
    assert command('data_projects_update', project_id=project['id'], body={'base_revision': 3, 'status': 'archived'})['status'] == 'archived'
    assert command('data_presets_update', preset_id=preset['id'], body={'base_revision': 1, 'status': 'archived'})['status'] == 'archived'
    assert command('data_setups_update', setup_id=setup['id'], body={'base_revision': 1, 'status': 'archived'})['status'] == 'archived'
    assert command('data_equipment_update_item', equipment_id=camera['id'], body={'kind': 'camera', 'base_revision': 1, 'status': 'archived'})['status'] == 'archived'
    rejected = subprocess.run([_entrypoint('apf'), 'call-tool', 'data_assets_update', '--asset-id', task['items'][0]['asset_id'], '--body', '{"base_revision":0}'], cwd=ROOT, env=service['env'], capture_output=True, text=True, check=False, encoding='utf-8')
    assert rejected.returncode != 0 and 'base_revision' in rejected.stdout + rejected.stderr

def test_apf_display_preview_stdio_image_and_cli_export(service, tmp_path):
    from base64 import b64decode
    from io import BytesIO
    photo = tmp_path / 'preview-source.png'
    Image.new('RGB', (1600, 800), color=(32, 64, 96)).save(photo, format='PNG')
    original = photo.read_bytes()
    task = _wait_cli_task(service, _cli_json(service, 'data_imports_upload_one', path=str(photo))['task_id'])
    asset_id, version_id = (task['items'][0]['asset_id'], task['items'][0]['asset_version_id'])

    async def exercise_preview():
        params = StdioServerParameters(command=_entrypoint('apf'), args=['mcp'], env=service['env'], cwd=str(ROOT))
        async with stdio_client(params) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                initial = _tool_data(await _call_operation(session, 'data_media_status', {'asset_id': asset_id, 'version_id': version_id}), service)
                assert initial['status'] == 'not_ready' and initial['error']['code'] == 'DISPLAY_NOT_GENERATED'
                scheduled = _tool_data(await _call_operation(session, 'data_media_schedule', {'asset_id': asset_id, 'version_id': version_id}), service)
                assert scheduled['status'] in {'generating', 'available'}
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    state = _tool_data(await _call_operation(session, 'data_media_status', {'asset_id': asset_id, 'version_id': version_id}), service)
                    if state['status'] != 'generating':
                        break
                    await asyncio.sleep(0.1)
                assert state['status'] == 'available' and (state['width'], state['height']) == (1080, 540), state
                result = await _call_operation(session, 'data_media_read', {'asset_id': asset_id, 'version_id': version_id})
                assert not result.is_error and result.structured_content is None
                assert len(result.content) == 1 and result.content[0].type == 'image'
                assert result.content[0].mime_type == 'image/jpeg'
                jpeg = b64decode(result.content[0].data)
                with Image.open(BytesIO(jpeg)) as image:
                    assert image.format == 'JPEG' and image.size == (1080, 540)
                assert _tool_data(await _call_operation(session, 'data_media_schedule', {'asset_id': asset_id, 'version_id': version_id}), service)['status'] == 'available'
                return jpeg
    jpeg = asyncio.run(exercise_preview())
    assert _cli_json(service, 'data_media_status', asset_id=asset_id, version_id=version_id)['status'] == 'available'
    output = tmp_path / 'display.jpg'
    exported = _cli_json(service, 'data_media_export', asset_id=asset_id, version_id=version_id, output=str(output))
    assert exported == {'path': str(output.resolve()), 'byte_size': len(jpeg)}
    assert output.read_bytes() == jpeg
    collision = subprocess.run([_entrypoint('apf'), 'call-tool', 'data_media_export', '--asset-id', asset_id, '--version-id', version_id, '--output', str(photo)], cwd=ROOT, env=service['env'], capture_output=True, text=True, check=False, encoding='utf-8')
    assert collision.returncode == 1 and photo.name in re.sub(r'\s+', '', collision.stdout + collision.stderr)
    assert photo.read_bytes() == original

def test_apf_mcp_confirmed_recursive_batch_and_fixed_project_links(service, tmp_path, record_property):
    import numpy as np
    from astropy.io import fits
    from uuid import uuid4
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
                baseline = await call('data_assets_list', {'query': {'limit': 50}})
                scan = await call('data_imports_inspect', {'body': {'paths': [str(root)]}})
                assert scan['file_count'] == 2
                before = await call('data_assets_list', {'query': {'limit': 50}})
                assert before['total'] == baseline['total']
                discovered = await session.call_tool('search_tools', {'query': 'data_imports_submit data_tasks_wait'})
                definitions = json.loads(_result_text(discovered))
                assert {'data_imports_submit', 'data_tasks_wait'} <= {row['name'] for row in definitions}
                assert len(definitions) <= 10
                project = await call('data_projects_create', {'body': {'name': 'Confirmed night'}})
                body = {'scan_id': scan['scan_id'], 'request_id': str(uuid4()), 'project_id': project['id'], 'project_revision': project['revision'], 'groups': [{'name': 'Confirmed M31', 'group_id': scan['groups'][0]['id']}]}
                accepted = await call('data_imports_submit', {'body': body})
                completed = await call('data_tasks_wait', {'body': {'request_id': body['request_id'], 'wait_seconds': 20}})
                assert completed['state'] == 'completed', completed
                assert completed['groups'][0]['items_total'] == 2
                link = completed['groups'][0]['project_link']
                assert link['state'] == 'linked'
                repeated = await call('data_imports_submit', {'body': body})
                assert repeated['groups'][0]['task_id'] == accepted['groups'][0]['task_id']
                assets = await call('data_assets_list', {'query': {'limit': 50}})
                assert assets['total'] == baseline['total'] + 2
                references = await call('data_projects_list_datasets', {'project_id': project['id'], 'limit': 50})
                assert references['total'] == 1
                assert references['items'][0]['dataset_version_id'] == link['dataset_version_id']
    asyncio.run(exercise())
