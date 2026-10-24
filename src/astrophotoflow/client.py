from __future__ import annotations

import os
from pathlib import Path
import tomllib
from typing import Any

import httpx


CONFIG_PATH = Path.home() / ".config" / "astrophotoflow" / "config.toml"


class ServiceApiError(RuntimeError):
    def __init__(self, status: int, code: str, message: str, request_id: str | None, fields: list[dict] | None = None):
        self.status = status
        self.code = code
        self.request_id = request_id
        self.fields = fields or []
        suffix = f" (request_id={request_id})" if request_id else ""
        field_text = f" fields={self.fields}" if self.fields else ""
        super().__init__(f"{code} (HTTP {status}): {message}{field_text}{suffix}")


def config_path() -> Path:
    configured = os.environ.get("ASTROPHOTOFLOW_CONFIG")
    pointer = CONFIG_PATH.parent / "active-workspace"
    if configured:
        return Path(configured).expanduser()
    if pointer.is_file():
        return Path(pointer.read_text(encoding="utf-8").strip()).expanduser()
    return CONFIG_PATH


class AssetClient:
    def __init__(self, path: Path | None = None):
        self.config_path = (path or config_path()).resolve()
        with self.config_path.open("rb") as stream:
            config = tomllib.load(stream)
        server = config["server"]
        storage = config["storage"]
        data_dir = Path(storage["data_dir"]).expanduser()
        if not data_dir.is_absolute():
            data_dir = self.config_path.parent / data_dir
        token = (data_dir / "service.token").read_text(encoding="utf-8").strip()
        if not token:
            raise ValueError("AstroPhotoFlow 本机服务令牌为空。")
        self.base_url = f"http://{server['host']}:{server['port']}/api/v1"
        self.client = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=30,
        )

    def request(self, method: str, path: str, *, params=None, json=None) -> Any:
        response = self.client.request(method, path, params=params, json=json)
        return self._result(response)

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

    def import_photo(self, path: Path) -> dict[str, Any]:
        path = path.expanduser().resolve(strict=True)
        if not path.is_file():
            raise ValueError(f"不是文件：{path}")
        create = self.request(
            "POST", "/uploads",
            json={"files": [{"name": path.name, "size": path.stat().st_size}],
                  "classification": {"frame_class": "subframe", "frame_type": "light"}},
        )
        task_id = str(create["task_id"])
        with path.open("rb") as stream:
            def chunks():
                while chunk := stream.read(1024 * 1024):
                    yield chunk

            response = self.client.put(f"/uploads/{task_id}/0", content=chunks(), timeout=None)
        self._result(response)
        self.request("POST", f"/uploads/{task_id}/start")
        return {"task_id": task_id, "status": "queued"}

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "AssetClient":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
