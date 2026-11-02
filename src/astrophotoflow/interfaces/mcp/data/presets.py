from fastmcp import FastMCP
from fastmcp.dependencies import Depends

from astrophotoflow.client import AssetClient
from astrophotoflow.contracts.setups import CapturePresetCreate, CapturePresetOut, CapturePresetPage, CapturePresetPatch, CapturePresetQuery
from astrophotoflow.interfaces.mcp.composition import tool_namespace
from astrophotoflow.interfaces.mcp.errors import service_errors
from astrophotoflow.interfaces.mcp.lifespan import service_client


def build_server() -> FastMCP:
    mcp = tool_namespace("presets")

    @mcp.tool(
        name="list",
        description="Page through capture presets, optionally restricted to their owning setup.\n分页读取拍摄预设，可限定所属设备组合。\n关键词: 设备 器材 相机 光学 滤镜 列表 分页 查询",
    )
    @service_errors
    def list_capture_presets(query: CapturePresetQuery | None = None, *, client: AssetClient = Depends(service_client)) -> CapturePresetPage:
        return client.list_capture_presets(query)

    @mcp.tool(
        name="create",
        description="Create a capture preset owned by a setup; omitted defaults stay unknown.\n为设备组合创建拍摄预设，省略的默认值保留未知。\n关键词: 设备 器材 相机 光学 滤镜 创建",
    )
    @service_errors
    def create_capture_preset(
        setup_id: str, body: CapturePresetCreate, *, client: AssetClient = Depends(service_client)
    ) -> CapturePresetOut:
        """Create a capture preset owned by a setup; omitted defaults stay unknown."""
        return client.create_capture_preset(setup_id, body)

    @mcp.tool(
        name="get",
        description="Read a capture preset and its owning setup.\n读取拍摄预设及其所属组合。\n关键词: 设备 器材 相机 光学 滤镜 读取 查询",
    )
    @service_errors
    def get_capture_preset(preset_id: str, *, client: AssetClient = Depends(service_client)) -> CapturePresetOut:
        """Read a capture preset and its owning setup."""
        return client.get_capture_preset(preset_id)

    @mcp.tool(
        name="update",
        description="Patch or archive a preset. Already accepted import snapshots remain immutable.\n更新或归档拍摄预设；已受理导入的预设快照保持不变。\n关键词: 设备 器材 相机 光学 滤镜 修改 更新",
    )
    @service_errors
    def update_capture_preset(
        preset_id: str, body: CapturePresetPatch, *, client: AssetClient = Depends(service_client)
    ) -> CapturePresetOut:
        """Patch or archive a preset. Already accepted import snapshots remain immutable."""
        return client.update_capture_preset(preset_id, body)

    return mcp
