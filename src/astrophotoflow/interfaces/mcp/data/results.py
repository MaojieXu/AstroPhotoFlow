from fastmcp import FastMCP
from fastmcp.dependencies import Depends

from astrophotoflow.client import AssetClient
from astrophotoflow.contracts.data_nodes import DataNodeResult
from astrophotoflow.interfaces.mcp.composition import tool_namespace
from astrophotoflow.interfaces.mcp.errors import service_errors
from astrophotoflow.interfaces.mcp.lifespan import service_client


def build_server() -> FastMCP:
    mcp = tool_namespace("results")

    @mcp.tool(
        name="get",
        description="Inspect an actual completed Data node and its ordered full-resolution members without executing the graph.\n读取Data节点实际运行结果及有序完整成员；不执行图。\n关键词: 导出 保存 格式 精度 成员 读取 查询",
    )
    @service_errors
    def get_data_result(prompt_id: str, execution_id: str, *, client: AssetClient = Depends(service_client)) -> DataNodeResult:
        return client.get_data_result(prompt_id, execution_id)

    return mcp
