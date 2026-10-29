import httpx
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from astrophotoflow.interfaces.mcp.tools import canvas, imports, library, organization
from astrophotoflow.client import AssetClient, ServiceApiError
from astrophotoflow.core.config import ConfigurationError


server = MCPServer("AstroPhotoFlow", instructions="Manage the local AstroPhotoFlow library through its shared HTTP service. Read current revisions before editing. Registration, original readiness and preview readiness are separate. Discover bundle nodes with list_nodes/get_node and read their parameters and examples. get_canvas reads the actual online graph without granting control. Add data or use edit_canvas to add nodes, set parameters and connect ports only on an explicitly authorized active canvas using current target tokens. Canvas editing does not execute the workflow. Query unknown application results with the same operation_id; never automatically replay them. Permanent cleanup requires a current trash preview and user authorization.")


def _call(operation):
    try:
        with AssetClient() as client:
            return operation(client)
    except (ConfigurationError, ServiceApiError, httpx.HTTPError, OSError, ValueError, KeyError) as exc:
        raise ToolError(str(exc)) from exc


for domain in (imports, library, organization, canvas):
    domain.register(server, _call)
