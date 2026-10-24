import os
import sys
import atexit
from pathlib import Path

from server import PromptServer

package_root = Path(os.environ["APF_PACKAGE_ROOT"])
sys.path.insert(0, str(package_root.parent))

from astrophotoflow.proxy import register_proxy_routes
from astrophotoflow.service_manager import ServiceManager

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
WEB_DIRECTORY = "./web"

_service_manager = ServiceManager(package_root)
_service_manager.start()
atexit.register(_service_manager.stop)
register_proxy_routes(PromptServer.instance.routes, _service_manager)
