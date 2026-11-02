from fastmcp import FastMCP
from fastmcp.dependencies import Depends
from fastmcp.utilities.types import Image

from astrophotoflow.client import AssetClient
from astrophotoflow.contracts.common import UuidInput
from astrophotoflow.contracts.software import BundlePreviewRequest
from astrophotoflow.interfaces.mcp.composition import tool_namespace
from astrophotoflow.interfaces.mcp.errors import service_errors
from astrophotoflow.interfaces.mcp.lifespan import service_client


def build_server() -> FastMCP:
    mcp = tool_namespace("Previews")

    @mcp.tool(name="render", description="Render a sample preview from an exact fixed reference. Preview is not scientific output; unknown replies must not be replayed automatically. 软件 样本 预览 固定 版本 图像 参数")
    @service_errors
    def render(body: BundlePreviewRequest, *, client: AssetClient = Depends(service_client)) -> Image:
        return Image(data=client.preview_bundle(body), format="png")

    @mcp.tool(name="release", description="Release this preview consumer and observe cancellation through the existing software mechanism. 软件 预览 释放 取消 消费者")
    @service_errors
    def release(consumer_id: UuidInput, *, client: AssetClient = Depends(service_client)) -> None:
        client.release_bundle_preview(consumer_id)

    return mcp
