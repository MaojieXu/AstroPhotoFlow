"""Shared error for all HTTP-backed service capabilities."""

from astrophotoflow.core.localization import forwarded_error


class ServiceApiError(RuntimeError):
    def __init__(self, status: int, code: str, message: str, request_id: str | None, fields: list[dict[str, str]] | None = None):
        self.status = status
        self.detail = forwarded_error(code, message, fields=fields)
        self.request_id = request_id
        suffix = f" (request_id={request_id})" if request_id else ""
        field_text = f" fields={self.fields}" if self.fields else ""
        super().__init__(f"{code} (HTTP {status}): {message}{field_text}{suffix}")

    @property
    def code(self) -> str:
        return self.detail.code

    @property
    def fields(self) -> list[dict[str, str]]:
        return self.detail.fields

