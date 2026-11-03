import json

import pytest
from fastmcp import Client

from astrophotoflow.contracts.image_management import ImagePage
from astrophotoflow.interfaces.client.errors import ServiceApiError
from astrophotoflow.interfaces.mcp import lifespan
from astrophotoflow.interfaces.mcp.server import build_tool_catalog, create_server


class Service:
    def __init__(self):
        self.opened = 0
        self.closed = 0
        self.calls = []

    def __enter__(self):
        self.opened += 1
        return self

    def __exit__(self, *args):
        self.closed += 1

    def image_assets_search(self, **values):
        self.calls.append(("list", values))
        return ImagePage(items=[], total=0, limit=50, offset=0)

    def image_assets_update(self, asset_id, expected_revision, changes):
        self.calls.append(("update", str(asset_id), {"expected_revision": expected_revision,
            "changes": changes.model_dump(mode="json", exclude_unset=True)}))
        raise ServiceApiError(409, "REVISION_CONFLICT", "changed", "request-123", [{"path": "expected_revision", "message": "stale"}])

    def read_display_preview(self, *args):
        self.calls.append(("image", args))
        return b"synthetic-jpeg"


@pytest.mark.asyncio
async def test_full_catalog_builds_offline_and_excludes_injected_dependencies(monkeypatch):
    def forbidden():
        pytest.fail("catalog construction opened a workspace client")
    monkeypatch.setattr(lifespan, "AssetClient", forbidden)
    tools = await build_tool_catalog().list_tools()
    names = {tool.name for tool in tools}
    assert len(names) == len(tools)
    assert {"data_assets_get", "data_library_search", "data_setups_create", "graph_canvas_edit", "software_calls_get_call", "software_packages_install"} <= names
    assert not {"data_management", "node_canvas_management"} & names
    assert all("client" not in tool.parameters.get("properties", {}) for tool in tools)


@pytest.mark.asyncio
async def test_one_shared_client_lifetime_and_mcp_error_result(monkeypatch):
    service = Service()
    monkeypatch.setattr(lifespan, "AssetClient", lambda: service)
    async with Client(build_tool_catalog()) as client:
        first = await client.call_tool("data_assets_search", {})
        assert first.structured_content["total"] == 0
        await client.call_tool("data_assets_search", {"query": {"offset": 0}})
        result = await client.call_tool("data_assets_update", {"asset_id": "00000000-0000-4000-8000-000000000001", "expected_revision": 2, "changes": {"notes": None, "parameters": {"gain": 0}}}, raise_on_error=False)
        assert result.is_error
        text = " ".join(block.text for block in result.content if hasattr(block, "text"))
        assert "REVISION_CONFLICT" in text and "request-123" in text and "expected_revision" in text
    assert service.opened == service.closed == 1
    assert service.calls[-1][2] == {"expected_revision": 2, "changes": {"notes": None, "parameters": {"gain": 0}}}


@pytest.mark.asyncio
async def test_search_view_keeps_exact_calls_and_returns_bounded_definitions(monkeypatch):
    service = Service()
    monkeypatch.setattr(lifespan, "AssetClient", lambda: service)
    async with Client(create_server()) as client:
        assert {tool.name for tool in await client.list_tools()} == {"search_tools", "call_tool"}
        for query in ("asset versions", "读取 素材"):
            found = await client.call_tool("search_tools", {"query": query})
            payload = json.loads(found.content[0].text)
            assert 1 <= len(payload) <= 10
            assert all("inputSchema" in row for row in payload)
        direct = await client.call_tool("data_assets_search", {})
        assert direct.structured_content["total"] == 0
        image = await client.call_tool("data_media_read", {"asset_id": "asset", "version_id": "version"})
        assert any(block.type == "image" and block.mime_type == "image/jpeg" for block in image.content)
