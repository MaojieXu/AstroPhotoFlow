from astrophotoflow.interfaces.mcp.localization import tool_description, node_display
from typing import Any

from astrophotoflow.contracts.workflows import CanvasAddRequest, CanvasGraphRequest


def register(server, call, locale='en'):
    @server.tool(description=tool_description(locale, 'list_nodes'))
    def list_nodes(query: str | None = None) -> list[dict[str, Any]]:
        """Discover installed workspace nodes, availability, parameter schemas and bundle help. Command references are not executable nodes."""
        return call(lambda client: [node_display(value, locale) for value in client.list_nodes(query)])

    @server.tool(description=tool_description(locale, 'get_node'))
    def get_node(definition_id: str) -> dict[str, Any]:
        """Read node ports, defaults, ranges, examples and current definition token before adding or configuring a node."""
        return call(lambda client: node_display(client.get_node(definition_id), locale))

    @server.tool(description=tool_description(locale, 'list_run_calls'))
    def list_run_calls(prompt_id: str, node_id: str | None = None, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        """Read observed software calls for an explicit native prompt. Returns checked output ports and implementation versions, not scientific pixels. An empty list is not proof that no work ran. Never replay unknown calls."""
        return call(lambda client: client.list_run_calls(prompt_id, node_id, limit, offset))

    @server.tool(description=tool_description(locale, 'get_run_call'))
    def get_run_call(prompt_id: str, call_id: str) -> dict[str, Any]:
        """Query one accepted software call, checked result availability and actual process observations. Unknown remains unknown even when an old process has exited; this tool never re-executes processing."""
        return call(lambda client: client.get_run_call(prompt_id, call_id))

    @server.tool(description=tool_description(locale, 'get_run_analysis'))
    def get_run_analysis(prompt_id: str, call_id: str, output_index: int, member_index: int) -> list[dict[str, Any]]:
        """Read one checked analysis member as metrics, a histogram/series, a table or a textual report. Units, sample limits and unavailable values are explicit; preview values are not scientific image inputs."""
        return call(lambda client: client.get_run_analysis(prompt_id, call_id, output_index, member_index))

    @server.tool(description=tool_description(locale, 'get_canvas'))
    def get_canvas(page_id: str) -> dict[str, Any]:
        """Read the actual connected canvas through its native page without changing its content."""
        return call(lambda client: client.get_canvas(page_id))

    @server.tool(description=tool_description(locale, 'edit_canvas'))
    def edit_canvas(body: CanvasGraphRequest) -> dict[str, Any]:
        """Apply one user-requested add_node, set_parameter, connect or delete_node operation to the exact active canvas using its current target IDs and content_token. Deletion removes the node and attached links through native undo support, retaining source assets. Stop on target/content changes; query unknown operation IDs instead of replaying. Does not execute the graph."""
        return call(lambda client: client.edit_canvas(body))

    @server.tool(description=tool_description(locale, 'list_canvas_pages'))
    def list_canvas_pages() -> list[dict[str, Any]]:
        """List connected active canvases and their current target IDs and content_token. Only edit the canvas requested by the user; never follow another graph automatically."""
        return call(lambda client: client.list_canvas_pages())

    @server.tool(description=tool_description(locale, 'add_canvas_data'))
    def add_canvas_data(body: CanvasAddRequest) -> dict[str, Any]:
        """Add a user-requested fixed asset/group to the exact active canvas using current target IDs and content_token. Stop on target/content changes; query unknown results with the same operation_id, never automatic replay."""
        return call(lambda client: client.add_canvas_data(body))

    @server.tool(description=tool_description(locale, 'get_canvas_request'))
    def get_canvas_request(operation_id: str) -> dict[str, Any]:
        """Read a canvas application receipt from this engine session; unknown is not proof that no node was added."""
        return call(lambda client: client.get_canvas_request(operation_id))
