import inspect
from pathlib import Path
from uuid import UUID

from astrophotoflow.interfaces.mcp.server import create_server


def test_tool_identity_and_schema_do_not_depend_on_display_language():
    english = create_server('en')._tool_manager.list_tools()
    chinese = create_server('zh')._tool_manager.list_tools()
    assert {tool.name for tool in english} == {tool.name for tool in chinese}
    by_name = {tool.name: tool for tool in chinese}
    for tool in english:
        translated = by_name[tool.name]
        assert tool.parameters == translated.parameters
        assert inspect.signature(tool.fn) == inspect.signature(translated.fn)
        assert tool.description != translated.description


def test_node_display_projection_does_not_modify_execution_definition():
    from astrophotoflow.interfaces.mcp.localization import node_display
    value = {'node': {'content_token': 'fixed', 'definition': {'name': 'User title'}},
             'help': 'legacy', 'display': {'en': {'help': 'English help'}, 'zh': {'help': '中文说明'}}}
    before = repr(value)
    assert node_display(value, 'zh')['help'] == '中文说明'
    assert node_display(value, 'en')['node'] == value['node']
    assert repr(value) == before
    assert node_display({'node': {}, 'display': {}}, 'zh') == {'node': {}, 'display': {}}


def test_software_details_decode_json_paths_and_node_ids(tmp_path, monkeypatch):
    from astrophotoflow.client import AssetClient
    client = AssetClient.__new__(AssetClient)
    identity = '169de083-7f81-4cde-a329-5541ecacf463'
    payload = {'package': {
        'package_id': 'siril', 'name': 'Siril', 'available_versions': ['1.4.4'], 'installed_version': '1.4.4',
        'install_path': str(tmp_path / 'app'), 'package_token': 'fixed', 'availability': 'ready',
        'operation_state': 'completed', 'node_definition_ids': [identity]
    }, 'current_action': None, 'result': None}
    monkeypatch.setattr(client, 'request', lambda *args, **kwargs: payload)
    details = client.get_software_package('siril')
    assert details.package.install_path == Path(tmp_path / 'app')
    assert details.package.node_definition_ids == [UUID(identity)]
