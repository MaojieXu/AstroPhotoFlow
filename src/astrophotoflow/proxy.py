import asyncio
import ipaddress
import os
from pathlib import Path
import tomllib
from urllib.parse import quote
from uuid import uuid4

import aiohttp
from aiohttp import web


CONFIG_PATH = Path.home() / ".config/astrophotoflow/config.toml"
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
    ("GET", "/capture-profiles", "/capture-profiles"),
    ("POST", "/capture-profiles", "/capture-profiles"),
    ("GET", "/capture-profiles/{profile_id}", "/capture-profiles/{profile_id}"),
    ("PATCH", "/capture-profiles/{profile_id}", "/capture-profiles/{profile_id}"),
    ("GET", "/library/assets", "/library/assets"),
    ("GET", "/library/items", "/library/items"),
    ("DELETE", "/library/items", "/library/items"),
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
    ("GET", "/datasets", "/datasets"),
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
        config_path = Path(os.environ.get("ASTROPHOTOFLOW_CONFIG", CONFIG_PATH)).expanduser()
        with config_path.open("rb") as stream:
            config = tomllib.load(stream)
        if set(config) not in ({"server", "storage", "comfyui"}, {"server", "storage", "comfyui", "imports"}):
            raise ValueError("配置包含未知字段")
        if "imports" in config:
            imports = config["imports"]
            if not isinstance(imports, dict) or set(imports) != {"roots"} or not isinstance(imports["roots"], list):
                raise ValueError("素材根目录配置无效")
            seen_root_ids = set()
            for root in imports["roots"]:
                if not isinstance(root, dict) or set(root) != {"id", "path"}:
                    raise ValueError("素材根目录配置无效")
                root_id, root_path = root["id"], root["path"]
                if not isinstance(root_id, str) or not root_id.strip() or root_id in seen_root_ids:
                    raise ValueError("素材根目录 id 必须非空且唯一")
                if not isinstance(root_path, str) or not root_path.strip():
                    raise ValueError("素材根目录路径无效")
                if not Path(root_path).expanduser().is_absolute():
                    raise ValueError("素材根目录路径必须为绝对路径")
                seen_root_ids.add(root_id)
        server = config["server"]
        storage = config["storage"]
        comfyui = config["comfyui"]
        if set(server) != {"host", "port"} or set(storage) != {"data_dir"} or set(comfyui) != {"allowed_origins"}:
            raise ValueError("配置字段与约定不符")
        host, port = server["host"], server["port"]
        origins, data_dir = comfyui["allowed_origins"], storage["data_dir"]
        if not isinstance(host, str) or not ipaddress.ip_address(host).is_loopback or type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("server 配置无效")
        if not isinstance(data_dir, str) or not data_dir.strip():
            raise ValueError("storage.data_dir 配置无效")
        if not isinstance(origins, list) or not origins:
            raise ValueError("comfyui.allowed_origins 配置无效")
        for origin in origins:
            from urllib.parse import urlsplit
            parsed = urlsplit(origin) if isinstance(origin, str) else None
            if parsed is None or parsed.scheme != "http" or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
                raise ValueError("allowed_origins 配置无效")
            if parsed.hostname != "localhost" and not ipaddress.ip_address(parsed.hostname).is_loopback:
                raise ValueError("allowed_origins 只能包含本机回环地址")
            if parsed.port is None or not 1 <= parsed.port <= 65535:
                raise ValueError("allowed_origins 配置无效")
        data_path = Path(data_dir).expanduser()
        if not data_path.is_absolute():
            data_path = config_path.parent / data_path
        token_path = data_path / "service.token"
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
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        return f"http://{host}:{port}", set(origins), token
    except (OSError, KeyError, TypeError, ValueError, tomllib.TOMLDecodeError) as exc:
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


async def forward(request: web.Request, path_template: str, service_manager=None) -> web.Response:
    request_id = str(uuid4())
    try:
        if service_manager is not None:
            try:
                await asyncio.to_thread(service_manager.ensure_available)
            except ProxyError as exc:
                return _error_response(request_id, exc.status, exc.code, exc.message)
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


def register_proxy_routes(routes: web.RouteTableDef, service_manager=None) -> None:
    for method, public_path, upstream_path in ROUTES:
        async def handler(
            request: web.Request,
            template: str = upstream_path,
            manager=service_manager,
        ) -> web.Response:
            return await forward(request, template, manager)
        routes.route(method, BASE_PATH + public_path)(handler)
