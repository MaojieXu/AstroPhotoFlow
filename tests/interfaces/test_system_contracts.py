from uuid import uuid4
from fastapi.routing import APIRoute, iter_route_contexts
from fastapi.testclient import TestClient
from astrophotoflow.contracts.assets import AssetContentObservation
from astrophotoflow.contracts.common import ErrorEnvelope
from astrophotoflow.contracts.imports import ImportReport
from astrophotoflow.contracts.media import MediaState
from astrophotoflow.contracts.system import ServiceCapabilities, ServiceHealth
from astrophotoflow.contracts.workbench import ConfigSave
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.schema import initialize_database
from astrophotoflow.interfaces.http.app import create_app

def test_documented_operation_identities_are_explicit_and_unique(tmp_path):
    app = create_app(Settings('127.0.0.1', 8190, tmp_path, (), workspace=tmp_path), 'schema-only')
    document = app.openapi()
    identities = []
    for context in iter_route_contexts(app.routes):
        if not isinstance(context.route, APIRoute):
            continue
        for method in context.route.methods:
            operation = document['paths'].get(context.path_format, {}).get(method.lower())
            if operation is None:
                continue
            assert context.operation_id is not None, context.path_format
            assert operation['operationId'] == context.operation_id
            identities.append(context.operation_id)
    assert len(identities) == len(set(identities))

def test_every_error_response_declares_the_actual_shared_envelope(tmp_path):
    document = create_app(Settings('127.0.0.1', 8190, tmp_path, (), workspace=tmp_path), 'schema-only').openapi()
    expected = {'$ref': '#/components/schemas/ErrorEnvelope'}
    for path, methods in document['paths'].items():
        for operation in methods.values():
            responses = operation['responses']
            assert responses['default']['content']['application/json']['schema'] == expected, path
            for status, response in responses.items():
                if status.startswith(('4', '5')):
                    assert response['content']['application/json']['schema'] == expected, (path, status)
    assert 'HTTPValidationError' not in document['components']['schemas']

def test_system_and_picker_contracts_are_concrete_without_starting_services(tmp_path):
    settings = Settings('127.0.0.1', 8190, tmp_path / 'data', (), workspace=tmp_path)
    schema = create_app(settings, 'test').openapi()
    for path, method, name, operation in [('/api/v1/health', 'get', 'ServiceHealth', 'getServiceHealth'), ('/api/v1/capabilities', 'get', 'ServiceCapabilities', 'getServiceCapabilities'), ('/api/v1/exports/select-local', 'post', 'DirectorySelectionResult', 'selectExportDestination')]:
        route = schema['paths'][path][method]
        assert route['operationId'] == operation
        assert route['responses']['200']['content']['application/json']['schema'] == {'$ref': f'#/components/schemas/{name}'}
    assert not settings.database_path.exists()

def test_default_workspace_schema_expresses_omission_without_allowing_null():
    schema = ConfigSave.model_json_schema()
    field = schema['properties']['default_workspace']
    assert field['type'] == 'string'
    assert field['minLength'] == 1
    assert 'default_workspace' not in schema['required']
    assert 'default' not in field and 'anyOf' not in field

def test_upload_declares_binary_request_body(tmp_path):
    settings = Settings('127.0.0.1', 8190, tmp_path / 'data', (), workspace=tmp_path)
    schema = create_app(settings, 'test').openapi()
    body = schema['paths']['/api/v1/uploads/{task_id}/{index}']['put']['requestBody']
    assert body == {'required': True, 'content': {'application/octet-stream': {'schema': {'type': 'string', 'format': 'binary'}}}}

def test_media_response_schema_requires_every_field_actually_serialized():
    state = MediaState(key='example', status='generating')
    schema = MediaState.model_json_schema(mode='serialization')
    assert set(schema['required']) == set(state.model_dump())
    assert {'width', 'height', 'selection', 'arrays', 'hdus', 'proxy'} <= set(schema['required'])

def test_import_report_preserves_open_batch_facts_and_absent_stages():
    facts = {'registration': {'total': 0, 'registered': 0, 'completed': False}, 'agent_batch': {'request_id': str(uuid4()), 'position': 0}}
    assert ImportReport.model_validate(facts).model_dump(mode='json') == facts
    assert ImportReport.model_validate({}).model_dump(mode='json') == {}

def test_observation_nanoseconds_round_trip_without_javascript_integer_rounding():
    stamp = '1793223954488571801'
    observed = AssetContentObservation(asset_id=uuid4(), base_revision=1, storage_mode='reference', stored_hash='blake3:original', state='unchanged', observed_hash='blake3:original', observed_mtime_ns=stamp, error=None)
    assert observed.model_dump(mode='json')['observed_mtime_ns'] == stamp

def test_public_success_responses_declare_their_real_body_or_no_content(tmp_path):
    settings = Settings('127.0.0.1', 8190, tmp_path / 'data', (), workspace=tmp_path)
    schema = create_app(settings, 'test').openapi()
    for path, operations in schema['paths'].items():
        for operation in operations.values():
            for status, response in operation.get('responses', {}).items():
                if not status.startswith('2'):
                    continue
                if status == '204':
                    assert not response.get('content'), path
                    continue
                assert response.get('content'), (path, status)
                for media_type, content in response['content'].items():
                    assert content.get('schema'), (path, status, media_type)
    for suffix, expected in [('log', 'text/plain'), ('outputs/{output_index}/members/{member_index}/file', 'application/octet-stream')]:
        response = schema['paths'][f'/api/v1/runs/{{prompt_id}}/calls/{{call_id}}/{suffix}']['get']['responses']['200']
        assert set(response['content']) == {expected}

def test_system_observations_and_errors_match_their_declared_contracts(tmp_path):
    settings = Settings('127.0.0.1', 8190, tmp_path / 'data', (), workspace=tmp_path)
    initialize_database(settings)
    app = create_app(settings, 'test')
    with TestClient(app) as client:
        headers = {'Authorization': 'Bearer test'}
        health = ServiceHealth.model_validate(client.get('/api/v1/health', headers=headers).json())
        assert health.workspace == str(tmp_path)
        capabilities = ServiceCapabilities.model_validate(client.get('/api/v1/capabilities', headers=headers).json())
        assert capabilities.asset_import and (not capabilities.asset_publish)
        identity = uuid4()
        for path, auth, expected in [('/api/v1/health', {}, 401), ('/missing', headers, 404)]:
            response = client.get(path, headers=auth | {'X-Request-ID': str(identity)})
            assert response.status_code == expected
            error = ErrorEnvelope.model_validate_json(response.content)
            assert error.request_id == identity
            assert response.headers['X-Request-ID'] == str(identity)
