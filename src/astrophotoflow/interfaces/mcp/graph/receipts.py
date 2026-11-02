from fastmcp import FastMCP
from fastmcp.dependencies import Depends

from astrophotoflow.client import AssetClient
from astrophotoflow.contracts.canvas import CanvasAddResult
from astrophotoflow.interfaces.mcp.composition import tool_namespace
from astrophotoflow.interfaces.mcp.errors import service_errors
from astrophotoflow.interfaces.mcp.lifespan import service_client


def build_server() -> FastMCP:
    mcp = tool_namespace("receipts")

    @mcp.tool(
        name="get",
        description="Read a canvas application receipt from this engine session; unknown is not proof that no node was added.\n读取本引擎会话的画布应用回执；unknown 不证明没有添加节点。\n关键词: 回执 未知 查询 读取 查询",
    )
    @service_errors
    def get_canvas_request(operation_id: str, *, client: AssetClient = Depends(service_client)) -> CanvasAddResult:
        """Read a canvas application receipt from this engine session; unknown is not proof that no node was added."""
        return client.get_canvas_request(operation_id)

    return mcp
