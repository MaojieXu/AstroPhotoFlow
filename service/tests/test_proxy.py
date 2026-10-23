import asyncio
from pathlib import Path
import sys

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.astrophotoflow import proxy


def config_file(path: Path, port: int, data_dir: Path, origins: list[str]) -> None:
    lines = [
        "[server]", 'host = "127.0.0.1"', f"port = {port}", "",
        "[storage]", f'data_dir = "{data_dir}"', "",
        "[comfyui]", "allowed_origins = [" + ", ".join(f'"{origin}"' for origin in origins) + "]", ""
    ]
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
        public_app = web.Application()
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
        config_file(config, upstream.port, data_dir, [origin])
        monkeypatch.setattr(proxy, "CONFIG_PATH", config)

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

            assert len(proxy.ROUTES) == 18
            assert all(method == "GET" for method, path, _ in proxy.ROUTES if "assets" in path or "asset-references" in path)
            assert not any(method in {"POST", "PATCH", "PUT", "DELETE"} and "assets" in path for method, path, _ in proxy.ROUTES)
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
        monkeypatch.setattr(proxy, "CONFIG_PATH", missing)
        try:
            response = await client.get("/api" + proxy.BASE_PATH + "/health", headers={"Origin": origin})
            assert response.status == 503
            assert (await response.json())["error"]["code"] == "SERVICE_NOT_CONFIGURED"

            data_dir = tmp_path / "data"
            data_dir.mkdir()
            (data_dir / "service.token").write_text("token")
            config = tmp_path / "config.toml"
            config_file(config, 1, data_dir, [origin])
            monkeypatch.setattr(proxy, "CONFIG_PATH", config)
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
