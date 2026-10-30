from typing import Any

from astrophotoflow.contracts.workflows import CanvasAddRequest, CanvasGraphRequest


def register(server, call):
    @server.tool()
    def list_nodes(query: str | None = None) -> list[dict[str, Any]]:
        """Discover installed workspace nodes, availability, parameter schemas and bundle help. Command references are not executable nodes."""
        return call(lambda client: client.list_nodes(query))

    @server.tool()
    def get_node(definition_id: str) -> dict[str, Any]:
        """Read node ports, defaults, ranges, examples and current definition token before adding or configuring a node."""
        return call(lambda client: client.get_node(definition_id))

    @server.tool()
    def get_canvas(page_id: str) -> dict[str, Any]:
        """Read the actual connected canvas through its native page without changing its content."""
        return call(lambda client: client.get_canvas(page_id))

    @server.tool()
    def edit_canvas(body: CanvasGraphRequest) -> dict[str, Any]:
        """Apply one user-requested add_node, set_parameter, connect or delete_node operation to the exact active canvas using its current target IDs and content_token. Deletion removes the node and attached links through native undo support, retaining source assets. Stop on target/content changes; query unknown operation IDs instead of replaying. Does not execute the graph."""
        return call(lambda client: client.edit_canvas(body))

    @server.tool()
    def list_canvas_pages() -> list[dict[str, Any]]:
        """List connected active canvases and their current target IDs and content_token. Only edit the canvas requested by the user; never follow another graph automatically."""
        return call(lambda client: client.list_canvas_pages())

    @server.tool()
    def add_canvas_data(body: CanvasAddRequest) -> dict[str, Any]:
        """Add a user-requested fixed asset/group to the exact active canvas using current target IDs and content_token. Stop on target/content changes; query unknown results with the same operation_id, never automatic replay."""
        return call(lambda client: client.add_canvas_data(body))

    @server.tool()
    def get_canvas_request(operation_id: str) -> dict[str, Any]:
        """Read a canvas application receipt from this engine session; unknown is not proof that no node was added."""
        return call(lambda client: client.get_canvas_request(operation_id))
