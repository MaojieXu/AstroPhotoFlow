import asyncio
import json
import os
import sys
from importlib.resources import files
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

import aiohttp
from aiohttp import web

from astrophotoflow.core.config import ConfigurationError
from astrophotoflow.core.localization import localized_error, workspace_locale
from astrophotoflow.interfaces.native.context import service_context

BASE_PATH = "/astrophotoflow/api/v1"

# Generated from the backend OpenAPI by scripts/export_openapi.py. Keep an
# explicit public allowlist; never expose native/internal paths via a wildcard.
_ROUTE_MANIFEST = json.loads(files("astrophotoflow").joinpath("vendor/http-routes.json").read_text(encoding="utf-8"))
ROUTES = [(item["method"], item["path"], item["path"]) for item in _ROUTE_MANIFEST["routes"]]


class ProxyError(Exception):
    def __init__(self, status: int, code: str, message: str, *, message_key: str):
        self.status = status
        self.code = code
        self.message = message
        self.message_key = message_key


def _configuration(*, allow_missing_token: bool = False):
    try:
        context = service_context(allow_missing_token=allow_missing_token)
        return context.settings.service_url, set(context.settings.allowed_origins), context.token
    except (OSError, ConfigurationError, ValueError) as exc:
        raise ProxyError(503, "SERVICE_NOT_CONFIGURED", "AstroPhotoFlow 本机服务配置或令牌不可用。", message_key='proxy_unconfigured') from exc


def _deny_origin(request: web.Request, allowed: set[str]) -> None:
    origin = request.headers.get("Origin")
    if origin is not None:
        if origin not in allowed:
            raise ProxyError(403, "ORIGIN_NOT_ALLOWED", "请求来源不在 AstroPhotoFlow 允许列表中。", message_key='proxy_origin_denied')
        return
    if request.headers.get("Sec-Fetch-Site") != "same-origin":
        raise ProxyError(403, "ORIGIN_NOT_ALLOWED", "缺少 Origin 时只接受同源 Fetch 请求。", message_key='proxy_same_origin_required')
    request_origin = f"{request.scheme}://{request.headers.get('Host', '')}"
    if request_origin not in allowed:
        raise ProxyError(403, "ORIGIN_NOT_ALLOWED", "请求来源不在 AstroPhotoFlow 允许列表中。", message_key='proxy_origin_denied')


def _error_response(request_id: str, status: int, code: str, message_key: str) -> web.Response:
    workspace = os.environ.get('APF_WORKSPACE')
    locale = workspace_locale(Path(workspace)) if workspace else 'en'
    body = {"error": localized_error(locale, code, message_key).model_dump(), "request_id": request_id}
    return web.json_response(body, status=status, headers={"X-Request-ID": request_id})


async def forward(request: web.Request, path_template: str) -> web.StreamResponse:
    request_id = str(uuid4())
    try:
        upstream, allowed_origins, token = _configuration()
        _deny_origin(request, allowed_origins)
        values = {key: quote(value, safe="-") for key, value in request.match_info.items()}
        upstream_path = path_template.format(**values)
        url = f"{upstream}/api/v1{upstream_path}"
        query = list(request.rel_url.query.items())
        headers = {"Authorization": f"Bearer {token}", "X-Request-ID": request_id}
        media_stream = request.method == "GET" and "/previews/viewer/" in path_template
        if media_stream:
            for header in ("Range", "If-Range", "If-None-Match", "If-Modified-Since"):
                if header in request.headers:
                    headers[header] = request.headers[header]
        if request.method in {"POST", "PATCH", "DELETE", "PUT"}:
            headers["Content-Type"] = request.headers.get("Content-Type", "application/json")
        streaming_upload = request.method == "PUT" and "/uploads/" in request.path
        body = request.content if streaming_upload else await request.read() if request.method in {"POST", "PATCH", "DELETE", "PUT"} else None
        directory_selection = request.method == "POST" and path_template in {"/settings/workbench/select-directory", "/imports/select-local", '/exports/select-local'}
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=10, sock_read=None) if streaming_upload or directory_selection or media_stream else aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as client:
            async def upstream_response():
                async with client.request(request.method, url, params=query, data=body, headers=headers, allow_redirects=False) as response:
                    if media_stream:
                        selected_headers = {key: value for key, value in response.headers.items() if key.lower() in {
                            "content-type", "content-length", "content-range", "accept-ranges", "etag", "last-modified", "cache-control", "x-request-id"}}
                        downstream = web.StreamResponse(status=response.status, headers=selected_headers)
                        await downstream.prepare(request)
                        async for chunk in response.content.iter_chunked(256 * 1024):
                            await downstream.write(chunk)
                        await downstream.write_eof()
                        return downstream
                    response_body = await response.read()
                    response_headers = {"X-Request-ID": response.headers.get("X-Request-ID", request_id)}
                    if content_type := response.headers.get("Content-Type"):
                        response_headers["Content-Type"] = content_type
                    return web.Response(body=response_body, status=response.status, headers=response_headers)
            if path_template != "/imports/select-local" and not media_stream:
                return await upstream_response()
            pending = asyncio.create_task(upstream_response())
            try:
                while not pending.done():
                    await asyncio.wait({pending}, timeout=0.1)
                    if request.transport is None or request.transport.is_closing():
                        raise asyncio.CancelledError()
                return await pending
            finally:
                if not pending.done():
                    pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
    except ProxyError as exc:
        return _error_response(request_id, exc.status, exc.code, exc.message_key)
    except TimeoutError:
        return _error_response(request_id, 504, "SERVICE_TIMEOUT", 'proxy_timeout')
    except aiohttp.ClientError:
        return _error_response(request_id, 503, "SERVICE_UNAVAILABLE", 'proxy_unavailable')


def register_proxy_routes(routes: web.RouteTableDef) -> None:
    from astrophotoflow.interfaces.native.bootstrap import register_bundle_routes
    from astrophotoflow.interfaces.native.canvas import register_canvas_routes

    register_canvas_routes(routes)
    register_bundle_routes(routes)
    if os.environ.get("APF_WORKSPACE") and (native_server := sys.modules.get("server")) is not None:
        native_server.PromptServer.instance.app.middlewares.append(native_admission_middleware())
    for method, public_path, upstream_path in ROUTES:
        async def handler(
            request: web.Request,
            template: str = upstream_path,
        ) -> web.Response:
            return await forward(request, template)
        routes.route(method, BASE_PATH + public_path)(handler)


def native_admission_middleware():
    queue_admission = asyncio.Lock()

    @web.middleware
    async def admission(request, handler):
        if request.method == "POST" and request.path in {"/prompt", "/api/prompt"}:
            async with queue_admission:
                try:
                    workspace = Path(os.environ["APF_WORKSPACE"])
                    record = json.loads((workspace / "run/processes.json").read_text(encoding="utf-8"))
                    closed = record["maintenance_operation_id"] is not None
                    control_path = workspace / "run/control.json"
                    if control_path.is_file():
                        control = json.loads(control_path.read_text(encoding="utf-8"))["result"]
                        closed = closed or control["state"] in {"in_progress", "unknown"}
                    if closed:
                        return _error_response(str(uuid4()), 409, "WORKBENCH_MAINTENANCE", 'proxy_maintenance')
                except (OSError, KeyError, TypeError, ValueError):
                    return _error_response(str(uuid4()), 503, "WORKBENCH_STATE_UNKNOWN", 'proxy_state_unknown')
                return await handler(request)
        if request.method == "GET" and request.path in {"/queue", "/api/queue"}:
            async with queue_admission:
                return await handler(request)
        return await handler(request)

    return admission
