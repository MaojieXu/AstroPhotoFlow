from pathlib import Path
from typing import Any

import httpx
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from astrophotoflow.backend.import_schemas import AssetParametersPatch

from .client import AssetClient, ServiceApiError
from .config import ConfigurationError


server = MCPServer("AstroPhotoFlow", instructions="使用本机 AstroPhotoFlow 工作台 API 管理托管天文照片和当前参数。")


def _call(operation):
    try:
        return operation()
    except (ConfigurationError, ServiceApiError, httpx.HTTPError, OSError, ValueError, KeyError) as exc:
        raise ToolError(str(exc)) from exc


@server.tool()
def import_photo(path: str) -> dict[str, Any]:
    """Copy one local photo into the shared AstroPhotoFlow library and start ingestion. Returns a task ID."""
    return _call(lambda: _with_client(lambda client: client.import_photo(Path(path))))


@server.tool()
def get_import_task(task_id: str) -> dict[str, Any]:
    """Read the status and result of an AstroPhotoFlow import task."""
    return _call(lambda: _with_client(lambda client: client.request("GET", f"/asset-tasks/{task_id}")))


@server.tool()
def list_assets(limit: int = 50, offset: int = 0) -> dict[str, Any]:
    """List shared library assets, with limit and offset pagination."""
    return _call(lambda: _with_client(lambda client: client.request("GET", "/library/assets", params={"limit": limit, "offset": offset})))


@server.tool()
def get_asset(asset_id: str) -> dict[str, Any]:
    """Read one shared library asset and its current editable parameters."""
    return _call(lambda: _with_client(lambda client: client.request("GET", f"/library/assets/{asset_id}")))


@server.tool()
def update_asset_parameters(asset_id: str, base_revision: int, parameters: AssetParametersPatch) -> dict[str, Any]:
    """Set, change, or clear supplied asset parameter fields. Omitted fields stay unchanged; explicit null clears a field. A current base_revision is required."""
    payload = parameters.model_dump(mode="json", exclude_unset=True)
    return _call(lambda: _with_client(lambda client: client.request(
        "PATCH", f"/library/assets/{asset_id}",
        json={"base_revision": base_revision, "parameters": payload},
    )))


def _with_client(operation):
    with AssetClient() as client:
        return operation(client)
