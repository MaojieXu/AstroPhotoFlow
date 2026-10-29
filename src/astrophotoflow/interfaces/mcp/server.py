import httpx
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from astrophotoflow.interfaces.mcp.tools import canvas, imports, library, organization
from astrophotoflow.client import AssetClient, ServiceApiError
from astrophotoflow.core.config import ConfigurationError


server = MCPServer("AstroPhotoFlow", instructions="Manage the local AstroPhotoFlow library through its shared HTTP service. Read current revisions before editing. Registration, original readiness and preview readiness are separate. Add fixed data only to an explicitly authorized active canvas using current target tokens. Query unknown application results with the same operation_id; never automatically replay them. Permanent cleanup requires a current trash preview and user authorization.")


def _call(operation):
    try:
        with AssetClient() as client:
            return operation(client)
    except (ConfigurationError, ServiceApiError, httpx.HTTPError, OSError, ValueError, KeyError) as exc:
        raise ToolError(str(exc)) from exc


for domain in (imports, library, organization, canvas):
    domain.register(server, _call)
