import asyncio
from pathlib import Path

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
import pytest

from astrophotoflow import config as app_config
from astrophotoflow.comfyui import proxy


def config_file(path: Path, port: int, data_dir: Path, origins: list[str], roots: list[tuple[str, str]] = ()) -> None:
    lines = [
        "[server]", 'host = "127.0.0.1"', f"port = {port}", "",
        "[storage]", f'data_dir = "{data_dir.as_posix()}"', "",
        "[comfyui]", "allowed_origins = [" + ", ".join(f'"{origin}"' for origin in origins) + "]", ""
    ]
    for root_id, root_path in roots:
        lines.extend(["[[imports.roots]]", f'id = "{root_id}"', f'path = "{Path(root_path).as_posix()}"', ""])
    path.write_text("\n".join(lines))


def test_proxy_whitelist_origin_headers_and_upstream_status(tmp_path, monkeypatch):
    async def run():
        seen = {}

        async def upstream_handler(request):
            seen["path"] = request.path
            seen["query"] = request.query.get("q")
            seen["encoded_text"] = request.query.get("text")
            seen["labels"] = request.query.getall("label", [])
            seen["offset"] = request.query.get("offset")
            seen["authorization"] = request.headers.get("Authorization")
            seen["cookie"] = request.headers.get("Cookie")
            seen["client_header"] = request.headers.get("X-Client-Actor")
            if request.method == "DELETE":
                seen["delete_body"] = await request.json()
            if request.method == "PUT":
                seen["upload_size"] = 0
                async for chunk in request.content.iter_chunked(1024 * 1024):
                    seen["upload_size"] += len(chunk)
                return web.json_response({"received": seen["upload_size"]})
            request_id = request.headers["X-Request-ID"]
            if request.path.endswith("/health"):
                return web.json_response({
                    "error": {"code": "AUTHENTICATION_REQUIRED", "message": "bad token", "fields": []},
                    "request_id": request_id
                }, status=401, headers={"X-Request-ID": request_id})
            return web.json_response({"items": [], "total": 0, "limit": 50, "offset": 0}, headers={"X-Request-ID": request_id})

        upstream_app = web.Application()
        upstream_app.router.add_route("*", "/api/v1/{tail:.*}", upstream_handler)
        upstream_client = TestClient(TestServer(upstream_app))
        await upstream_client.start_server()
        upstream = upstream_client.server

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "service.token").write_text("server-only-token")
        public_app = web.Application(client_max_size=100 * 1024 * 1024)
        routes = web.RouteTableDef()
        proxy.register_proxy_routes(routes)
        public_app.add_routes(routes)
        api_routes = web.RouteTableDef()
        for route in routes:
            api_routes.route(route.method, "/api" + route.path)(route.handler)
        public_app.add_routes(api_routes)
        public = TestServer(public_app)
        client = TestClient(public)
        await client.start_server()
        origin = str(client.make_url("/")).rstrip("/")
        config = tmp_path / "config.toml"
        config_file(config, upstream.port, data_dir, [origin], [("astrodata", str(tmp_path / "astrodata"))])
        monkeypatch.setattr(app_config, "CONFIG_PATH", config)

        try:
            response = await client.get(
                "/api" + proxy.BASE_PATH + "/projects",
                params=[("q", "M31 #2"), ("text", "literal%26"), ("label", "one"), ("label", "two"), ("limit", "50"), ("offset", "0")],
                headers={"Origin": origin, "Cookie": "browser-cookie", "Authorization": "Bearer browser-secret", "X-Client-Actor": "admin"}
            )
            assert response.status == 200
            assert response.headers["X-Request-ID"]
            assert seen == {
                "path": "/api/v1/projects", "query": "M31 #2", "encoded_text": "literal%26",
                "labels": ["one", "two"], "offset": "0", "authorization": "Bearer server-only-token",
                "cookie": None, "client_header": None
            }

            blocked = await client.get("/api" + proxy.BASE_PATH + "/projects", headers={"Origin": "http://evil.invalid"})
            assert blocked.status == 403
            assert (await blocked.json())["error"]["code"] == "ORIGIN_NOT_ALLOWED"

            no_origin = await client.get("/api" + proxy.BASE_PATH + "/projects", headers={"Sec-Fetch-Site": "same-origin"})
            assert no_origin.status == 200
            blocked_no_origin = await client.get("/api" + proxy.BASE_PATH + "/projects")
            assert blocked_no_origin.status == 403

            auth_failure = await client.get("/api" + proxy.BASE_PATH + "/health", headers={"Origin": origin})
            assert auth_failure.status == 401
            assert (await auth_failure.json())["error"]["code"] == "AUTHENTICATION_REQUIRED"

            deleted = await client.request(
                "DELETE",
                "/api" + proxy.BASE_PATH + "/projects/project/asset-references/reference",
                json={"base_revision": 4},
                headers={"Origin": origin},
            )
            assert deleted.status == 200
            assert seen["delete_body"] == {"base_revision": 4}

            library_delete_body = {"items": [{"entry_type":"asset","id":"asset-id","revision":3}]}
            library_deleted = await client.request(
                "DELETE", "/api" + proxy.BASE_PATH + "/library/items", json=library_delete_body,
                headers={"Origin": origin},
            )
            assert library_deleted.status == 200
            assert seen["delete_body"] == library_delete_body

            async def large_upload():
                chunk = b"x" * (1024 * 1024)
                for _ in range(101):
                    yield chunk

            uploaded = await client.put(
                "/api" + proxy.BASE_PATH + "/uploads/00000000-0000-0000-0000-000000000001/0",
                data=large_upload(), headers={"Origin": origin, "Content-Type": "application/octet-stream"},
            )
            assert uploaded.status == 200
            assert (await uploaded.json())["received"] == 101 * 1024 * 1024

            for base in (
                "/library/assets/asset/versions/version/previews/display",
                "/projects/project/asset-references/reference/previews/display",
            ):
                scheduled = await client.post("/api" + proxy.BASE_PATH + base, json={}, headers={"Origin": origin})
                assert scheduled.status == 200
                assert seen["path"] == "/api/v1" + base
                assert seen["authorization"] == "Bearer server-only-token"
                polled = await client.get("/api" + proxy.BASE_PATH + base + "/status", headers={"Origin": origin})
                assert polled.status == 200
                assert seen["path"] == "/api/v1" + base + "/status"
                blocked = await client.post("/api" + proxy.BASE_PATH + base, json={}, headers={"Origin": "http://evil.invalid"})
                assert blocked.status == 403

            assert len(proxy.ROUTES) == 76
            assert all(
                method == "GET" or (method == "POST" and path == "/datasets/{dataset_id}/versions")
                or (method == "PATCH" and path == "/datasets/{dataset_id}/member-parameters")
                or (method == "POST" and path in {"/library/assets/{asset_id}/versions/{version_id}/previews/display", "/projects/{project_id}/asset-references/{reference_id}/previews/display"})
                for method, path, _ in proxy.ROUTES
                if "/versions" in path or path.endswith("/previews/{size}")
            )
            assert ("PATCH", "/library/assets/{asset_id}", "/library/assets/{asset_id}") in proxy.ROUTES
            assert ("DELETE", "/library/items", "/library/items") in proxy.ROUTES
            assert ("POST", "/projects/{project_id}/asset-references", "/projects/{project_id}/asset-references") in proxy.ROUTES
            assert ("DELETE", "/projects/{project_id}/asset-references/{reference_id}", "/projects/{project_id}/asset-references/{reference_id}") in proxy.ROUTES
            assert not any(
                method in {"POST", "PATCH", "PUT", "DELETE"}
                and "/versions" in path
                and path != "/datasets/{dataset_id}/versions"
                and path != "/datasets/{dataset_id}/member-parameters"
                and not (method == "POST" and path == "/library/assets/{asset_id}/versions/{version_id}/previews/display")
                for method, path, _ in proxy.ROUTES
            )
        finally:
            await client.close()
            await upstream_client.close()

    asyncio.run(run())


def test_proxy_distinguishes_missing_config_and_unavailable_service(tmp_path, monkeypatch):
    async def run():
        app = web.Application()
        routes = web.RouteTableDef()
        proxy.register_proxy_routes(routes)
        app.add_routes(routes)
        api_routes = web.RouteTableDef()
        for route in routes:
            api_routes.route(route.method, "/api" + route.path)(route.handler)
        app.add_routes(api_routes)
        client = TestClient(TestServer(app))
        await client.start_server()
        origin = str(client.make_url("/")).rstrip("/")
        missing = tmp_path / "missing.toml"
        monkeypatch.setattr(app_config, "CONFIG_PATH", missing)
        try:
            response = await client.get("/api" + proxy.BASE_PATH + "/health", headers={"Origin": origin})
            assert response.status == 503
            assert (await response.json())["error"]["code"] == "SERVICE_NOT_CONFIGURED"

            data_dir = tmp_path / "data"
            data_dir.mkdir()
            (data_dir / "service.token").write_text("token")
            config = tmp_path / "config.toml"
            config_file(config, 1, data_dir, [origin])
            monkeypatch.setattr(app_config, "CONFIG_PATH", config)
            response = await client.get("/api" + proxy.BASE_PATH + "/health", headers={"Origin": origin})
            assert response.status == 503
            assert (await response.json())["error"]["code"] == "SERVICE_UNAVAILABLE"

            class TimeoutContext:
                async def __aenter__(self):
                    raise asyncio.TimeoutError()
                async def __aexit__(self, *_args):
                    return None
            class TimeoutClient:
                def __init__(self, timeout):
                    assert timeout.total == 10
                async def __aenter__(self):
                    return self
                async def __aexit__(self, *_args):
                    return None
                def request(self, *_args, **_kwargs):
                    return TimeoutContext()
            monkeypatch.setattr(proxy.aiohttp, "ClientSession", TimeoutClient)
            response = await client.get("/api" + proxy.BASE_PATH + "/health", headers={"Origin": origin})
            assert response.status == 504
            assert (await response.json())["error"]["code"] == "SERVICE_TIMEOUT"
        finally:
            await client.close()

    asyncio.run(run())


def test_proxy_rejects_relative_import_roots(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "service.token").write_text("token")
    config = tmp_path / "config.toml"
    config_file(config, 8190, data_dir, ["http://127.0.0.1:8188"], [("bad-root", "relative/path")])
    monkeypatch.setattr(app_config, "CONFIG_PATH", config)
    with pytest.raises(proxy.ProxyError) as error:
        proxy._configuration()
    assert error.value.message == "AstroPhotoFlow 本机服务配置或令牌不可用。"
    assert "素材根目录路径必须为绝对路径" in str(error.value.__cause__)



def test_proxy_returns_service_manager_startup_error(tmp_path):
    async def run():
        class FailedManager:
            def ensure_available(self):
                raise proxy.ProxyError(503, "SERVICE_UNAVAILABLE", "uv 环境未准备。")

        app = web.Application()
        routes = web.RouteTableDef()
        proxy.register_proxy_routes(routes, FailedManager())
        app.add_routes(routes)
        api_routes = web.RouteTableDef()
        for route in routes:
            api_routes.route(route.method, "/api" + route.path)(route.handler)
        app.add_routes(api_routes)
        client = TestClient(TestServer(app))
        await client.start_server()
        origin = str(client.make_url("/")).rstrip("/")
        try:
            response = await client.get(
                "/api" + proxy.BASE_PATH + "/health",
                headers={"Origin": origin},
            )
            body = await response.json()
            assert response.status == 503
            assert body["error"]["code"] == "SERVICE_UNAVAILABLE"
            assert body["error"]["message"] == "uv 环境未准备。"
            assert body["request_id"] == response.headers["X-Request-ID"]
        finally:
            await client.close()

    asyncio.run(run())
