from fastmcp import FastMCP
from fastmcp.dependencies import Depends

from astrophotoflow.client import AssetClient
from astrophotoflow.contracts.assets import LibraryFilterOptions, LibraryItemPage, LibraryQuery
from astrophotoflow.interfaces.mcp.composition import tool_namespace
from astrophotoflow.interfaces.mcp.errors import service_errors
from astrophotoflow.interfaces.mcp.lifespan import service_client


def build_server() -> FastMCP:
    mcp = tool_namespace("library")

    @mcp.tool(
        name="search",
        description="List the library view containing logical datasets and independent assets.\n读取包含逻辑图像组与独立素材的素材库视图。\n关键词: 素材库 搜索 筛选 分页 ",
    )
    @service_errors
    def list_library_items(query: LibraryQuery | None = None, *, client: AssetClient = Depends(service_client)) -> LibraryItemPage:
        return client.list_library_items(query)

    @mcp.tool(
        name="filters",
        description="Read available library filtering values and ranges using the same visible scope. 素材库 筛选 选项 范围 相机 滤镜",
    )
    @service_errors
    def filters(*, client: AssetClient = Depends(service_client)) -> LibraryFilterOptions:
        return client.get_library_filter_options()

    return mcp
