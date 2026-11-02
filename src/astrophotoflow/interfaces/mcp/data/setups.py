from fastmcp import FastMCP
from fastmcp.dependencies import Depends

from astrophotoflow.client import AssetClient
from astrophotoflow.contracts.setups import (
    EquipmentSetupCreate,
    EquipmentSetupOut,
    EquipmentSetupPage,
    EquipmentSetupPatch,
    EquipmentSetupQuery,
)
from astrophotoflow.interfaces.mcp.composition import tool_namespace
from astrophotoflow.interfaces.mcp.errors import service_errors
from astrophotoflow.interfaces.mcp.lifespan import service_client


def build_server() -> FastMCP:
    mcp = tool_namespace("setups")

    @mcp.tool(
        name="list", description="Page through equipment setups.\n分页读取设备组合。\n关键词: 设备 器材 相机 光学 滤镜 列表 分页 查询"
    )
    @service_errors
    def list_equipment_setups(query: EquipmentSetupQuery | None = None, *, client: AssetClient = Depends(service_client)) -> EquipmentSetupPage:
        return client.list_equipment_setups(query)

    @mcp.tool(
        name="create",
        description="Create a setup with registered references or inline equipment snapshots. Inline equipment is not auto-registered.\n使用已登记设备引用或内嵌设备快照创建组合；内嵌设备不会自动登记到设备库。\n关键词: 设备 器材 相机 光学 滤镜 创建",
    )
    @service_errors
    def create_equipment_setup(body: EquipmentSetupCreate, *, client: AssetClient = Depends(service_client)) -> EquipmentSetupOut:
        """Create a setup with registered references or inline equipment snapshots. Inline equipment is not auto-registered."""
        return client.create_equipment_setup(body)

    @mcp.tool(name="get", description="Read an equipment setup.\n读取设备组合。\n关键词: 设备 器材 相机 光学 滤镜 读取 查询")
    @service_errors
    def get_equipment_setup(setup_id: str, *, client: AssetClient = Depends(service_client)) -> EquipmentSetupOut:
        """Read an equipment setup."""
        return client.get_equipment_setup(setup_id)

    @mcp.tool(
        name="update",
        description="Patch or archive a setup without modifying registered equipment.\n更新或归档组合，不修改已登记设备。\n关键词: 设备 器材 相机 光学 滤镜 修改 更新",
    )
    @service_errors
    def update_equipment_setup(
        setup_id: str, body: EquipmentSetupPatch, *, client: AssetClient = Depends(service_client)
    ) -> EquipmentSetupOut:
        """Patch or archive a setup without modifying registered equipment."""
        return client.update_equipment_setup(setup_id, body)

    return mcp
