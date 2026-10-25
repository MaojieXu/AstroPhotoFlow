import atexit
from pathlib import Path

from server import PromptServer

from .src.astrophotoflow import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
from .src.astrophotoflow.comfyui.proxy import register_proxy_routes
from .src.astrophotoflow.comfyui.service_manager import ServiceManager

WEB_DIRECTORY = "./build/frontend"

_service_manager = ServiceManager(Path(__file__).resolve().parent)
_service_manager.start()
atexit.register(_service_manager.stop)
register_proxy_routes(PromptServer.instance.routes, _service_manager)

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
