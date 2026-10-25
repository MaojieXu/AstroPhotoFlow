import httpx
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from .agent_tools import imports, library, organization
from .client import AssetClient, ServiceApiError
from .config import ConfigurationError


server = MCPServer("AstroPhotoFlow", instructions="Manage the local AstroPhotoFlow library through its shared HTTP service. Read current revisions before editing. Registration, original readiness and preview readiness are separate. Permanent cleanup requires a current trash preview and user authorization.")


def _call(operation):
    try:
        with AssetClient() as client:
            return operation(client)
    except (ConfigurationError, ServiceApiError, httpx.HTTPError, OSError, ValueError, KeyError) as exc:
        raise ToolError(str(exc)) from exc


for domain in (imports, library, organization):
    domain.register(server, _call)
