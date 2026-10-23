from server import PromptServer

from .src.astrophotoflow import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
from .src.astrophotoflow.proxy import register_proxy_routes

WEB_DIRECTORY = "./web"

register_proxy_routes(PromptServer.instance.routes)

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
