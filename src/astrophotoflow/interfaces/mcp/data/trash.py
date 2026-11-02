from fastmcp import FastMCP
from fastmcp.dependencies import Depends

from astrophotoflow.client import AssetClient
from astrophotoflow.contracts.trash import (
    LibraryEntriesRemove,
    LibraryEntriesRemoveOut,
    LibraryTrashDelete,
    LibraryTrashDeleteOut,
    LibraryTrashPage,
    LibraryTrashPreviewOut,
    LibraryTrashRestoreOut,
    LibraryTrashSelection,
)
from astrophotoflow.interfaces.mcp.composition import tool_namespace
from astrophotoflow.interfaces.mcp.errors import service_errors
from astrophotoflow.interfaces.mcp.lifespan import service_client


def build_server() -> FastMCP:
    mcp = tool_namespace("trash")

    @mcp.tool(
        name="remove",
        description="Move selected library entries to reversible trash using their current revisions and version IDs.\n使用当前 revision 和版本 ID 将所选素材库条目移入可恢复的回收站。\n关键词: 回收站 清理 删除 恢复 确认 移除 删除",
    )
    @service_errors
    def remove_library_items(body: LibraryEntriesRemove, *, client: AssetClient = Depends(service_client)) -> LibraryEntriesRemoveOut:
        """Move selected library entries to reversible trash using their current revisions and version IDs."""
        return client.remove_library_items(body)

    @mcp.tool(
        name="list",
        description="List removed entries and partial or failed cleanup outcomes. Use returned identities for restore/delete preview.\n读取已移除条目及部分成功／失败的清理结果。恢复或删除预览使用返回的准确身份。\n关键词: 回收站 清理 删除 恢复 确认 列表 分页 查询",
    )
    @service_errors
    def list_trash(
        limit: int = 50, offset: int = 0, group_id: str | None = None, *, client: AssetClient = Depends(service_client)
    ) -> LibraryTrashPage:
        """List removed entries and partial or failed cleanup outcomes. Use returned identities for restore/delete preview."""
        return client.list_trash(limit, offset, group_id)

    @mcp.tool(
        name="restore",
        description="Restore the selected trash records without deleting originals.\n恢复所选回收站记录，不删除原件。\n关键词: 回收站 清理 删除 恢复 确认 恢复",
    )
    @service_errors
    def restore_trash(body: LibraryTrashSelection, *, client: AssetClient = Depends(service_client)) -> LibraryTrashRestoreOut:
        """Restore the selected trash records without deleting originals."""
        return client.restore_trash(body)

    @mcp.tool(
        name="preview_delete",
        description="Preview permanent cleanup: inspect references, tasks, managed files and fingerprint before explicit deletion.\n预览永久清理：检查引用、任务、托管文件及范围指纹，实际删除仍需明确授权。\n关键词: 回收站 清理 删除 恢复 确认 预检 只读",
    )
    @service_errors
    def preview_trash_delete(body: LibraryTrashSelection, *, client: AssetClient = Depends(service_client)) -> LibraryTrashPreviewOut:
        """Preview permanent cleanup: inspect references, tasks, managed files and fingerprint before explicit deletion."""
        return client.preview_trash_delete(body)

    @mcp.tool(
        name="delete",
        description="Permanently clean selected trash using the current preview fingerprint only when the user authorized this cleanup. Historical references remain protected; re-read trash and preview after partial failures.\n仅在用户授权本次清理后，使用最新预览指纹永久清理所选条目。历史引用仍受保护；部分失败后重新读取回收站并预览。\n关键词: 回收站 清理 删除 恢复 确认 删除 确认",
    )
    @service_errors
    def delete_trash(body: LibraryTrashDelete, *, client: AssetClient = Depends(service_client)) -> LibraryTrashDeleteOut:
        """Permanently clean selected trash using the current preview fingerprint only when the user authorized this cleanup. Historical references remain protected; re-read trash and preview after partial failures."""
        return client.delete_trash(body)

    return mcp
