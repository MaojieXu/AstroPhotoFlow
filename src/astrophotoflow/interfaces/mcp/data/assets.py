from fastmcp import FastMCP
from fastmcp.dependencies import Depends

from astrophotoflow.client import AssetClient
from astrophotoflow.contracts.assets import (
    AssetContentAccept,
    AssetContentObservation,
    AssetOut,
    AssetPage,
    AssetPatch,
    AssetQuery,
    AssetVersionOut,
    AssetVersionPage,
)
from astrophotoflow.contracts.inputs import CanvasDataOut, CanvasDataRequest
from astrophotoflow.contracts.metadata import AssetParametersPatch
from astrophotoflow.interfaces.mcp.composition import tool_namespace
from astrophotoflow.interfaces.mcp.errors import service_errors
from astrophotoflow.interfaces.mcp.lifespan import service_client


def build_server() -> FastMCP:
    mcp = tool_namespace("assets")

    @mcp.tool(
        name="prepare_canvas_data",
        description="Prepare a fixed scientific reference for a single asset or ordered group; this does not apply it to a canvas.\n为单件素材或有序组准备固定科学引用；本工具不会将其加入画布。\n关键词: 素材 照片 版本 科学 输入 准备",
    )
    @service_errors
    def prepare_canvas_data(body: CanvasDataRequest, *, client: AssetClient = Depends(service_client)) -> CanvasDataOut:
        """Prepare a fixed scientific reference for a single asset or ordered group; this does not apply it to a canvas."""
        return client.prepare_canvas_data(body)

    @mcp.tool(
        name="list",
        description="Page through shared assets, optionally filtering names, status, role or frame use.\n分页读取共享素材，可按名称、状态、角色或帧用途筛选。\n关键词: 素材 照片 版本 科学 输入 列表 分页 查询",
    )
    @service_errors
    def list_assets(query: AssetQuery | None = None, *, client: AssetClient = Depends(service_client)) -> AssetPage:
        return client.list_assets(query)

    @mcp.tool(
        name="get",
        description="Read a shared asset and its revision, classification, current parameters and original readiness.\n读取素材及其 revision、分类、当前参数和原件就绪状态。\n关键词: 素材 照片 版本 科学 输入 读取 查询",
    )
    @service_errors
    def get_asset(asset_id: str, *, client: AssetClient = Depends(service_client)) -> AssetOut:
        """Read a shared asset and its revision, classification, current parameters and original readiness."""
        return client.get_asset(asset_id)

    @mcp.tool(
        name="update",
        description="Patch asset metadata, classification or parameters at base_revision. Omitted fields remain; explicit null clears; zero is retained.\n在 base_revision 上更新素材资料、分类或参数。省略字段保持原值，显式 null 清空，零值保留。\n关键词: 素材 照片 版本 科学 输入 修改 更新",
    )
    @service_errors
    def update_asset(asset_id: str, body: AssetPatch, *, client: AssetClient = Depends(service_client)) -> AssetOut:
        """Patch asset metadata, classification or parameters at base_revision. Omitted fields remain; explicit null clears; zero is retained."""
        return client.update_asset(asset_id, body)

    @mcp.tool(
        name="update_parameters",
        description="Patch supplied asset parameters at the current revision. Omitted fields remain, null clears and zero is valid.\n在当前 revision 上更新提供的素材参数。省略保持原值，null 清空，零是有效值。\n关键词: 素材 照片 版本 科学 输入 修改 更新",
    )
    @service_errors
    def update_asset_parameters(
        asset_id: str, base_revision: int, parameters: AssetParametersPatch, *, client: AssetClient = Depends(service_client)
    ) -> AssetOut:
        """Patch supplied asset parameters at the current revision. Omitted fields remain, null clears and zero is valid."""
        return client.update_asset_parameters(asset_id, base_revision, parameters)

    @mcp.tool(
        name="list_versions",
        description="List fixed original asset versions.\n列出原件的固定版本。\n关键词: 素材 照片 版本 科学 输入 列表 分页 查询",
    )
    @service_errors
    def list_asset_versions(
        asset_id: str, limit: int = 50, offset: int = 0, *, client: AssetClient = Depends(service_client)
    ) -> AssetVersionPage:
        """List fixed original asset versions."""
        return client.list_asset_versions(asset_id, limit, offset)

    @mcp.tool(
        name="get_version",
        description="Read a fixed original version and its immutable intake facts.\n读取固定原件版本和不可变的受理事实。\n关键词: 素材 照片 版本 科学 输入 读取 查询",
    )
    @service_errors
    def get_asset_version(asset_id: str, version_id: str, *, client: AssetClient = Depends(service_client)) -> AssetVersionOut:
        """Read a fixed original version and its immutable intake facts."""
        return client.get_asset_version(asset_id, version_id)

    @mcp.tool(
        name="observe_content",
        description="Observe original-file content against its fixed version without accepting changes. 素材 原件 文件 内容 检查 哈希 变化",
    )
    @service_errors
    def observe_content(asset_id: str, *, client: AssetClient = Depends(service_client)) -> AssetContentObservation:
        return client.observe_asset_content(asset_id)

    @mcp.tool(
        name="accept_content",
        description="Accept only explicitly confirmed original content at the observed hash and revision; query unknown results rather than replay. 素材 原件 内容 接纳 确认 版本 修订",
    )
    @service_errors
    def accept_content(asset_id: str, body: AssetContentAccept, *, client: AssetClient = Depends(service_client)) -> AssetOut:
        return client.accept_asset_content(asset_id, body)

    return mcp
