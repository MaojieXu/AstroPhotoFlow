"""Protocol coverage for the public two-domain surface; not a compatibility API."""
import json
from base64 import b64decode

import pytest
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from astrophotoflow.interfaces.mcp import server
from astrophotoflow.interfaces.mcp.registry import DATA_NAMES, CANVAS_NAMES
from astrophotoflow.interfaces.mcp.tools import imports, library, organization, canvas


def tools(locale='en'):
    return {tool.name: tool for tool in server.create_server(locale)._tool_manager.list_tools()}


def test_only_domain_schemas_are_advertised_and_leaf_contracts_stay_deferred():
    advertised = tools()
    assert set(advertised) == {'data_management', 'node_canvas_management'}
    for tool in advertised.values():
        assert set(tool.parameters['properties']) == {'operation', 'arguments'}
        assert '$defs' not in tool.parameters
    # Compare equivalent flat registration without executing a service or touching source files.
    flat = MCPServer('baseline')
    for module in (imports, library, organization, canvas):
        module.register(flat, lambda fn: None)
    original = [tool for tool in flat._tool_manager.list_tools() if tool.name != 'get_nodes']
    assert len(original) == 69
    assert len(json.dumps([tool.parameters for tool in advertised.values()])) < len(json.dumps([tool.parameters for tool in original])) / 10
    data = advertised['data_management'].fn('describe', {'operations': list(DATA_NAMES.values())[:10]}).structured_content
    assert data['items'][0]['input_schema']['type'] == 'object'


def test_every_preexisting_operation_is_registered_under_exactly_one_domain():
    advertised = tools()
    for domain, mapping in (('data_management', DATA_NAMES), ('node_canvas_management', CANVAS_NAMES)):
        for operation in mapping.values():
            described = advertised[domain].fn('describe', {'operations': [operation]}).structured_content
            assert described['items'][0]['operation'] == operation
    assert len(set(DATA_NAMES.values())) == len(DATA_NAMES)
    assert not set(DATA_NAMES.values()) & set(CANVAS_NAMES.values())


def test_known_operation_calls_once_without_discovery_and_preserves_manual_null_zero(monkeypatch):
    captured = []
    class Client:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def update_asset(self, identity, body):
            captured.append((identity, body.model_dump(exclude_unset=True)))
            return {'id': identity}
    monkeypatch.setattr(server, 'AssetClient', Client)
    response = tools()['data_management'].fn('assets.update', {
        'asset_id': 'asset', 'body': {'base_revision': 2, 'notes': None, 'parameters': {'gain': 0}}})
    assert response.structured_content == {'id': 'asset'}
    assert captured == [('asset', {'base_revision': 2, 'notes': None, 'parameters': {'gain': 0}})]


def test_exact_discovery_returns_schema_and_candidates_are_bounded():
    tool = tools()['data_management']
    exact = tool.fn('discover', {'query': 'projects.add_dataset'}).structured_content
    assert exact['definition']['operation'] == 'projects.add_dataset'
    assert 'body' in exact['definition']['input_schema']['properties']
    page = tool.fn('discover', {'group': 'projects', 'limit': 3, 'offset': 3}).structured_content
    assert len(page['items']) == 3 and page['total'] == 13
    assert all(item['operation'].startswith('projects.') for item in page['items'])
    with pytest.raises(ToolError): tool.fn('discover', {'limit': 11})
    with pytest.raises(ToolError): tool.fn('describe', {'operations': ['does.not.exist']})
    with pytest.raises(ToolError): tool.fn('projects.get', {'unknown': 'value'})
    with pytest.raises(ToolError): tool.fn('get_project', {'project_id': 'value'})


def test_domain_output_preserves_native_image_content(monkeypatch):
    class Client:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read_display_preview(self, *args): return b'jpeg bytes'
    monkeypatch.setattr(server, 'AssetClient', Client)
    response = tools()['data_management'].fn('previews.read', {'asset_id': 'asset', 'version_id': 'fixed'})
    assert response.structured_content is None
    assert response.content[0].type == 'image'
    assert b64decode(response.content[0].data) == b'jpeg bytes'


def test_node_search_returns_short_page_and_batch_details_share_one_client(monkeypatch):
    calls = []
    class Client:
        def __enter__(self): calls.append('open'); return self
        def __exit__(self, *args): pass
        def list_nodes(self, query):
            return [{'node': {'definition': {'definition_id': str(i), 'name': 'Node', 'description': 'Description', 'parameters': ['large']},
                              'content_token': 'token'}, 'available': True, 'help': 'large help', 'examples': ['large']}
                    for i in range(25)]
        def get_node(self, identity): return {'id': identity, 'parameters': ['full']}
    monkeypatch.setattr(server, 'AssetClient', Client)
    tool = tools()['node_canvas_management']
    response = tool.fn('nodes.search', {'limit': 2, 'offset': 1}).structured_content
    assert response['total'] == 25 and len(response['items']) == 2
    assert all('parameters' not in item and 'help' not in item for item in response['items'])
    calls.clear()
    response = tool.fn('nodes.get_many', {'definition_ids': ['first', 'second']}).structured_content
    assert len(response['items']) == 2 and calls == ['open']
