from __future__ import annotations

from pathlib import Path
import json
from typing import Any

import httpx
from pydantic import BaseModel
from astrophotoflow.contracts.workbench import ConfigSave, ConfigState

from astrophotoflow.interfaces.client.imports import ImportOperations
from astrophotoflow.interfaces.client.library import LibraryOperations
from astrophotoflow.interfaces.client.organization import OrganizationOperations


from astrophotoflow.core.config import load_settings, load_running_settings, resolve_config_path


class ServiceApiError(RuntimeError):
    def __init__(self, status: int, code: str, message: str, request_id: str | None, fields: list[dict] | None = None):
        self.status = status
        self.code = code
        self.request_id = request_id
        self.fields = fields or []
        suffix = f" (request_id={request_id})" if request_id else ""
        field_text = f" fields={self.fields}" if self.fields else ""
        super().__init__(f"{code} (HTTP {status}): {message}{field_text}{suffix}")


class AssetClient(ImportOperations, LibraryOperations, OrganizationOperations):
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

    def request(self, method: str, path: str, *, params=None, json=None) -> Any:
        if isinstance(json, BaseModel):
            json = json.model_dump(mode="json", exclude_unset=True)
        if params is not None:
            params = {key: value for key, value in params.items() if value is not None}
        response = self.client.request(method, path, params=params, json=json)
        return self._result(response)

    def get_workbench_configuration(self) -> ConfigState:
        return ConfigState.model_validate(self.request("GET", "/settings/workbench"))

    def save_workbench_configuration(self, body: ConfigSave) -> ConfigState:
        return ConfigState.model_validate(self.request("PATCH", "/settings/workbench", json=body))

    def _result(self, response: httpx.Response) -> Any:
        try:
            body = response.json()
        except ValueError as exc:
            raise ServiceApiError(response.status_code, "INVALID_RESPONSE", "服务响应不是有效 JSON。", response.headers.get("X-Request-ID")) from exc
        if not response.is_success:
            error = body.get("error", {}) if isinstance(body, dict) else {}
            raise ServiceApiError(
                response.status_code,
                str(error.get("code", "SERVICE_ERROR")),
                str(error.get("message", "AstroPhotoFlow 服务请求失败。")),
                body.get("request_id") or response.headers.get("X-Request-ID"),
                error.get("fields"),
            )
        return body

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "AssetClient":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
