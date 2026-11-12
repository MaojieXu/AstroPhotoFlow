"""The conversational image surface has explicit, typed and bounded contracts."""
import json
from uuid import UUID
import pytest
from fastmcp import Client
from pydantic import ValidationError
from astrophotoflow.contracts.image_calibration import ImageCalibrationUpdate
from astrophotoflow.contracts.image_imports import ExplicitImportRequest
from astrophotoflow.contracts.image_management import ImageChanges, ImageSearch, ImageTimes, ScientificTime
from astrophotoflow.interfaces.client.errors import ServiceApiError
from astrophotoflow.interfaces.mcp import lifespan
from astrophotoflow.interfaces.mcp.server import build_tool_catalog
ASSET = '00000000-0000-4000-8000-000000000001'
VERSION = '00000000-0000-4000-8000-000000000002'
REQUEST = '00000000-0000-4000-8000-000000000003'
CORE = {'imports': {'inspect', 'get_inspection', 'entries', 'import_asset', 'import_dataset', 'append_dataset', 'retry_publication'}, 'assets': {'search', 'get', 'update', 'update_metadata_batch', 'apply_equipment', 'read_header', 'get_master_provenance', 'update_master_provenance'}, 'datasets': {'search', 'get', 'create', 'update', 'members', 'edit_members'}, 'calibration': {'search', 'check', 'check_import', 'get_image', 'update_image', 'get_dataset', 'update_dataset', 'get_operation'}}

class ImageService:

    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def image_assets_update(self, **values):
        self.calls.append(('update', values))
        raise ServiceApiError(409, 'REVISION_CONFLICT', 'Changed', REQUEST, [{'path': 'expected_revision', 'message': 'Read it again.'}])

    def image_calibration_update_image(self, **values):
        self.calls.append(('binding', values))
        return {'request_id': REQUEST, 'operation': 'update_image', 'result': {'asset_id': ASSET}, 'message': '关系已保存，尚未执行校准。'}

    def image_imports_inspect(self, **values):
        self.calls.append(('inspect', values))
        return {'scan_id': REQUEST, 'recursive': values['recursive'], 'roots': values['paths'], 'file_count': 1, 'excluded_count': 0, 'issues': [], 'issues_total': 0}

@pytest.fixture
def service(monkeypatch):
    service = ImageService()
    monkeypatch.setattr(lifespan, 'AssetClient', lambda: service)
    return service

@pytest.mark.asyncio
async def test_core_and_tasks_have_typed_top_level_inputs(service):
    async with Client(build_tool_catalog()) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}
    expected = {f'data_{namespace}_{name}' for namespace, names in CORE.items() for name in names}
    assert len(expected) == 29
    assert expected <= tools.keys()
    tasks = {name for name in tools if name.startswith('data_tasks_')}
    assert tasks == {f'data_tasks_{name}' for name in ('list', 'get', 'status', 'wait', 'cancel', 'resume', 'retry', 'recover_organization')}
    for name in expected | tasks:
        schema = tools[name].input_schema
        assert 'client' not in schema['properties']
        if name == 'data_tasks_recover_organization':
            assert schema['properties']['body']['type'] == 'object'
            assert set(schema['properties']['body']['required']) == {'request_id', 'mode'}
        else:
            assert 'body' not in schema['properties']
        assert tools[name].output_schema
    assert 'group_id' not in tools['data_imports_entries'].input_schema['properties']
    assert 'data_imports_submit' not in tools
    image_binding = tools['data_calibration_update_image'].input_schema
    assert 'expected_revision' in image_binding['required']
    assert 'base_binding_version_id' not in image_binding['properties']
    assert tools['data_tasks_wait'].input_schema['properties']['wait_seconds']['maximum'] == 20
    for name in ('import_asset', 'import_dataset', 'append_dataset'):
        prompt = tools[f'data_imports_{name}'].description
        assert 'user confirmation' in prompt
        assert 'Unknown values are allowed' in prompt
        assert 'selected Master does not mean all unknowns were accepted' in prompt
        assert 'Few-shot' in prompt

@pytest.mark.asyncio
async def test_image_patch_preserves_sparse_null_and_zero_and_service_error(service):
    async with Client(build_tool_catalog()) as client:
        result = await client.call_tool('data_assets_update', {'asset_id': ASSET, 'expected_revision': 2, 'changes': {'target_name': None, 'parameters': {'gain': 0, 'offset': 0, 'readout_mode': None}, 'times': {'capture_start': {'raw_value': '2026-11-02T01:02:03', 'time_system': 'UNKNOWN'}}}}, raise_on_error=False)
    assert result.is_error
    error = json.loads(result.content[0].text)
    assert error['error']['code'] == 'REVISION_CONFLICT'
    assert error['error']['fields'][0]['path'] == 'expected_revision'
    values = service.calls[0][1]
    assert values['asset_id'] == UUID(ASSET)
    assert values['changes'].model_dump(mode='json', exclude_unset=True) == {'target_name': None, 'parameters': {'gain': 0.0, 'offset': 0.0, 'readout_mode': None}, 'times': {'capture_start': {'raw_value': '2026-11-02T01:02:03', 'time_system': 'UNKNOWN'}}}

@pytest.mark.asyncio
async def test_standalone_binding_uses_current_revision_and_does_not_execute(service):
    payload = {'request_id': REQUEST, 'asset_id': ASSET, 'expected_revision': 1, 'changes': {'dark': {'mode': 'disabled'}}}
    async with Client(build_tool_catalog()) as client:
        result = await client.call_tool('data_calibration_update_image', payload)
    assert result.structured_content['message'] == '关系已保存，尚未执行校准。'
    assert len(service.calls) == 1
    assert service.calls[0][1]['changes'].model_dump(exclude_unset=True) == {'dark': {'mode': 'disabled'}}

@pytest.mark.asyncio
async def test_inspection_returns_facts_without_server_grouping(service):
    async with Client(build_tool_catalog()) as client:
        result = await client.call_tool('data_imports_inspect', {'paths': ['C:/night'], 'recursive': True})
    assert result.structured_content['file_count'] == 1
    assert 'groups' not in result.structured_content
    assert service.calls == [('inspect', {'paths': ['C:/night'], 'recursive': True})]

@pytest.mark.asyncio
async def test_task_status_and_wait_preserve_existing_project_batch_receipts(service):
    receipt = {'request_id': REQUEST, 'state': 'completed', 'groups': [], 'errors': [], 'errors_total': 0, 'next_poll_seconds': None}
    service.image_tasks_status = lambda **values: receipt
    service.image_tasks_wait = lambda **values: receipt
    async with Client(build_tool_catalog()) as client:
        for name in ('status', 'wait'):
            result = await client.call_tool(f'data_tasks_{name}', {'request_id': REQUEST})
            payload = result.structured_content['result']
            assert payload['state'] == 'completed'
            assert payload['groups'] == []
        failed = await client.call_tool('data_tasks_wait', {'request_id': REQUEST, 'wait_seconds': 21}, raise_on_error=False)
        assert failed.is_error

@pytest.mark.asyncio
async def test_task_get_preserves_explicit_import_stage_receipt_and_page(service):
    receipt = {'request_id': REQUEST, 'task_id': ASSET, 'status': 'queued', 'state': 'running', 'stages': {'registration': {'total': 0, 'registered': 0}, 'originals': {'available': 0, 'total': 0}, 'metadata': {'available': 0, 'total': 0}, 'publication': {'state': 'pending'}, 'calibration': {}, 'previews': {'available': 0, 'total': 0}}, 'items': [], 'items_total': 0, 'items_limit': 5, 'items_offset': 0, 'next_poll_seconds': 5, 'error': None}

    def get(**values):
        service.calls.append(('task', values))
        return receipt
    service.image_tasks_get = get
    async with Client(build_tool_catalog()) as client:
        result = await client.call_tool('data_tasks_get', {'task_id': ASSET, 'items_limit': 5})
    payload = result.structured_content['result']
    assert payload['stages']['publication']['state'] == 'pending'
    assert payload['items_limit'] == 5
    assert service.calls == [('task', {'task_id': UUID(ASSET), 'items_limit': 5, 'items_offset': 0})]

def test_contracts_reject_implicit_timezone_wrong_equipment_channel_and_inherit_defaults():
    assert ScientificTime.model_validate({'utc': '2026-11-02T01:02:03Z'}).utc.utcoffset().total_seconds() == 0
    with pytest.raises(ValidationError):
        ScientificTime.model_validate_json('{"utc":"2026-11-02T01:02:03"}')
    with pytest.raises(ValidationError):
        ScientificTime.model_validate({'utc': 1793581323})
    with pytest.raises(ValidationError):
        ImageTimes.model_validate_json('{"capture_start":{"utc":"2026-11-02T02:00:00Z"},"capture_end":{"utc":"2026-11-02T01:00:00Z"}}')
    with pytest.raises(ValidationError):
        ImageChanges.model_validate({'parameters': {'camera_id': UUID(ASSET)}})
    with pytest.raises(ValidationError):
        ImageCalibrationUpdate.model_validate({'request_id': UUID(REQUEST), 'expected_revision': 1, 'changes': {'dark': {'mode': 'inherit'}}})
    assert ImageSearch.model_validate({'limit': '20', 'gain_min': '0'}).gain_min == 0

def test_import_contract_requires_explicit_unique_files_and_correct_destination_slots():
    base = {'request_id': UUID(REQUEST), 'scan_id': UUID(VERSION), 'files': [{'file_id': UUID(ASSET)}], 'destination': {'mode': 'standalone'}}
    assert ExplicitImportRequest.model_validate(base).destination.mode == 'standalone'
    with pytest.raises(ValidationError):
        ExplicitImportRequest.model_validate({**base, 'files': base['files'] * 2})
    with pytest.raises(ValidationError):
        ExplicitImportRequest.model_validate({**base, 'calibration_defaults': {'dark': {'mode': 'disabled'}}})
    append = {**base, 'destination': {'mode': 'append_dataset', 'dataset_id': UUID(ASSET), 'expected_revision': 2}}
    assert ExplicitImportRequest.model_validate(append).destination.expected_revision == 2
    with pytest.raises(ValidationError, match='incoming_calibration'):
        ExplicitImportRequest.model_validate({**append, 'incoming_calibration': {'flat': {'mode': 'unconfigured'}}})
