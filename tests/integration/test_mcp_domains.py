"""Business discovery stays bounded; full node details remain separate reads."""
from uuid import UUID
import pytest
from fastmcp import Client
from astrophotoflow.contracts.nodes import NodeCapability, NodeDefinition, SavedDefinition
from astrophotoflow.interfaces.mcp import lifespan
from astrophotoflow.interfaces.mcp.server import build_tool_catalog

def capability(index: int) -> NodeCapability:
    identity = UUID(int=index + 1)
    definition = NodeDefinition(definition_id=identity, source='custom', name=f'Node {index}', description='Description', inputs=[], outputs=[], parameters=[], execution={'package_id': 'siril', 'operation_id': 'stats', 'inputs': {}, 'parameters': {}, 'outputs': {}})
    saved = SavedDefinition(definition=definition, content_token='fixed', native_type=f'APF_fixture_{index}')
    return NodeCapability(node=saved, operation=None, available=True, reason=None, preview=None, help='Detailed help', examples=[], display={'en': {'name': f'Node {index}', 'description': 'Description', 'help': 'English help'}, 'zh': {'name': f'节点 {index}', 'description': '说明', 'help': '中文帮助'}})

@pytest.mark.asyncio
async def test_node_search_returns_short_page_and_batch_details_share_one_client(monkeypatch):
    values = [capability(i) for i in range(25)]
    before = [value.model_dump(mode='json') for value in values]
    calls = []

    class Service:

        def __enter__(self):
            calls.append('open')
            return self

        def __exit__(self, *args):
            calls.append('close')

        def list_nodes(self, query):
            return values

        def get_node(self, identity):
            calls.append(identity)
            return next((value for value in values if str(value.node.definition.definition_id) == identity))
    monkeypatch.setattr(lifespan, 'AssetClient', Service)
    async with Client(build_tool_catalog()) as client:
        result = await client.call_tool('graph_nodes_search', {'limit': 2, 'offset': 1, 'locale': 'zh'})
        page = result.structured_content
        assert page['total'] == 25 and len(page['items']) == 2
        assert page['items'][0]['name'] == '节点 1'
        assert all(('parameters' not in row and 'help' not in row for row in page['items']))
        identities = [str(value.node.definition.definition_id) for value in values[:2]]
        result = await client.call_tool('graph_nodes_get_many', {'definition_ids': identities})
        assert len(result.structured_content['items']) == 2
        assert calls == ['open', *identities]
    assert calls[-1] == 'close'
    assert [value.model_dump(mode='json') for value in values] == before
