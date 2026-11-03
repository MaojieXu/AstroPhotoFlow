from fastmcp import FastMCP
from fastmcp.dependencies import Depends

from astrophotoflow.client import AssetClient
from astrophotoflow.contracts.trash import EquipmentDelete, ManagementTrashDeleteOut, ManagementTrashPreviewOut
from astrophotoflow.interfaces.mcp.composition import tool_namespace
from astrophotoflow.interfaces.mcp.data.equipment import READ_ONLY, UPDATE
from astrophotoflow.interfaces.mcp.data.equipment_inputs import ConfigurationTargets
from astrophotoflow.interfaces.mcp.errors import service_errors
from astrophotoflow.interfaces.mcp.lifespan import service_client


def build_server() -> FastMCP:
    mcp = tool_namespace("equipment_management")

    @mcp.tool(name="preview_delete", annotations=READ_ONLY, description="Preview deletion of equipment and equipment setups, selected in targets.equipment/setups with exact id and revision. Return all dependency effects and the current preview_fingerprint. Does not delete anything. 删除 设备 设备组合 setup 影响 预检 确认指纹 批量删除。")
    @service_errors
    def preview_delete(targets: ConfigurationTargets, *, client: AssetClient = Depends(service_client)) -> ManagementTrashPreviewOut:
        return client.preview_equipment_delete(targets.to_selection())

    @mcp.tool(name="delete", annotations=UPDATE, description="Delete the exact user-authorized equipment/setup targets using their current revisions and matching preview_fingerprint from data_equipment_management_preview_delete. Direct deletion, not archival; historical snapshots and original files remain. Re-preview changed impacts; unknown results must be reconciled, not replayed. 删除设备 删除设备组合 批量删除 确认指纹。")
    @service_errors
    def delete(targets: ConfigurationTargets, preview_fingerprint: str,
               *, client: AssetClient = Depends(service_client)) -> ManagementTrashDeleteOut:
        selection = targets.to_selection()
        return client.delete_equipment_entries(EquipmentDelete(items=selection.items, preview_fingerprint=preview_fingerprint))

    return mcp
