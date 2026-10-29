from typing import Any

from astrophotoflow.contracts.workflows import CanvasAddRequest, CanvasGraphRequest
from uuid import uuid4


class CanvasOperations:
    def list_canvas_pages(self) -> list[dict[str, Any]]:
        return self.request("GET", "/canvas/pages")

    def add_canvas_data(self, body: CanvasAddRequest) -> dict[str, Any]:
        return self.request("POST", "/canvas/requests", json=body)

    def get_canvas_request(self, operation_id: str) -> dict[str, Any]:
        return self.request("GET", f"/canvas/requests/{operation_id}")

    def list_nodes(self, query: str | None = None):
        return self.request('GET', '/nodes', params={'query': query} if query else {})

    def get_node(self, definition_id: str):
        return self.request('GET', f'/nodes/{definition_id}')

    def get_canvas(self, page_id: str):
        page = next((item for item in self.list_canvas_pages() if str(item['page_id']) == str(page_id)), None)
        if page is None:
            raise ValueError('Canvas is offline; no graph snapshot is available.')
        body = CanvasGraphRequest(operation_id=uuid4(), page_id=page['page_id'], workflow_id=page['workflow_id'],
                                  graph_id=page['graph_id'], content_token=page['content_token'],
                                  control_token=page['control_token'], edit={'action': 'inspect'})
        return self.request('POST', '/canvas/graph', json=body)

    def edit_canvas(self, body: CanvasGraphRequest):
        return self.request('POST', '/canvas/graph', json=body)
