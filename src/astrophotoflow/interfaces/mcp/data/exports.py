from fastmcp import FastMCP
from fastmcp.dependencies import Depends

from astrophotoflow.client import AssetClient
from astrophotoflow.contracts.data_nodes import ExportReceipt, ExportRequest
from astrophotoflow.interfaces.mcp.composition import tool_namespace
from astrophotoflow.interfaces.mcp.errors import service_errors
from astrophotoflow.interfaces.mcp.lifespan import service_client


def build_server() -> FastMCP:
    mcp = tool_namespace("exports")

    @mcp.tool(
        name="submit",
        description="Save explicitly selected Data members to the library or an absolute local destination. Format/precision affect copies only; preserve numeric values by default. Reuse request_id for unknown acceptance; never rerun upstream processing.\n按用户明确选择保存Data完整结果到素材库或本机；格式与精度只影响副本，默认保留数值，request_id防重复；不执行上游。\n关键词: 导出 保存 格式 精度 成员 提交 确认",
    )
    @service_errors
    def submit_export(body: ExportRequest, *, client: AssetClient = Depends(service_client)) -> ExportReceipt:
        return client.submit_export(body)

    @mcp.tool(
        name="status",
        description="Read export receipts and member outcomes, including registration task IDs. Query unknown results rather than replaying writes.\n查询导出回执与成员结果，包括登记任务ID；未知结果先查，不重放。\n关键词: 导出 保存 格式 精度 成员 ",
    )
    @service_errors
    def get_export(request_id: str, *, client: AssetClient = Depends(service_client)) -> ExportReceipt:
        return client.get_export(request_id)

    @mcp.tool(
        name="cancel",
        description="Request export cancellation. Completed members remain; read the receipt to confirm actual stopping.\n请求取消尚未完成的导出；已完成的成员保留，查询回执确认实际停止。\n关键词: 导出 保存 格式 精度 成员 取消 停止",
    )
    @service_errors
    def cancel_export(request_id: str, *, client: AssetClient = Depends(service_client)) -> ExportReceipt:
        return client.cancel_export(request_id)

    return mcp
