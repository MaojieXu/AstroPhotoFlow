"""Own the configured HTTPX connection and JSON request lifecycle."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Self, overload

import httpx
from pydantic import BaseModel, JsonValue, TypeAdapter, ValidationError

from astrophotoflow.core.config import load_running_settings, load_settings, resolve_config_path
from astrophotoflow.interfaces.client.errors import ServiceApiError


class HttpTransport:
    def __init__(self, path: Path | None = None):
        self.config_path = resolve_config_path(path)
        workspace = self.config_path.parent
        process_path = workspace / "run/processes.json"
        active = process_path.is_file() and bool(json.loads(process_path.read_text(encoding="utf-8"))["processes"])
        settings = load_running_settings(workspace) if active else load_settings(self.config_path)
        token = settings.token_path.read_text(encoding="utf-8").strip()
        if not token:
            raise ValueError("AstroPhotoFlow 本机服务令牌为空。")
        self.base_url = settings.service_url + "/api/v1"
        self.client = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=30,
        )

    @overload
    def request[T](self, method: str, path: str, *, adapter: TypeAdapter[T], params=None, json=None) -> T: ...

    @overload
    def request(self, method: str, path: str, *, params=None, json=None, adapter: None = None) -> JsonValue: ...

    def request(self, method: str, path: str, *, params=None, json=None, adapter: TypeAdapter[Any] | None = None) -> Any:
        if isinstance(json, BaseModel):
            json = json.model_dump(mode="json", exclude_unset=True)
        if params is not None:
            params = {key: value for key, value in params.items() if value is not None}
        response = self.client.request(method, path, params=params, json=json)
        return self._result(response, adapter=adapter)

    @overload
    def _result[T](self, response: httpx.Response, *, adapter: TypeAdapter[T]) -> T: ...

    @overload
    def _result(self, response: httpx.Response, *, adapter: None = None) -> JsonValue: ...

    def _result(self, response: httpx.Response, *, adapter: TypeAdapter[Any] | None = None) -> Any:
        try:
            body = response.json()
        except ValueError as exc:
            raise ServiceApiError(response.status_code, "INVALID_RESPONSE", "服务响应不是有效 JSON。", response.headers.get("X-Request-ID")) from exc
        if not response.is_success:
            if not isinstance(body, dict) or not isinstance(body.get("error"), dict):
                raise ServiceApiError(
                    response.status_code, "INVALID_RESPONSE", "服务错误响应缺少错误对象。",
                    response.headers.get("X-Request-ID"),
                )
            error = body["error"]
            raise ServiceApiError(
                response.status_code,
                str(error.get("code", "SERVICE_ERROR")),
                str(error.get("message", "AstroPhotoFlow 服务请求失败。")),
                body.get("request_id") or response.headers.get("X-Request-ID"),
                error.get("fields"),
            )
        if adapter is None:
            return body
        try:
            # JSON mode preserves strict contract handling of dates and UUIDs.
            return adapter.validate_json(response.content)
        except ValidationError as exc:
            raise ServiceApiError(
                response.status_code, "INVALID_RESPONSE", "服务成功响应不符合接口契约。",
                response.headers.get("X-Request-ID"),
                [{"path": ".".join(map(str, issue["loc"])), "message": issue["msg"]}
                 for issue in exc.errors(include_url=False, include_input=False)],
            ) from exc

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
