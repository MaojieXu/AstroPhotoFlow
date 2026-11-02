"""One HTTP error envelope and request identity for every route."""

import logging
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from astrophotoflow.contracts.common import ErrorEnvelope
from astrophotoflow.core.config import ConfigurationError
from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.localization import error_fields, error_message, localized_error, workspace_locale

logger = logging.getLogger("astrophotoflow.service")


def register_error_handlers(app: FastAPI) -> None:
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
        fields = error_fields(_response_locale(request), exc) if exc.message_key else [*error_fields(_response_locale(request), exc), {'path': '', 'message': exc.message}]
        return error_response(request, exc.status_code, exc.code, exc.message, fields,
                               message_key=exc.message_key, message_params=exc.message_params)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        fields = []
        for error in exc.errors():
            path = ".".join(str(part) for part in error.get("loc", ()) if part not in ("body", "query", "path"))
            if error.get("loc", (None,))[0] == "query":
                path = "query." + path
            fields.append({"path": path, "message": error_message(_response_locale(request), 'VALIDATION_ERROR', 'invalid_field')})
        return error_response(request, 422, "VALIDATION_ERROR", "请求数据不符合接口契约。", fields, message_key='validation_error')

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        code = "RESOURCE_NOT_FOUND" if exc.status_code == 404 else "METHOD_NOT_ALLOWED" if exc.status_code == 405 else "INTERNAL_ERROR"
        message = "未找到请求的资源。" if exc.status_code == 404 else "该资源不支持此 HTTP 方法。" if exc.status_code == 405 else "请求失败。"
        key = 'the_requested_resource_was_not_found' if exc.status_code == 404 else 'method_not_allowed' if exc.status_code == 405 else 'request_failed'
        return error_response(request, exc.status_code, code, message, [], message_key=key)

    @app.exception_handler(Exception)
    async def internal_error_handler(request: Request, exc: Exception):
        logger.exception("request failed request_id=%s", getattr(request.state, "request_id", "unknown"))
        return error_response(request, 500, "INTERNAL_ERROR", "服务发生未预期错误。", [], message_key='internal_error')



def _response_locale(request: Request):
    try:
        return workspace_locale(request.app.state.settings.workspace)
    except ConfigurationError:
        return 'en'


def error_response(request: Request, status_code: int, code: str, message: str, fields: list[dict[str, str]],
                    *, message_key: str | None = None, message_params: dict | None = None):
    from fastapi.responses import JSONResponse

    detail = localized_error(_response_locale(request), code, message_key, parameters=message_params, fields=fields)
    rid = getattr(request.state, "request_id", uuid4())
    envelope = ErrorEnvelope(error=detail, request_id=rid)
    return JSONResponse(status_code=status_code, content=envelope.model_dump(mode="json"), headers={"X-Request-ID": str(rid)})
