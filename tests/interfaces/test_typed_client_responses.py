from datetime import datetime
from uuid import UUID
import httpx
import pytest
from astrophotoflow.client import AssetClient, ServiceApiError
from astrophotoflow.contracts.assets import AssetOut, AssetPatch
from astrophotoflow.contracts.equipment import CameraOut
from astrophotoflow.contracts.software import BundlePreviewRequest
from astrophotoflow.interfaces.serialization import json_value
IDENTITY = '00000000-0000-4000-8000-000000000001'
ASSET = {'id': IDENTITY, 'name': 'M31', 'scope': 'shared', 'owner_project_id': None, 'role': 'raw', 'calibration_level': None, 'classification': {}, 'parameters': {'gain': 0, 'offset': None}, 'equipment_snapshot': {}, 'value_sources': {}, 'notes': None, 'status': 'active', 'revision': 2, 'created_at': '2026-10-31T00:00:00Z', 'view_base': f'/library/assets/{IDENTITY}/previews', 'storage_mode': 'managed', 'storage_location': f'objects/{IDENTITY}/source.fits', 'byte_size': 1, 'content_hash': None, 'availability': 'unknown', 'capture_snapshot': None, 'scientific_metadata': None}

def client_with_response(payload):
    client = AssetClient.__new__(AssetClient)
    client.client = httpx.Client(base_url='http://isolated-test/api/v1', transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload, headers={'X-Request-ID': 'typed-response'})))
    return client

def test_json_response_mode_preserves_strict_dates_uuid_zero_and_null():
    with client_with_response(ASSET) as client:
        result = client.get_asset(IDENTITY)
    assert isinstance(result, AssetOut)
    assert result.id == UUID(IDENTITY)
    assert isinstance(result.created_at, datetime)
    assert result.parameters.gain == 0
    assert 'offset' in result.parameters.model_fields_set
    assert result.parameters.offset is None
    assert json_value(result)['created_at'] == ASSET['created_at']
    assert json_value(result)['parameters'] == {'gain': 0, 'offset': None}
    assert json_value([result])[0]['id'] == IDENTITY

def test_page_responses_validate_and_materialize_their_members():
    with client_with_response({'items': [ASSET], 'total': 1, 'limit': 50, 'offset': 0}) as client:
        result = client.list_assets()
    assert result.total == 1
    assert isinstance(result.items[0], AssetOut)
    assert result.items[0].id == UUID(IDENTITY)

@pytest.mark.parametrize('changes,path', [({'revision': '2'}, 'revision'), ({'unexpected': 'never-echo-this-input'}, 'unexpected'), ({'created_at': 'not-a-date'}, 'created_at')])
def test_invalid_success_is_a_response_error_with_identity_and_field_diagnostics(changes, path):
    with client_with_response({**ASSET, **changes}) as client, pytest.raises(ServiceApiError) as caught:
        client.get_asset(IDENTITY)
    assert caught.value.code == 'INVALID_RESPONSE'
    assert caught.value.status == 200
    assert caught.value.request_id == 'typed-response'
    assert any((field['path'] == path for field in caught.value.fields))
    assert 'never-echo-this-input' not in str(caught.value)
    assert all((set(field) == {'path', 'message'} for field in caught.value.fields))

def test_equipment_response_uses_the_shared_discriminator():
    payload = {'id': IDENTITY, 'name': 'Camera', 'model': None, 'notes': None, 'status': 'active', 'revision': 1, 'created_at': ASSET['created_at'], 'updated_at': ASSET['created_at'], 'kind': 'camera', 'specs': {'pixel_size_um': 3.76}}
    with client_with_response(payload) as client:
        result = client.get_equipment(IDENTITY)
    assert isinstance(result, CameraOut)
    assert result.specs.pixel_size_um == 3.76
    with client_with_response({**payload, 'kind': 'invented'}) as client, pytest.raises(ServiceApiError):
        client.get_equipment(IDENTITY)

def test_unknown_write_timeout_is_not_replayed():
    calls = []

    def timeout(request):
        calls.append(request)
        raise httpx.ReadTimeout('reply unknown', request=request)
    client = AssetClient.__new__(AssetClient)
    client.client = httpx.Client(base_url='http://isolated-test/api/v1', transport=httpx.MockTransport(timeout))
    with client, pytest.raises(httpx.ReadTimeout):
        client.update_asset(IDENTITY, AssetPatch(base_revision=2, parameters={'gain': 0}))
    assert len(calls) == 1

def test_invalid_upload_receipt_stops_before_starting_processing(tmp_path):
    source = tmp_path / 'source.bin'
    source.write_bytes(b'synthetic-science-input')
    calls = []

    def respond(request):
        calls.append(request)
        if request.url.path == '/api/v1/uploads':
            return httpx.Response(202, json={'task_id': IDENTITY, 'status': 'queued'})
        return httpx.Response(200, json={'received': -1})
    client = AssetClient.__new__(AssetClient)
    client.client = httpx.Client(base_url='http://isolated-test/api/v1', transport=httpx.MockTransport(respond))
    with client, pytest.raises(ServiceApiError, match='INVALID_RESPONSE'):
        client.import_photo(source)
    assert [call.method for call in calls] == ['POST', 'PUT']
    assert not any((call.url.path.endswith('/start') for call in calls))
    assert source.read_bytes() == b'synthetic-science-input'

def test_bundle_preview_uses_fixed_reference_zero_values_and_empty_release_response():
    import json
    calls = []

    def respond(request):
        calls.append(request)
        if request.method == 'DELETE':
            return httpx.Response(204)
        return httpx.Response(200, content=b'png', headers={'Content-Type': 'image/png'})
    body = BundlePreviewRequest.model_validate({'reference': {'kind': 'asset', 'asset_id': IDENTITY, 'selection': {'kind': 'whole_file'}}, 'consumer_id': IDENTITY, 'generation': 0, 'package_id': 'siril', 'operation_id': 'autostretch', 'parameters': {'shadowsclip': 0, 'linked': False}})
    client = AssetClient.__new__(AssetClient)
    client.client = httpx.Client(base_url='http://isolated-test/api/v1', transport=httpx.MockTransport(respond))
    with client:
        assert client.preview_bundle(body) == b'png'
        assert client.release_bundle_preview(UUID(IDENTITY)) is None
    assert calls[0].url.path == '/api/v1/software/preview'
    assert json.loads(calls[0].content) == body.model_dump(mode='json', exclude_unset=True)
    assert calls[1].url.path.endswith('/software/preview/' + IDENTITY)

def test_bundle_preview_rejects_wrong_mime_with_request_identity():
    body = BundlePreviewRequest.model_validate({'reference': {'kind': 'asset', 'asset_id': IDENTITY, 'selection': {'kind': 'whole_file'}}, 'consumer_id': IDENTITY, 'generation': 0, 'package_id': 'siril', 'operation_id': 'autostretch', 'parameters': {}})
    with client_with_response({'not': 'png'}) as client, pytest.raises(ServiceApiError) as caught:
        client.preview_bundle(body)
    assert caught.value.request_id == 'typed-response' and caught.value.code == 'INVALID_RESPONSE'
