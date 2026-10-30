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
    def list_run_calls(prompt_id: str, node_id: str | None = None, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        """Read observed software calls for an explicit native prompt. Returns checked output ports and implementation versions, not scientific pixels. An empty list is not proof that no work ran. Never replay unknown calls."""
        return call(lambda client: client.list_run_calls(prompt_id, node_id, limit, offset))

    @server.tool()
    def get_run_call(prompt_id: str, call_id: str) -> dict[str, Any]:
        """Query one accepted software call, checked result availability and actual process observations. Unknown remains unknown even when an old process has exited; this tool never re-executes processing."""
        return call(lambda client: client.get_run_call(prompt_id, call_id))

    @server.tool()
    def get_run_analysis(prompt_id: str, call_id: str, output_index: int, member_index: int) -> list[dict[str, Any]]:
        """Read one checked analysis member as metrics, a histogram/series, a table or a textual report. Units, sample limits and unavailable values are explicit; preview values are not scientific image inputs."""
        return call(lambda client: client.get_run_analysis(prompt_id, call_id, output_index, member_index))

    @server.tool()
    def get_canvas(page_id: str) -> dict[str, Any]:
        """Read the actual connected canvas through its native page. Reading never grants or restores Agent control."""
        return call(lambda client: client.get_canvas(page_id))

    @server.tool()
    def edit_canvas(body: CanvasGraphRequest) -> dict[str, Any]:
        """Apply one native add_node, set_parameter or connect operation to the exact authorized canvas. Use current tokens; read the actual receipt and query unknown operation IDs instead of replaying. Does not execute the graph."""
        return call(lambda client: client.edit_canvas(body))

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
