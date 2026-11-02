"""One error translation policy, before mounted execution masks failures."""

import json
import logging
from collections.abc import Callable
from functools import wraps

import httpx
from fastmcp.exceptions import NotFoundError, ToolError
from fastmcp.server.middleware import Middleware, MiddlewareContext

from astrophotoflow.contracts.common import ErrorDetail
from astrophotoflow.core.localization import localized_error
from astrophotoflow.interfaces.client.errors import ServiceApiError

logger = logging.getLogger(__name__)


def tool_error(detail: ErrorDetail, *, request_id=None) -> ToolError:
    return ToolError(json.dumps({"error": detail.model_dump(mode="json"), "request_id": request_id}, ensure_ascii=False))


def translate_error(exc: Exception, source: str) -> ToolError:
    if isinstance(exc, NotFoundError):
        return tool_error(localized_error('en', 'TOOL_NOT_FOUND', 'mcp_tool_not_found', fields=[{'path': 'diagnostic', 'message': str(exc)}]))
    if isinstance(exc, ServiceApiError):
        return tool_error(exc.detail, request_id=exc.request_id)
    if isinstance(exc, httpx.TimeoutException):
        return tool_error(localized_error('en', 'TRANSPORT_TIMEOUT', 'mcp_transport_timeout'))
    if isinstance(exc, httpx.HTTPError):
        return tool_error(localized_error('en', 'SERVICE_UNAVAILABLE', 'mcp_service_unavailable'))
    if isinstance(exc, (OSError, ValueError)):
        return tool_error(localized_error('en', 'INVALID_REQUEST', 'mcp_invalid_request', fields=[{'path': 'diagnostic', 'message': str(exc)}]))
    logger.exception("MCP operation failed: %s", source)
    return tool_error(localized_error('en', 'INTERNAL_ERROR', 'mcp_unexpected_failure'))


class ServiceErrors(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        try:
            return await call_next(context)
        except ToolError:
            raise
        except Exception as exc:
            raise translate_error(exc, context.message.name) from exc


def service_errors[**P, R](function: Callable[P, R]) -> Callable[P, R]:
    @wraps(function)
    def invoke(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return function(*args, **kwargs)
        except ToolError:
            raise
        except Exception as exc:
            raise translate_error(exc, function.__name__) from exc

    return invoke
