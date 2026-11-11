from astrophotoflow.contracts.library import (
    LibraryDirectoryOpened, LibraryEntryType, LibraryLocationOut,
    LibraryOrganizeRequest, LibraryOrganizeExecute, LibraryOrganizePlan, LibraryOrganizeReceipt,
)
from astrophotoflow.contracts.common import UuidInput
from astrophotoflow.contracts.image_management import Revision
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

    @mcp.tool(name='location', description='Read actual library file paths, calibration facts and dataset mirror status. 素材库 实际位置 校准状态 说明文件')
    @service_errors
    def location(entry_type: LibraryEntryType, entry_id: UuidInput, *, client: AssetClient = Depends(service_client)) -> LibraryLocationOut:
        return client.library_location(entry_type, str(entry_id))

    @mcp.tool(name='rebuild_manifest', description='Rebuild dataset.json from current SQLite facts at the submitted revision. 数据集 重建 JSON 当前资料')
    @service_errors
    def rebuild_manifest(dataset_id: UuidInput, expected_revision: Revision, *, client: AssetClient = Depends(service_client)) -> LibraryLocationOut:
        return client.rebuild_dataset_manifest(str(dataset_id), expected_revision)

    @mcp.tool(name='open_directory', description='Open the registered directory in Windows Explorer. 素材库 打开目录')
    @service_errors
    def open_directory(entry_type: LibraryEntryType, entry_id: UuidInput, *, client: AssetClient = Depends(service_client)) -> LibraryDirectoryOpened:
        return client.open_library_directory(entry_type, str(entry_id))

    @mcp.tool(name='plan_organization', description='Preflight current directory moves, original hashes, conflicts and activity. 素材库 整理目录 预检 占用 冲突')
    @service_errors
    def plan_organization(body: LibraryOrganizeRequest, *, client: AssetClient = Depends(service_client)) -> LibraryOrganizePlan:
        return client.plan_library_organization(body)

    @mcp.tool(name='organize', description='Execute a reviewed directory plan at revision. Query the request receipt after an uncertain response. 素材库 整理目录 实际回执 部分失败')
    @service_errors
    def organize(body: LibraryOrganizeExecute, *, client: AssetClient = Depends(service_client)) -> LibraryOrganizeReceipt:
        return client.organize_library(body)

    @mcp.tool(name='organization', description='Read actual per-file movement and cleanup status without rerunning. 素材库 整理回执 查询')
    @service_errors
    def organization(request_id: UuidInput, *, client: AssetClient = Depends(service_client)) -> LibraryOrganizeReceipt:
        return client.get_library_organization(str(request_id))

    return mcp
