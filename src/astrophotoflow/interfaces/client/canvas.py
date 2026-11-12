from uuid import uuid4

from pydantic import TypeAdapter

from astrophotoflow.contracts.canvas import CanvasAddRequest, CanvasAddResult, CanvasGraphRequest, CanvasPageOut
from astrophotoflow.contracts.nodes import NodeCapability


class CanvasOperations:
    def list_canvas_pages(self) -> list[CanvasPageOut]:
        return self.request("GET", "/canvas/pages", adapter=TypeAdapter(list[CanvasPageOut]))

    def add_canvas_data(self, body: CanvasAddRequest) -> CanvasAddResult:
        return self.request("POST", "/canvas/requests", json=body, adapter=TypeAdapter(CanvasAddResult))

    def get_canvas_request(self, operation_id: str) -> CanvasAddResult:
        return self.request("GET", f"/canvas/requests/{operation_id}", adapter=TypeAdapter(CanvasAddResult))

    def list_nodes(self, query: str | None = None) -> list[NodeCapability]:
        return self.request('GET', '/nodes', params={'query': query} if query else {}, adapter=TypeAdapter(list[NodeCapability]))

    def get_node(self, definition_id: str) -> NodeCapability:
        return self.request('GET', f'/nodes/{definition_id}', adapter=TypeAdapter(NodeCapability))




    def get_canvas(self, page_id: str) -> CanvasAddResult:
        page = next((item for item in self.list_canvas_pages() if str(item.page_id) == str(page_id)), None)
        if page is None:
            raise ValueError('Canvas is offline; no graph snapshot is available.')
        body = CanvasGraphRequest(operation_id=uuid4(), page_id=page.page_id, workflow_id=page.workflow_id,
                                  graph_id=page.graph_id, content_token=page.content_token,
                                  edit={'action': 'inspect'})
        return self.request('POST', '/canvas/graph', json=body, adapter=TypeAdapter(CanvasAddResult))

    def edit_canvas(self, body: CanvasGraphRequest) -> CanvasAddResult:
        return self.request('POST', '/canvas/graph', json=body, adapter=TypeAdapter(CanvasAddResult))
