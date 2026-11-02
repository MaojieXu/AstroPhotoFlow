from fastmcp import FastMCP
from fastmcp.dependencies import Depends

from astrophotoflow.client import AssetClient
from astrophotoflow.contracts.calibration import CalibrationTargetPage
from astrophotoflow.interfaces.mcp.composition import tool_namespace
from astrophotoflow.interfaces.mcp.errors import service_errors
from astrophotoflow.interfaces.mcp.lifespan import service_client


def build_server() -> FastMCP:
    mcp = tool_namespace("calibration")

    @mcp.tool(
        name="targets",
        description="Find fixed Master asset or calibration dataset version targets, with pagination.\n分页查找固定 Master 素材版本或校准图像组版本。\n关键词: 校准 暗场 偏置 平场 绑定 ",
    )
    @service_errors
    def list_calibration_targets(
        limit: int = 50,
        offset: int = 0,
        frame_type: str | None = None,
        q: str | None = None,
        *,
        client: AssetClient = Depends(service_client),
    ) -> CalibrationTargetPage:
        """Find fixed Master asset or calibration dataset version targets, with pagination."""
        return client.list_calibration_targets(limit, offset, frame_type, q)

    return mcp
