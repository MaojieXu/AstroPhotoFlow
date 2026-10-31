import asyncio
import os
import json
import sys
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

import aiohttp
from aiohttp import web


from astrophotoflow.core.config import ConfigurationError, load_settings, load_running_settings
from astrophotoflow.core.localization import localized_error, workspace_locale
BASE_PATH = "/astrophotoflow/api/v1"

# Public route, corresponding API path, and method. No wildcard proxy route is registered.
ROUTES = [
    ("POST", "/imports/select-local", "/imports/select-local"),
    ("POST", "/library/canvas-data/inspect", "/library/canvas-data/inspect"),
    ("POST", "/library/canvas-data", "/library/canvas-data"),
    ("GET", "/settings/workbench", "/settings/workbench"),
    ("GET", "/settings/locale", "/settings/locale"),
    ('GET', '/software/packages/{package_id}/releases', '/software/packages/{package_id}/releases'),
    ("POST", "/settings/workbench/restart", "/settings/workbench/restart"),
    ("GET", "/settings/workbench/restart/{operation_id}", "/settings/workbench/restart/{operation_id}"),
    ("PATCH", "/settings/workbench", "/settings/workbench"),
    ("POST", "/settings/workbench/select-directory", "/settings/workbench/select-directory"),
    ("GET", "/health", "/health"),
    ("GET", "/software/packages", "/software/packages"),
    ("GET", "/nodes", "/nodes"),
    ("GET", "/nodes/{definition_id}", "/nodes/{definition_id}"),
    ('GET', '/runs/{prompt_id}/calls', '/runs/{prompt_id}/calls'),
    ('GET', '/runs/{prompt_id}/calls/{call_id}', '/runs/{prompt_id}/calls/{call_id}'),
    ('GET', '/runs/{prompt_id}/calls/{call_id}/log', '/runs/{prompt_id}/calls/{call_id}/log'),
    ("POST", "/software/preview", "/software/preview"),
    ("DELETE", "/software/preview/{consumer_id}", "/software/preview/{consumer_id}"),
    (
        "GET",
        "/software/packages/{package_id}/versions/{version}/commands",
        "/software/packages/{package_id}/versions/{version}/commands",
    ),
    ("GET", "/software/packages/{package_id}", "/software/packages/{package_id}"),
    ("POST", "/software/packages/{package_id}/install", "/software/packages/{package_id}/install"),
    ("POST", "/software/packages/{package_id}/uninstall", "/software/packages/{package_id}/uninstall"),
    ("POST", "/software/packages/siril/autostretch-preview", "/software/packages/siril/autostretch-preview"),
    ("DELETE", "/software/packages/siril/autostretch-preview/{consumer_id}", "/software/packages/siril/autostretch-preview/{consumer_id}"),
    ("POST", "/software/packages/{package_id}/prepare", "/software/packages/{package_id}/prepare"),
    ("GET", "/capabilities", "/capabilities"),
    ("GET", "/projects", "/projects"),
    ("POST", "/projects", "/projects"),
    ("GET", "/projects/{project_id}", "/projects/{project_id}"),
    ("PATCH", "/projects/{project_id}", "/projects/{project_id}"),
    ("GET", "/equipment", "/equipment"),
    ("POST", "/equipment", "/equipment"),
    ("GET", "/equipment/{equipment_id}", "/equipment/{equipment_id}"),
    ("PATCH", "/equipment/{equipment_id}", "/equipment/{equipment_id}"),
    ("GET", "/settings/trash", "/settings/trash"),
    ("POST", "/settings/trash/archive", "/settings/trash/archive"),
    ("POST", "/settings/trash/restore", "/settings/trash/restore"),
    ("POST", "/settings/trash/delete-preview", "/settings/trash/delete-preview"),
    ("POST", "/settings/trash/delete", "/settings/trash/delete"),
    ("POST", "/equipment-management/delete-preview", "/equipment-management/delete-preview"),
    ("POST", "/equipment-management/delete", "/equipment-management/delete"),
    ("GET", "/equipment-setups", "/equipment-setups"),
    ("POST", "/equipment-setups", "/equipment-setups"),
    ("GET", "/equipment-setups/{setup_id}", "/equipment-setups/{setup_id}"),
    ("PATCH", "/equipment-setups/{setup_id}", "/equipment-setups/{setup_id}"),
    ("GET", "/equipment-setups/{setup_id}/presets", "/equipment-setups/{setup_id}/presets"),
    ("POST", "/equipment-setups/{setup_id}/presets", "/equipment-setups/{setup_id}/presets"),
    ("GET", "/capture-presets", "/capture-presets"),
    ("GET", "/capture-presets/{preset_id}", "/capture-presets/{preset_id}"),
    ("PATCH", "/capture-presets/{preset_id}", "/capture-presets/{preset_id}"),
    ("GET", "/library/assets", "/library/assets"),
    ("GET", "/library/items", "/library/items"),
    ("DELETE", "/library/items", "/library/items"),
    ("GET", "/library/trash", "/library/trash"),
    ("POST", "/library/trash/restore", "/library/trash/restore"),
    ("POST", "/library/trash/delete-preview", "/library/trash/delete-preview"),
    ("POST", "/library/trash/delete", "/library/trash/delete"),
    ("GET", "/library/filter-options", "/library/filter-options"),
    ("GET", "/library/assets/{asset_id}", "/library/assets/{asset_id}"),
    ("POST", "/library/assets/{asset_id}/content-observation", "/library/assets/{asset_id}/content-observation"),
    ("POST", "/library/assets/{asset_id}/content-accept", "/library/assets/{asset_id}/content-accept"),
    ("GET", "/projects/{project_id}/assets", "/projects/{project_id}/assets"),
    ("GET", "/projects/{project_id}/asset-references/{reference_id}", "/projects/{project_id}/asset-references/{reference_id}"),
    ("GET", "/projects/{project_id}/asset-references/{reference_id}/previews/{size}", "/projects/{project_id}/asset-references/{reference_id}/previews/{size}"),
    ("GET", "/projects/{project_id}/asset-references/{reference_id}/versions/{version_id}/hdus", "/projects/{project_id}/asset-references/{reference_id}/versions/{version_id}/hdus"),
    ("GET", "/projects/{project_id}/asset-references/{reference_id}/versions/{version_id}/hdus/{hdu_index}/header", "/projects/{project_id}/asset-references/{reference_id}/versions/{version_id}/hdus/{hdu_index}/header"),
    ("GET", "/import-roots", "/import-roots"),
    ("GET", "/import-roots/{root_id}/entries", "/import-roots/{root_id}/entries"),
    ("POST", "/imports", "/imports"),
    ("POST", "/uploads", "/uploads"),
    ("PUT", "/uploads/{task_id}/{index}", "/uploads/{task_id}/{index}"),
    ("POST", "/uploads/{task_id}/start", "/uploads/{task_id}/start"),
    ("POST", "/uploads/{task_id}/fail", "/uploads/{task_id}/fail"),
    ("GET", "/asset-tasks", "/asset-tasks"),
    ("GET", "/asset-tasks/{task_id}", "/asset-tasks/{task_id}"),
    ("POST", "/asset-tasks/{task_id}/cancel", "/asset-tasks/{task_id}/cancel"),
    ("POST", "/asset-tasks/{task_id}/resume", "/asset-tasks/{task_id}/resume"),
    ("POST", "/asset-tasks/{task_id}/retry", "/asset-tasks/{task_id}/retry"),
    ("PATCH", "/library/assets/{asset_id}", "/library/assets/{asset_id}"),
    ("GET", "/library/assets/{asset_id}/versions", "/library/assets/{asset_id}/versions"),
    ("GET", "/library/assets/{asset_id}/versions/{version_id}", "/library/assets/{asset_id}/versions/{version_id}"),
    ("GET", "/library/assets/{asset_id}/versions/{version_id}/hdus", "/library/assets/{asset_id}/versions/{version_id}/hdus"),
    ("GET", "/library/assets/{asset_id}/versions/{version_id}/hdus/{hdu_index}/header", "/library/assets/{asset_id}/versions/{version_id}/hdus/{hdu_index}/header"),
    ("GET", "/library/assets/{asset_id}/versions/{version_id}/previews/{size}", "/library/assets/{asset_id}/versions/{version_id}/previews/{size}"),
    ("POST", "/library/assets/{asset_id}/versions/{version_id}/previews/display", "/library/assets/{asset_id}/versions/{version_id}/previews/display"),
    ("GET", "/library/assets/{asset_id}/versions/{version_id}/previews/display/status", "/library/assets/{asset_id}/versions/{version_id}/previews/display/status"),
    ("POST", "/library/assets/{asset_id}/versions/{version_id}/previews/display/auto-stretch", "/library/assets/{asset_id}/versions/{version_id}/previews/display/auto-stretch"),
    ("POST", "/projects/{project_id}/asset-references/{reference_id}/previews/display", "/projects/{project_id}/asset-references/{reference_id}/previews/display"),
    ("GET", "/projects/{project_id}/asset-references/{reference_id}/previews/display/status", "/projects/{project_id}/asset-references/{reference_id}/previews/display/status"),
    ("POST", "/projects/{project_id}/asset-references/{reference_id}/previews/display/auto-stretch", "/projects/{project_id}/asset-references/{reference_id}/previews/display/auto-stretch"),
    ("GET", "/datasets", "/datasets"),
    ("POST", "/datasets", "/datasets"),
    ("GET", "/calibration/targets", "/calibration/targets"),
    ("GET", "/datasets/{dataset_id}", "/datasets/{dataset_id}"),
    ("PATCH", "/datasets/{dataset_id}", "/datasets/{dataset_id}"),
    ("PATCH", "/datasets/{dataset_id}/member-parameters", "/datasets/{dataset_id}/member-parameters"),
    ("GET", "/datasets/{dataset_id}/versions", "/datasets/{dataset_id}/versions"),
    ("POST", "/datasets/{dataset_id}/versions", "/datasets/{dataset_id}/versions"),
    ("GET", "/datasets/{dataset_id}/versions/{version_id}", "/datasets/{dataset_id}/versions/{version_id}"),
    ("GET", "/projects/{project_id}/datasets", "/projects/{project_id}/datasets"),
    ("GET", "/projects/{project_id}/dataset-references", "/projects/{project_id}/dataset-references"),
    ("POST", "/projects/{project_id}/dataset-references", "/projects/{project_id}/dataset-references"),
    ("GET", "/projects/{project_id}/dataset-references/{reference_id}", "/projects/{project_id}/dataset-references/{reference_id}"),
    ("DELETE", "/projects/{project_id}/dataset-references/{reference_id}", "/projects/{project_id}/dataset-references/{reference_id}"),
    ("POST", "/projects/{project_id}/asset-references", "/projects/{project_id}/asset-references"),
    ("DELETE", "/projects/{project_id}/asset-references/{reference_id}", "/projects/{project_id}/asset-references/{reference_id}"),
]


class ProxyError(Exception):
    def __init__(self, status: int, code: str, message: str, *, message_key: str):
        self.status = status
        self.code = code
        self.message = message
        self.message_key = message_key


for _scope in ("/library/assets/{asset_id}/versions/{version_id}/previews", "/projects/{project_id}/asset-references/{reference_id}/previews"):
    for _method, _suffix in (("POST", "/viewer"), ("DELETE", "/viewer/consumer/{consumer_id}"), ("GET", "/viewer/{key}/status"), ("GET", "/viewer/{key}/tiles/{level}/{x}/{y}"), ("GET", "/viewer/{key}/{file}")):
        ROUTES.append((_method, _scope + _suffix, _scope + _suffix))

_output_scope = '/runs/{prompt_id}/calls/{call_id}/outputs/{output_index}/members/{member_index}'
for _method, _suffix in [('GET', '/analysis'), ('GET', '/file'), ('GET', '/thumbnail'),
                         ('POST', '/viewer'), ('DELETE', '/viewer/consumer/{consumer_id}'),
                         ('GET', '/viewer/{key}/status'), ('GET', '/viewer/{key}/tiles/{level}/{x}/{y}'),
                         ('GET', '/viewer/{key}/{file}')]:
    ROUTES.append((_method, _output_scope + _suffix, _output_scope + _suffix))


def _configuration(*, allow_missing_token: bool = False):
    try:
        settings = load_running_settings(Path(os.environ["APF_WORKSPACE"])) if "APF_WORKSPACE" in os.environ else load_settings()
        token_path = settings.token_path
        try:
            token = token_path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            if not allow_missing_token:
                raise
            token = None
        if token is not None and not token:
            if allow_missing_token:
                token = None
            else:
                raise ValueError("服务令牌为空")
        return settings.service_url, set(settings.allowed_origins), token
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
        directory_selection = request.method == "POST" and path_template in {"/settings/workbench/select-directory", "/imports/select-local"}
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
    except (asyncio.TimeoutError, TimeoutError):
        return _error_response(request_id, 504, "SERVICE_TIMEOUT", 'proxy_timeout')
    except aiohttp.ClientError:
        return _error_response(request_id, 503, "SERVICE_UNAVAILABLE", 'proxy_unavailable')


def register_proxy_routes(routes: web.RouteTableDef) -> None:
    from astrophotoflow.interfaces.canvas_native import register_canvas_routes
    from astrophotoflow.interfaces.comfyui import register_bundle_routes

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
