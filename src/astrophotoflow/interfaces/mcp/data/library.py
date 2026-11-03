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
        description="List logical datasets and independent assets with batched effective Master calibration columns. exposure_summary is a read-only whole-group sum of subframe exposure_seconds, with known/unknown counts; pagination/filtering never changes that total. Do not add integration_seconds or Masters. Browsing performs no scientific calibration check.\n读取素材库、有效Master校准列和自动累计曝光，未知不按0处理。\n关键词: 素材库 搜索 筛选 分页 累计曝光 校准 ",
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
