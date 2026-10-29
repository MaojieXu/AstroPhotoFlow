import asyncio
import hmac
from uuid import UUID

from aiohttp import web
from pydantic import TypeAdapter, ValidationError

from astrophotoflow.contracts.common import ErrorDetail
from astrophotoflow.contracts.workflows import CanvasAddResult, CanvasPageOut, NativeCanvasCommand, NativeCanvasEvent
from astrophotoflow.comfyui.proxy import _configuration


def _error(status: int, code: str, message: str):
    return web.json_response({"error": {"code": code, "message": message, "fields": []}}, status=status)


def _authorized(request):
    _, _, token = _configuration()
    return hmac.compare_digest(request.headers.get("Authorization", ""), f"Bearer {token}")


def initialize_canvas(server):
    server.apf_canvas_pages = {}
    server.apf_canvas_operations = {}


async def handle_canvas_socket(server, socket, message):
    if message.get("type") != "apf.canvas":
        return False
    client_id = next((key for key, value in server.sockets.items() if value is socket), None)
    if client_id is None:
        return True
    metadata = server.sockets_metadata[client_id]
    page_id = metadata["apf_page_id"]
    try:
        event = TypeAdapter(NativeCanvasEvent).validate_python(message.get("data"))
    except ValidationError:
        return True
    if event.action == "state":
        if event.state is None:
            server.apf_canvas_pages.pop(client_id, None)
        else:
            server.apf_canvas_pages[client_id] = CanvasPageOut(page_id=page_id, **event.state.model_dump())
    else:
        operation = server.apf_canvas_operations.get(str(event.result.operation_id))
        if operation is None or operation["client_id"] != client_id or operation["socket"] is not socket:
            return True
        command = operation["command"].request
        result = event.result
        if (str(result.page_id), str(result.workflow_id), str(result.graph_id)) != (str(command.page_id), str(command.workflow_id), str(command.graph_id)):
            return True
        if not operation["future"].done():
            operation["future"].set_result(result)
    return True


def close_canvas_socket(server, client_id, socket):
    server.apf_canvas_pages.pop(client_id, None)
    for operation in server.apf_canvas_operations.values():
        if operation["socket"] is socket and not operation["future"].done():
            operation["future"].set_result(_unknown(operation["command"].request))


def _unknown(request):
    return CanvasAddResult(
        operation_id=request.operation_id, page_id=request.page_id,
        workflow_id=request.workflow_id, graph_id=request.graph_id,
        applied=None, node_id=None,
        error=ErrorDetail(code="CANVAS_RESULT_UNKNOWN", message="未收到画布应用结果；先查询同一 operation_id，不自动重发。", fields=[]),
    )


def register_canvas_routes(routes):
    def server():
        from server import PromptServer
        return PromptServer.instance

    @routes.get("/astrophotoflow/internal/canvas/pages")
    async def pages(request):
        if not _authorized(request):
            return _error(401, "AUTHENTICATION_REQUIRED", "需要平台服务令牌。")
        native = server()
        return web.json_response([page.model_dump(mode="json") for client_id, page in native.apf_canvas_pages.items() if client_id in native.sockets])

    @routes.post("/astrophotoflow/internal/canvas/requests")
    async def add(request):
        if not _authorized(request):
            return _error(401, "AUTHENTICATION_REQUIRED", "需要平台服务令牌。")
        try:
            command = NativeCanvasCommand.model_validate(await request.json())
        except (ValidationError, ValueError):
            return _error(422, "VALIDATION_ERROR", "画布请求无效。")
        native = server()
        body = command.request
        key = str(body.operation_id)
        operation = native.apf_canvas_operations.get(key)
        if operation is not None:
            if operation["command"] != command:
                return _error(409, "CANVAS_REQUEST_CONFLICT", "operation_id 已用于其他请求。")
        else:
            target = next(((client_id, page) for client_id, page in native.apf_canvas_pages.items() if page.page_id == body.page_id), None)
            if target is None or target[0] not in native.sockets:
                return _error(409, "CANVAS_OFFLINE", "目标画布不在线。")
            client_id, page = target
            if (page.workflow_id, page.graph_id, page.content_token, page.control_token) != (body.workflow_id, body.graph_id, body.content_token, body.control_token):
                return _error(409, "CANVAS_TARGET_CHANGED", "画布内容或控制已变化，请重新读取并由用户交回控制。")
            future = asyncio.get_running_loop().create_future()
            operation = {"command": command, "client_id": client_id, "socket": native.sockets[client_id], "future": future}
            native.apf_canvas_operations[key] = operation
            await native.send_json("apf.canvas_command", command.model_dump(mode="json"), client_id)
        try:
            result = await asyncio.wait_for(asyncio.shield(operation["future"]), timeout=5)
        except asyncio.TimeoutError:
            result = _unknown(body)
        return web.json_response(result.model_dump(mode="json"))

    @routes.get("/astrophotoflow/internal/canvas/requests/{operation_id}")
    async def result(request):
        if not _authorized(request):
            return _error(401, "AUTHENTICATION_REQUIRED", "需要平台服务令牌。")
        try:
            key = str(UUID(request.match_info["operation_id"]))
        except ValueError:
            return _error(422, "VALIDATION_ERROR", "operation_id 无效。")
        operation = server().apf_canvas_operations.get(key)
        if operation is None:
            return _error(404, "CANVAS_REQUEST_UNKNOWN", "当前引擎会话没有此请求的回执，不能据此认定未应用。")
        value = operation["future"].result() if operation["future"].done() else _unknown(operation["command"].request)
        return web.json_response(value.model_dump(mode="json"))
