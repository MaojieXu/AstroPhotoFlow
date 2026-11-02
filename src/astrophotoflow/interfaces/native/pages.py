import asyncio
import logging
from typing import Any
from uuid import uuid4

from pydantic import TypeAdapter

from astrophotoflow.contracts.native import NativePageEvent, NativePageReply
from astrophotoflow.core.config import ConfigurationError
from astrophotoflow.core.localization import exception_error, localized_error, workspace_locale

from .context import native_locale, service_context

logger = logging.getLogger(__name__)

def socket_id(server: Any, socket: Any) -> str | None:
    return next((client_id for client_id, candidate in server.sockets.items() if candidate is socket), None)


async def handle_socket(server: Any, socket: Any, message: dict) -> bool:
    from astrophotoflow.interfaces.native.canvas import handle_canvas_socket

    if await handle_canvas_socket(server, socket, message):
        return True
    if message.get("type") != "apf.page":
        return False
    data = message.get("data")
    client_id = socket_id(server, socket)
    if not isinstance(data, dict) or client_id is None:
        return True
    lock = server.apf_page_locks.setdefault(client_id, asyncio.Lock())
    task = asyncio.create_task(forward_page_event_locked(lock, server, socket, client_id, data))
    server.apf_page_tasks.setdefault(client_id, set()).add(task)
    task.add_done_callback(server.apf_page_tasks[client_id].discard)
    return True


async def forward_page_event_locked(lock: asyncio.Lock, server: Any, socket: Any, client_id: str, data: dict) -> None:
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
        context = service_context()
        settings, token = context.settings, context.token
        if token is None:
            raise ConfigurationError('领域服务令牌为空。')
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
                if (reply.event_id != event.event_id or reply.page_id != event.page_id
                        or reply.page_token != event.page_token):
                    raise ValueError('Native page reply belongs to another request or page.')
            else:
                body = await response.json()
                message_text = body.get('error', {}).get('message')
                reply = NativePageReply(
                    event_id=event.event_id, page_id=event.page_id, page_token=event.page_token,
                    result=None, error=localized_error(workspace_locale(settings.workspace), 'NATIVE_PAGE_REJECTED', 'forwarded_service_error' if message_text else 'native_page_rejected', parameters={'message': message_text}, fields=body.get('error', {}).get('fields', [])),
                )
    except (OSError, KeyError, ValueError, ConfigurationError, TimeoutError, ClientError) as exc:
        reply = NativePageReply(
            event_id=event.event_id,
            page_id=event.page_id,
            page_token=event.page_token,
            result=None,
            error=exception_error(native_locale(), exc, code='NATIVE_BRIDGE_UNAVAILABLE', message_key='native_bridge_unavailable'),
        )
    if event.action != "close":
        await server.send_json("apf.page_result", reply.model_dump(mode="json"), client_id)


async def socket_closed(server: Any, socket: Any) -> None:
    from astrophotoflow.interfaces.native.canvas import close_canvas_socket
    client_id = socket_id(server, socket)
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
