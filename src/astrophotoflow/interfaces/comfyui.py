import asyncio
import hmac
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4
from pydantic import TypeAdapter

from astrophotoflow.contracts.common import ErrorDetail
from astrophotoflow.contracts.workflows import NativePageEvent, NativePageReply
from astrophotoflow.core.config import ConfigurationError, load_running_settings

if TYPE_CHECKING:
    from aiohttp import web

logger = logging.getLogger("astrophotoflow.comfyui")


def register_bundle_routes(routes):
    from aiohttp import web
    from astrophotoflow.comfyui.proxy import _configuration

    @routes.post("/astrophotoflow/internal/bundles/reload")
    async def reload(request):
        _, _, token = _configuration()
        if not hmac.compare_digest(request.headers.get("Authorization", ""), f"Bearer {token}"):
            return web.json_response({"error": {"code": "AUTHENTICATION_REQUIRED", "message": "需要平台服务令牌。", "fields": []}}, status=401)
        from server import PromptServer
        from astrophotoflow.interfaces.bundle_nodes import reload_bundle_nodes
        await reload_bundle_nodes(PromptServer.instance)
        return web.json_response({"status": "loaded"})


def register_native(server: Any) -> None:
    from astrophotoflow.interfaces.canvas_native import initialize_canvas
    from astrophotoflow.interfaces.data_reference_node import DataReferenceNode, FileReferenceNode
    import nodes

    nodes.NODE_CLASS_MAPPINGS["APF_DATA_REFERENCE"] = DataReferenceNode
    nodes.NODE_DISPLAY_NAME_MAPPINGS["APF_DATA_REFERENCE"] = "Data"
    nodes.NODE_CLASS_MAPPINGS['APF_FILE_REFERENCE'] = FileReferenceNode
    nodes.NODE_DISPLAY_NAME_MAPPINGS['APF_FILE_REFERENCE'] = 'File'
    from astrophotoflow.interfaces.bundle_nodes import register_bundle_nodes, watch_bundle_nodes
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


def _socket_id(server: Any, socket: Any) -> str | None:
    return next((client_id for client_id, candidate in server.sockets.items() if candidate is socket), None)


async def handle_socket(server: Any, socket: Any, message: dict) -> bool:
    from astrophotoflow.interfaces.canvas_native import handle_canvas_socket

    if await handle_canvas_socket(server, socket, message):
        return True
    if message.get("type") != "apf.page":
        return False
    data = message.get("data")
    client_id = _socket_id(server, socket)
    if not isinstance(data, dict) or client_id is None:
        return True
    lock = server.apf_page_locks.setdefault(client_id, asyncio.Lock())
    task = asyncio.create_task(_forward_page_event_locked(lock, server, socket, client_id, data))
    server.apf_page_tasks.setdefault(client_id, set()).add(task)
    task.add_done_callback(server.apf_page_tasks[client_id].discard)
    return True


async def _forward_page_event_locked(lock: asyncio.Lock, server: Any, socket: Any, client_id: str, data: dict) -> None:
    async with lock:
        await forward_page_event(server, socket, client_id, data)


async def forward_page_event(server: Any, socket: Any, client_id: str, data: dict) -> None:
    from aiohttp import ClientError

    metadata = server.sockets_metadata.get(client_id)
    if metadata is None:
        return
    try:
        event = TypeAdapter(NativePageEvent).validate_python({
            **data,
            "page_id": metadata["apf_page_id"],
            "page_token": metadata["apf_page_token"],
        })
    except (KeyError, TypeError, ValueError):
        return
    try:
        settings = load_running_settings(Path(os.environ["APF_WORKSPACE"]))
        token = settings.token_path.read_text(encoding="utf-8").strip()
        if not token:
            raise ConfigurationError("领域服务令牌为空。")
        if server.client_session is None:
            raise ConfigurationError("领域服务连接未就绪。")
        async with server.client_session.post(
            settings.service_url + "/internal/native/page",
            json=event.model_dump(mode="json"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        ) as response:
            if response.status == 200:
                reply = NativePageReply.model_validate_json(await response.text())
            else:
                body = await response.json()
                message_text = body.get("error", {}).get("message", "页面操作已被领域服务拒绝。")
                reply = NativePageReply(
                    event_id=event.event_id, page_id=event.page_id, page_token=event.page_token,
                    result=None, error=ErrorDetail(code="NATIVE_PAGE_REJECTED", message=message_text, fields=[]),
                )
    except (OSError, KeyError, ValueError, ConfigurationError, asyncio.TimeoutError, TimeoutError, ClientError):
        reply = NativePageReply(
            event_id=event.event_id,
            page_id=event.page_id,
            page_token=event.page_token,
            result=None,
            error=ErrorDetail(code="NATIVE_BRIDGE_UNAVAILABLE", message="无法核对软件页面操作结果。", fields=[]),
        )
    if event.action != "close":
        await server.send_json("apf.page_result", reply.model_dump(mode="json"), client_id)


async def socket_closed(server: Any, socket: Any) -> None:
    from astrophotoflow.interfaces.canvas_native import close_canvas_socket
    client_id = _socket_id(server, socket)
    if client_id is None:
        return
    close_canvas_socket(server, client_id, socket)
    tasks = server.apf_page_tasks.pop(client_id, set())
    for result in await asyncio.gather(*tasks, return_exceptions=True):
        if isinstance(result, BaseException):
            logger.warning("native page event ended with unknown result: %s", result)
    server.apf_page_locks.pop(client_id, None)
    metadata = server.sockets_metadata.get(client_id)
    if metadata is not None:
        await forward_page_event(server, socket, client_id, {
            "event_id": str(uuid4()),
            "action": "close",
            "payload": None,
        })
