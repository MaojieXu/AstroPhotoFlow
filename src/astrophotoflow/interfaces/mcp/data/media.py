from pathlib import Path

from fastmcp import FastMCP
from fastmcp.dependencies import Depends
from fastmcp.utilities.types import Image

from astrophotoflow.client import AssetClient
from astrophotoflow.contracts.previews import DisplayPreviewState
from astrophotoflow.interfaces.client.exports import PreviewExportResult
from astrophotoflow.interfaces.mcp.composition import tool_namespace
from astrophotoflow.interfaces.mcp.errors import service_errors
from astrophotoflow.interfaces.mcp.lifespan import service_client


def build_server() -> FastMCP:
    mcp = tool_namespace("media")

    @mcp.tool(
        name="schedule",
        description="Schedule or retry a lazy display JPEG for a fixed original version. Poll get_display_preview_status for readiness.\n为固定原件版本按需生成或重试显示 JPEG，轮询 get_display_preview_status 确认就绪。\n关键词: 预览 图像 显示 JPEG 准备 预览",
    )
    @service_errors
    def schedule_display_preview(asset_id: str, version_id: str, *, client: AssetClient = Depends(service_client)) -> DisplayPreviewState:
        """Schedule or retry a lazy display JPEG for a fixed original version. Poll get_display_preview_status for readiness."""
        return client.schedule_display_preview(asset_id, version_id)

    @mcp.tool(
        name="status",
        description="Read display preview state and errors. Poll generating; for not_ready inspect original/task readiness and wait only for live import/retry work. Cached failed/unsupported are terminal.\n读取显示预览状态及错误。generating 可轮询；not_ready 先查询原件／任务状态，仅有实际导入或重试正在进行时等待。缓存的 failed／unsupported 是终止状态。\n关键词: 预览 图像 显示 JPEG ",
    )
    @service_errors
    def get_display_preview_status(asset_id: str, version_id: str, *, client: AssetClient = Depends(service_client)) -> DisplayPreviewState:
        """Read display preview state and errors. Poll generating; for not_ready inspect original/task readiness and wait only for live import/retry work. Cached failed/unsupported are terminal."""
        return client.get_display_preview_status(asset_id, version_id)

    @mcp.tool(
        name="read",
        description="Explicitly read an available cached display JPEG as an MCP image. Schedule and poll first; routine import results contain no image data.\n明确读取可用的缓存显示 JPEG，作为 MCP 图像返回。先调度并查询就绪；普通导入结果不包含图像数据。\n关键词: 预览 图像 显示 JPEG 读取 图像",
    )
    @service_errors
    def read_display_preview(asset_id: str, version_id: str, *, client: AssetClient = Depends(service_client)) -> Image:
        """Explicitly read an available cached display JPEG as an MCP image. Schedule and poll first; routine import results contain no image data."""
        data = client.read_display_preview(asset_id, version_id)
        return Image(data=data, format="jpeg")

    @mcp.tool(name='export',description='Export an available cached display JPEG to an explicitly chosen new file, never overwriting an existing destination. This is a preview, not scientific output. 预览 显示 图像 导出 文件 原件 保护 不覆盖')
    @service_errors
    def export_preview(asset_id:str,version_id:str,output:Path,*,client:AssetClient=Depends(service_client))->PreviewExportResult:
        return client.export_display_preview(asset_id,version_id,output)

    return mcp
