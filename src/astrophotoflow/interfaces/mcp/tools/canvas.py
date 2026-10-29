from typing import Any

from astrophotoflow.contracts.workflows import CanvasAddRequest


def register(server, call):
    @server.tool()
    def list_canvas_pages() -> list[dict[str, Any]]:
        """List connected active canvases; only a non-null control_token permits adding data after explicit user handoff."""
        return call(lambda client: client.list_canvas_pages())

    @server.tool()
    def add_canvas_data(body: CanvasAddRequest) -> dict[str, Any]:
        """Add a fixed asset/group to the exact authorized canvas. Read current tokens first; unknown results require querying the same operation_id, never automatic replay."""
        return call(lambda client: client.add_canvas_data(body))

    @server.tool()
    def get_canvas_request(operation_id: str) -> dict[str, Any]:
        """Read a canvas application receipt from this engine session; unknown is not proof that no node was added."""
        return call(lambda client: client.get_canvas_request(operation_id))
