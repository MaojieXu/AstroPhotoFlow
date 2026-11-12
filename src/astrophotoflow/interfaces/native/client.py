"""Typed native canvas protocol over the serving application's HTTP pool."""

import json
from dataclasses import dataclass, field
from uuid import UUID

import httpx
from pydantic import TypeAdapter

from astrophotoflow.contracts.canvas import (
    CanvasAddResult,
    CanvasPageOut,
    NativeCanvasCommand,
    NativeCanvasGraphCommand,
)
from astrophotoflow.contracts.common import ErrorDetail
from astrophotoflow.core.errors import ApiError


@dataclass(frozen=True)
class NativeClient:
    http: httpx.AsyncClient
    origin: str
    token: str = field(repr=False)

    async def _request[T](self, method: str, path: str, adapter: TypeAdapter[T], body=None) -> T:
        try:
            response = await self.http.request(
                method, self.origin + "/astrophotoflow/internal/canvas" + path,
                json=body, headers={"Authorization": f"Bearer {self.token}"}, timeout=10,
            )
            if not response.is_success:
                error = TypeAdapter(ErrorDetail).validate_json(json.dumps(response.json()["error"]))
                raise ApiError(response.status_code, error.code, error.message, fields=error.fields,
                               message_key="forwarded_service_error", message_params={"message": error.message})
            return adapter.validate_json(response.content)
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise ApiError(503, "CANVAS_CONNECTION_UNKNOWN", "无法核对画布结果；请查询同一 operation_id，不要自动重发。",
                           message_key="cannot_confirm_the_canvas_result_query_the_same_operation_id_do_not_automat") from exc

    async def list_pages(self) -> list[CanvasPageOut]:
        return await self._request("GET", "/pages", TypeAdapter(list[CanvasPageOut]))

    async def send(self, command: NativeCanvasCommand | NativeCanvasGraphCommand) -> CanvasAddResult:
        result = await self._request("POST", "/requests", TypeAdapter(CanvasAddResult), command.model_dump(mode="json"))
        expected = command.request
        if (result.operation_id, result.page_id, result.workflow_id, result.graph_id) != (expected.operation_id, expected.page_id, expected.workflow_id, expected.graph_id):
            raise ApiError(503, "CANVAS_CONNECTION_UNKNOWN", "原生回执身份不匹配，请继续核对原操作。", message_key='native_receipt_identity_mismatch')
        return result

    async def receipt(self, operation_id: UUID) -> CanvasAddResult:
        result = await self._request("GET", f"/requests/{operation_id}", TypeAdapter(CanvasAddResult))
        if result.operation_id != operation_id:
            raise ApiError(503, "CANVAS_CONNECTION_UNKNOWN", "原生回执身份不匹配，请继续核对原操作。", message_key='native_receipt_identity_mismatch')
        return result
