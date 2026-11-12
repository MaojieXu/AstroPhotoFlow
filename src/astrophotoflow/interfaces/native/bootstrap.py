import hmac
import os
from typing import Any

from astrophotoflow.core.config import ConfigurationError
from astrophotoflow.core.localization import localized_error

from .context import native_locale, service_context
from .pages import handle_socket, socket_closed


def register_bundle_routes(routes):
    from aiohttp import web

    @routes.post("/astrophotoflow/internal/bundles/reload")
    async def reload(request):
        try:
            token = service_context().token
        except (OSError, ValueError, ConfigurationError):
            return web.json_response({'error': localized_error(native_locale(), 'SERVICE_NOT_CONFIGURED', 'proxy_unconfigured').model_dump()}, status=503)
        if not hmac.compare_digest(request.headers.get("Authorization", ""), f"Bearer {token}"):
            return web.json_response({'error': localized_error(native_locale(), 'AUTHENTICATION_REQUIRED', 'canvas_auth_required').model_dump()}, status=401)
        from server import PromptServer

        from astrophotoflow.interfaces.native.bundles.catalog import reload_bundle_nodes
        await reload_bundle_nodes(PromptServer.instance)
        return web.json_response({"status": "loaded"})


def register_native(server: Any) -> None:
    import nodes

    from astrophotoflow.interfaces.native.canvas import initialize_canvas
    from astrophotoflow.interfaces.native.data import DataReferenceNode, FileReferenceNode

    nodes.NODE_CLASS_MAPPINGS["APF_DATA_REFERENCE"] = DataReferenceNode
    nodes.NODE_DISPLAY_NAME_MAPPINGS["APF_DATA_REFERENCE"] = "Data"
    nodes.NODE_CLASS_MAPPINGS['APF_FILE_REFERENCE'] = FileReferenceNode
    nodes.NODE_DISPLAY_NAME_MAPPINGS['APF_FILE_REFERENCE'] = 'File'
    from astrophotoflow.interfaces.native.bundles.catalog import register_bundle_nodes
    from astrophotoflow.interfaces.native.bundles.watcher import watch_bundle_nodes
    register_bundle_nodes(server, nodes.NODE_CLASS_MAPPINGS, nodes.NODE_DISPLAY_NAME_MAPPINGS)
    watch_bundle_nodes(server)
    initialize_canvas(server)
    server.apf_page_tasks = {}
    server.apf_page_locks = {}
    server.apf_page_id_by_client = {}
    server.apf_handle_socket = handle_socket
    server.apf_socket_closed = socket_closed
    if os.environ.get("APF_WORKSPACE"):
        from comfy_api import feature_flags
        feature_flags.SERVER_FEATURE_FLAGS["apf_page"] = True
