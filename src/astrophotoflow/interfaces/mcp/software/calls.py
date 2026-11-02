from fastmcp import FastMCP
from fastmcp.dependencies import Depends

from astrophotoflow.client import AssetClient
from astrophotoflow.contracts.bundles import AnalysisResult
from astrophotoflow.contracts.software import SoftwareCallResult
from astrophotoflow.interfaces.mcp.composition import tool_namespace
from astrophotoflow.interfaces.mcp.errors import service_errors
from astrophotoflow.interfaces.mcp.lifespan import service_client


def build_server() -> FastMCP:
    mcp = tool_namespace("calls")

    @mcp.tool(
        name="list_calls",
        description="Read observed software calls for an explicit native prompt. Returns checked output ports and implementation versions, not scientific pixels. An empty list is not proof that no work ran. Never replay unknown calls.\n查询明确原生 prompt 的实际软件调用、已检查输出端口和实现版本，不返回科学像素。空列表不证明没有执行过。未知调用不得重放。\n关键词: 软件 调用 分析 结果 列表 分页 查询",
    )
    @service_errors
    def list_run_calls(
        prompt_id: str, node_id: str | None = None, limit: int = 50, offset: int = 0, *, client: AssetClient = Depends(service_client)
    ) -> list[SoftwareCallResult]:
        """Read observed software calls for an explicit native prompt. Returns checked output ports and implementation versions, not scientific pixels. An empty list is not proof that no work ran. Never replay unknown calls."""
        return client.list_run_calls(prompt_id, node_id, limit, offset)

    @mcp.tool(
        name="get_call",
        description="Query one accepted software call, checked result availability and actual process observations. Unknown remains unknown even when an old process has exited; this tool never re-executes processing.\n查询已受理的软件调用、已检查结果及实际进程状态。旧进程退出不代表未知结果变为已知；本工具不会重新执行处理。\n关键词: 软件 调用 分析 结果 读取 查询",
    )
    @service_errors
    def get_run_call(prompt_id: str, call_id: str, *, client: AssetClient = Depends(service_client)) -> SoftwareCallResult:
        """Query one accepted software call, checked result availability and actual process observations. Unknown remains unknown even when an old process has exited; this tool never re-executes processing."""
        return client.get_run_call(prompt_id, call_id)

    @mcp.tool(
        name="analysis",
        description="Read one checked analysis member as metrics, a histogram/series, a table or a textual report. Units, sample limits and unavailable values are explicit; preview values are not scientific image inputs.\n读取已检查分析成员的指标、直方图／曲线、表格或文本报告。保留单位、样本限制和不可用值；预览数值不是科学图像输入。\n关键词: 软件 调用 分析 结果 ",
    )
    @service_errors
    def get_run_analysis(
        prompt_id: str, call_id: str, output_index: int, member_index: int, *, client: AssetClient = Depends(service_client)
    ) -> list[AnalysisResult]:
        """Read one checked analysis member as metrics, a histogram/series, a table or a textual report. Units, sample limits and unavailable values are explicit; preview values are not scientific image inputs."""
        return client.get_run_analysis(prompt_id, call_id, output_index, member_index)

    return mcp
