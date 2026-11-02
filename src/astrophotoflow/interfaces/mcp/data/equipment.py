from fastmcp import FastMCP
from fastmcp.dependencies import Depends

from astrophotoflow.client import AssetClient
from astrophotoflow.contracts.equipment import EquipmentCreate, EquipmentOut, EquipmentPage, EquipmentPatch, EquipmentQuery
from astrophotoflow.contracts.trash import EquipmentDelete, EquipmentDeleteSelection, ManagementTrashDeleteOut, ManagementTrashPreviewOut
from astrophotoflow.interfaces.mcp.composition import tool_namespace
from astrophotoflow.interfaces.mcp.errors import service_errors
from astrophotoflow.interfaces.mcp.lifespan import service_client


def build_server() -> FastMCP:
    mcp = tool_namespace("equipment")

    @mcp.tool(
        name="list_items",
        description="Page through registered cameras, telescopes, optical systems, filters, mounts and accessories.\n分页读取已登记的相机、望远镜、成像系统、滤镜、赤道仪和配件。\n关键词: 设备 器材 相机 光学 滤镜 列表 分页 查询",
    )
    @service_errors
    def list_equipment(query: EquipmentQuery | None = None, *, client: AssetClient = Depends(service_client)) -> EquipmentPage:
        return client.list_equipment(query)

    @mcp.tool(
        name="create_item",
        description="Register equipment with the backend discriminated kind/specification schema.\n按服务端 kind 区分的规格契约登记设备。\n关键词: 设备 器材 相机 光学 滤镜 创建",
    )
    @service_errors
    def create_equipment(body: EquipmentCreate, *, client: AssetClient = Depends(service_client)) -> EquipmentOut:
        """Register equipment with the backend discriminated kind/specification schema."""
        return client.create_equipment(body)

    @mcp.tool(name="get_item", description="Read registered equipment.\n读取已登记设备。\n关键词: 设备 器材 相机 光学 滤镜 读取 查询")
    @service_errors
    def get_equipment(equipment_id: str, *, client: AssetClient = Depends(service_client)) -> EquipmentOut:
        """Read registered equipment."""
        return client.get_equipment(equipment_id)

    @mcp.tool(
        name="update_item",
        description="Patch or archive registered equipment at base_revision. Include its kind.\n在 base_revision 上更新或归档已登记设备；必须包含原 kind。\n关键词: 设备 器材 相机 光学 滤镜 修改 更新",
    )
    @service_errors
    def update_equipment(equipment_id: str, body: EquipmentPatch, *, client: AssetClient = Depends(service_client)) -> EquipmentOut:
        """Patch or archive registered equipment at base_revision. Include its kind."""
        return client.update_equipment(equipment_id, body)

    @mcp.tool(
        name="preview_delete",
        description="Read exact equipment/setup/preset deletion effects and confirmation fingerprint. 设备 组合 预设 删除 预检 影响 确认",
    )
    @service_errors
    def preview_delete(body: EquipmentDeleteSelection, *, client: AssetClient = Depends(service_client)) -> ManagementTrashPreviewOut:
        return client.preview_equipment_delete(body)

    @mcp.tool(
        name="delete",
        description="Delete only explicitly confirmed equipment entries with their current impact fingerprint; snapshots remain. 设备 删除 确认 指纹 快照",
    )
    @service_errors
    def delete(body: EquipmentDelete, *, client: AssetClient = Depends(service_client)) -> ManagementTrashDeleteOut:
        return client.delete_equipment_entries(body)

    return mcp
