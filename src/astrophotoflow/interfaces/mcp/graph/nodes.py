from typing import Annotated

from fastmcp import FastMCP
from fastmcp.dependencies import Depends
from pydantic import Field

from astrophotoflow.client import AssetClient
from astrophotoflow.contracts.common import UuidInput
from astrophotoflow.contracts.localization import Locale
from astrophotoflow.contracts.nodes import NodeCapabilities, NodeCapability, NodeCapabilitySummary, NodeSearchPage
from astrophotoflow.interfaces.mcp.composition import tool_namespace
from astrophotoflow.interfaces.mcp.errors import service_errors
from astrophotoflow.interfaces.mcp.lifespan import service_client


def build_server() -> FastMCP:
    mcp = tool_namespace("Nodes")

    @mcp.tool(
        name="search", description="Find short installed-node summaries; get full definitions before editing. 节点 目录 搜索 参数 定义 分页"
    )
    @service_errors
    def search_nodes(
        query: str | None = None,
        limit: Annotated[int, Field(ge=1, le=10)] = 10,
        offset: Annotated[int, Field(ge=0)] = 0,
        locale: Locale = "en",
        *,
        client: AssetClient = Depends(service_client),
    ) -> NodeSearchPage:
        values = client.list_nodes(query)
        items = []
        for value in values[offset : offset + limit]:
            definition = value.node.definition
            display = value.display.get(locale)
            items.append(
                NodeCapabilitySummary(
                    definition_id=definition.definition_id,
                    name=display.name if display else definition.name,
                    description=display.description if display else definition.description,
                    available=value.available,
                    reason=value.reason,
                    content_token=value.node.content_token,
                )
            )
        return NodeSearchPage(items=items, total=len(values), limit=limit, offset=offset)

    @mcp.tool(
        name="get",
        description="Read a node's full typed definition, ports, ranges, help and definition token. 节点 读取 详情 端口 参数 示例",
    )
    @service_errors
    def get_node(definition_id: UuidInput, *, client: AssetClient = Depends(service_client)) -> NodeCapability:
        return client.get_node(str(definition_id))

    @mcp.tool(name="get_many", description="Read up to ten exact full node definitions. 节点 批量 读取 定义")
    @service_errors
    def get_nodes(
        definition_ids: Annotated[list[UuidInput], Field(min_length=1, max_length=10)], *, client: AssetClient = Depends(service_client)
    ) -> NodeCapabilities:
        return NodeCapabilities(items=[client.get_node(str(identity)) for identity in definition_ids])

    return mcp
