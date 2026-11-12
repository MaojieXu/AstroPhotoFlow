from fastmcp import FastMCP
from fastmcp.dependencies import Depends

from astrophotoflow.client import AssetClient
from astrophotoflow.contracts.canvas import CanvasAddRequest, CanvasAddResult, CanvasGraphRequest, CanvasPageOut
from astrophotoflow.interfaces.mcp.composition import tool_namespace
from astrophotoflow.interfaces.mcp.errors import service_errors
from astrophotoflow.interfaces.mcp.lifespan import service_client


def build_server() -> FastMCP:
    mcp = tool_namespace("canvas")

    @mcp.tool(
        name="get",
        description="Read the actual connected canvas through its native page without changing its content.\n通过原生页面读取实际在线画布，不修改内容。\n关键词: 画布 内容 目标 修改 图 节点 读取 查询",
    )
    @service_errors
    def get_canvas(page_id: str, *, client: AssetClient = Depends(service_client)) -> CanvasAddResult:
        """Read the actual connected canvas through its native page without changing its content."""
        return client.get_canvas(page_id)

    @mcp.tool(
        name="edit",
        description="Apply one user-requested add_node, set_parameter, connect or delete_node operation to the exact active canvas using its current target IDs and content_token. Deletion removes the node and attached links through native undo support, retaining source assets. Stop on target/content changes; query unknown operation IDs instead of replaying. Does not execute the graph.\n按用户明确要求，使用准确的当前目标 ID 和 content_token 执行一次 add_node、set_parameter、connect 或 delete_node。删除通过原生撤销机制移除节点及连线，保留源素材。目标或内容变化即停止；未知 operation_id 先查询，不重放。本工具不运行图。\n关键词: 画布 内容 目标 修改 图 节点 ",
    )
    @service_errors
    def edit_canvas(body: CanvasGraphRequest, *, client: AssetClient = Depends(service_client)) -> CanvasAddResult:
        """Apply one user-requested add_node, set_parameter, connect or delete_node operation to the exact active canvas using its current target IDs and content_token. Deletion removes the node and attached links through native undo support, retaining source assets. Stop on target/content changes; query unknown operation IDs instead of replaying. Does not execute the graph."""
        return client.edit_canvas(body)

    @mcp.tool(
        name="pages",
        description="List connected active canvases and their current target IDs and content_token. Only edit the canvas requested by the user; never follow another graph automatically.\n列出当前在线画布及其目标 ID、content_token。只编辑用户指定的画布，不自动跟随其他图。\n关键词: 画布 内容 目标 修改 图 节点 ",
    )
    @service_errors
    def list_canvas_pages(*, client: AssetClient = Depends(service_client)) -> list[CanvasPageOut]:
        """List connected active canvases and their current target IDs and content_token. Only edit the canvas requested by the user; never follow another graph automatically."""
        return client.list_canvas_pages()

    @mcp.tool(
        name="add_data",
        description="Add a user-requested fixed asset/group to the exact active canvas using current target IDs and content_token. Stop on target/content changes; query unknown results with the same operation_id, never automatic replay.\n按用户明确要求，使用准确目标 ID 和 content_token 将固定素材或组加入活动画布。目标或内容变化即停止；未知结果查询同一 operation_id，不自动重放。\n关键词: 画布 内容 目标 修改 图 节点 ",
    )
    @service_errors
    def add_canvas_data(body: CanvasAddRequest, *, client: AssetClient = Depends(service_client)) -> CanvasAddResult:
        """Add a user-requested fixed asset/group to the exact active canvas using current target IDs and content_token. Stop on target/content changes; query unknown results with the same operation_id, never automatic replay."""
        return client.add_canvas_data(body)

    return mcp
