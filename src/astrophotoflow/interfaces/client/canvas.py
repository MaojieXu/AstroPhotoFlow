from typing import Any

from astrophotoflow.contracts.workflows import CanvasAddRequest


class CanvasOperations:
    def list_canvas_pages(self) -> list[dict[str, Any]]:
        return self.request("GET", "/canvas/pages")

    def add_canvas_data(self, body: CanvasAddRequest) -> dict[str, Any]:
        return self.request("POST", "/canvas/requests", json=body)

    def get_canvas_request(self, operation_id: str) -> dict[str, Any]:
        return self.request("GET", f"/canvas/requests/{operation_id}")
