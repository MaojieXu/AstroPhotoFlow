import logging
import asyncio
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Request
import httpx
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from astrophotoflow.core.database.db import Database
from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.http import authenticate
from astrophotoflow.core.config import Settings
from astrophotoflow.modules.data.public import DisplayPreviews, import_workers, data_busy
from astrophotoflow.contracts.workbench import BusyState
from astrophotoflow.contracts.common import StrictModel
from typing import Literal
from astrophotoflow.modules.data.routes import router as data_router
from astrophotoflow.interfaces.http import system


logger = logging.getLogger("astrophotoflow.service")


class MaintenanceAction(StrictModel):
    action: Literal["enter", "release"]


def create_app(settings: Settings, token: str) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        with import_workers(settings) as workers:
            app.state.import_workers = workers
            app.state.display_previews = DisplayPreviews(app.state.database, settings, workers[1])
            yield

    app = FastAPI(lifespan=lifespan, title="AstroPhotoFlow Asset Service", version="1.0.0", docs_url=None, redoc_url=None)
    app.state.settings = settings
    app.state.token = token
    app.state.database = Database(settings.database_path)
    app.state.maintenance_lock = asyncio.Lock()
    app.state.maintenance = False

    @app.post("/internal/maintenance", dependencies=[Depends(authenticate)], include_in_schema=False)
    async def maintenance(body: MaintenanceAction):
        async with app.state.maintenance_lock:
            if body.action == "release":
                app.state.maintenance = False
                return BusyState(busy=False, unknown=False, blockers=[])
            state = data_busy(app.state.database)
            try:
                async with httpx.AsyncClient(timeout=3) as client:
                    response = await client.get(settings.allowed_origins[0] + "/queue")
                    response.raise_for_status()
                    queue = response.json()
                    running, pending = queue["queue_running"], queue["queue_pending"]
                    if not isinstance(running, list) or not isinstance(pending, list):
                        raise ValueError("原生队列格式无效。")
                    if running or pending:
                        state.busy = True
                        state.blockers.append("原生队列仍有执行或排队任务")
            except (httpx.HTTPError, KeyError, TypeError, ValueError):
                state.unknown = True
                state.blockers.append("无法确认原生队列空闲")
            app.state.maintenance = not (state.busy or state.unknown)
            return state

    @app.post("/internal/shutdown", dependencies=[Depends(authenticate)], include_in_schema=False)
    async def shutdown(request: Request):
        async with app.state.maintenance_lock:
            app.state.maintenance = True
            request.app.state.shutdown()
        return {"status": "stopping"}

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        try:
            request.state.request_id = UUID(request.headers.get("X-Request-ID", ""))
        except ValueError:
            request.state.request_id = uuid4()
        response = await call_next(request)
        response.headers["X-Request-ID"] = str(request.state.request_id)
        return response

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError):
        return _error_response(request, exc.status_code, exc.code, exc.message, exc.fields)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        fields = []
        for error in exc.errors():
            path = ".".join(str(part) for part in error.get("loc", ()) if part not in ("body", "query", "path"))
            if error.get("loc", (None,))[0] == "query":
                path = "query." + path
            fields.append({"path": path, "message": "请求字段无效。"})
        return _error_response(request, 422, "VALIDATION_ERROR", "请求数据不符合接口契约。", fields)

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        code = "RESOURCE_NOT_FOUND" if exc.status_code == 404 else "METHOD_NOT_ALLOWED" if exc.status_code == 405 else "INTERNAL_ERROR"
        message = "未找到请求的资源。" if exc.status_code == 404 else "该资源不支持此 HTTP 方法。" if exc.status_code == 405 else "请求失败。"
        return _error_response(request, exc.status_code, code, message, [])

    @app.exception_handler(Exception)
    async def internal_error_handler(request: Request, exc: Exception):
        logger.exception("request failed request_id=%s", getattr(request.state, "request_id", "unknown"))
        return _error_response(request, 500, "INTERNAL_ERROR", "服务发生未预期错误。", [])

    app.include_router(system.router)
    app.include_router(data_router)
    return app


def _error_response(request: Request, status_code: int, code: str, message: str, fields: list[dict[str, str]]):
    from fastapi.responses import JSONResponse

    rid = getattr(request.state, "request_id", uuid4())
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message, "fields": fields}, "request_id": str(rid)}, headers={"X-Request-ID": str(rid)})
