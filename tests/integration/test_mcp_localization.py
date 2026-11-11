import pytest
import httpx
from pathlib import Path
from uuid import UUID

@pytest.mark.asyncio
async def test_tool_identity_and_schema_are_stable_with_bilingual_descriptions():
    from astrophotoflow.interfaces.mcp.server import build_tool_catalog
    first = await build_tool_catalog().list_tools()
    second = await build_tool_catalog().list_tools()
    assert {t.name: t.parameters for t in first} == {t.name: t.parameters for t in second}
    selected = next((t for t in first if t.name == 'data_assets_get'))
    assert 'Read a shared asset' in selected.description and '素材' in selected.description

def test_software_details_decode_json_paths_and_node_ids(tmp_path, monkeypatch):
    from astrophotoflow.client import AssetClient
    client = AssetClient.__new__(AssetClient)
    identity = '169de083-7f81-4cde-a329-5541ecacf463'
    payload = {'package': {'package_id': 'siril', 'name': 'Siril', 'available_versions': ['1.4.4'], 'installed_version': '1.4.4', 'install_path': str(tmp_path / 'app'), 'package_token': 'fixed', 'availability': 'ready', 'operation_state': 'completed', 'node_definition_ids': [identity]}, 'current_action': None, 'result': None}
    client.client = httpx.Client(base_url='http://isolated-test/api/v1', transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)))
    with client:
        details = client.get_software_package('siril')
    assert details.package.install_path == Path(tmp_path / 'app')
    assert details.package.node_definition_ids == [UUID(identity)]
