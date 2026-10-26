import asyncio
from urllib.parse import quote
from uuid import uuid4

import aiohttp
from aiohttp import web


from astrophotoflow.core.config import ConfigurationError, load_settings
BASE_PATH = "/astrophotoflow/api/v1"

# Public route, corresponding API path, and method. No wildcard proxy route is registered.
ROUTES = [
    ("GET", "/health", "/health"),
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
    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message


def _configuration(*, allow_missing_token: bool = False):
    try:
        settings = load_settings()
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
        raise ProxyError(503, "SERVICE_NOT_CONFIGURED", "AstroPhotoFlow 本机服务配置或令牌不可用。") from exc


def _deny_origin(request: web.Request, allowed: set[str]) -> None:
    origin = request.headers.get("Origin")
    if origin is not None:
        if origin not in allowed:
            raise ProxyError(403, "ORIGIN_NOT_ALLOWED", "请求来源不在 AstroPhotoFlow 允许列表中。")
        return
    if request.headers.get("Sec-Fetch-Site") != "same-origin":
        raise ProxyError(403, "ORIGIN_NOT_ALLOWED", "缺少 Origin 时只接受同源 Fetch 请求。")
    request_origin = f"{request.scheme}://{request.headers.get('Host', '')}"
    if request_origin not in allowed:
        raise ProxyError(403, "ORIGIN_NOT_ALLOWED", "请求来源不在 AstroPhotoFlow 允许列表中。")


def _error_response(request_id: str, status: int, code: str, message: str) -> web.Response:
    body = {"error": {"code": code, "message": message, "fields": []}, "request_id": request_id}
    return web.json_response(body, status=status, headers={"X-Request-ID": request_id})


async def forward(request: web.Request, path_template: str) -> web.Response:
    request_id = str(uuid4())
    try:
        upstream, allowed_origins, token = _configuration()
        _deny_origin(request, allowed_origins)
        values = {key: quote(value, safe="-") for key, value in request.match_info.items()}
        upstream_path = path_template.format(**values)
        url = f"{upstream}/api/v1{upstream_path}"
        query = list(request.rel_url.query.items())
        headers = {"Authorization": f"Bearer {token}", "X-Request-ID": request_id}
        if request.method in {"POST", "PATCH", "DELETE", "PUT"}:
            headers["Content-Type"] = request.headers.get("Content-Type", "application/json")
        streaming_upload = request.method == "PUT" and "/uploads/" in request.path
        body = request.content if streaming_upload else await request.read() if request.method in {"POST", "PATCH", "DELETE", "PUT"} else None
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=10, sock_read=None) if streaming_upload else aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as client:
            async with client.request(request.method, url, params=query, data=body, headers=headers, allow_redirects=False) as response:
                response_body = await response.read()
                response_headers = {"X-Request-ID": response.headers.get("X-Request-ID", request_id)}
                if content_type := response.headers.get("Content-Type"):
                    response_headers["Content-Type"] = content_type
                return web.Response(body=response_body, status=response.status, headers=response_headers)
    except ProxyError as exc:
        return _error_response(request_id, exc.status, exc.code, exc.message)
    except (asyncio.TimeoutError, TimeoutError):
        return _error_response(request_id, 504, "SERVICE_TIMEOUT", "等待 AstroPhotoFlow 服务超时。")
    except aiohttp.ClientError:
        return _error_response(request_id, 503, "SERVICE_UNAVAILABLE", "AstroPhotoFlow 服务当前不可用。")


def register_proxy_routes(routes: web.RouteTableDef) -> None:
    for method, public_path, upstream_path in ROUTES:
        async def handler(
            request: web.Request,
            template: str = upstream_path,
        ) -> web.Response:
            return await forward(request, template)
        routes.route(method, BASE_PATH + public_path)(handler)
