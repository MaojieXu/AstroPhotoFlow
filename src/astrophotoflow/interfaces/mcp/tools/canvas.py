from astrophotoflow.interfaces.mcp.localization import tool_description, node_display
from typing import Any
from typing import Annotated
from pydantic import Field

from astrophotoflow.contracts.workflows import CanvasAddRequest, CanvasGraphRequest


def register(server, call, locale='en'):
    @server.tool(description=tool_description(locale, 'list_nodes'))
    def list_nodes(query: str | None = None, limit: Annotated[int, Field(ge=1, le=10)] = 10,
                   offset: Annotated[int, Field(ge=0)] = 0) -> dict[str, Any]:
        """Search at most ten short installed-node summaries per page. Read parameters/examples with nodes.get/get_many. Command references are not executable nodes."""
        def search(client):
            values = client.list_nodes(query)
            items = []
            for value in values[offset:offset + limit]:
                definition = value['node']['definition']
                display = value.get('display', {}).get(locale, {})
                items.append({'definition_id': definition['definition_id'],
                              'name': display.get('name', definition['name']),
                              'description': display.get('description', definition['description']),
                              'available': value['available'], 'reason': value.get('reason'),
                              'content_token': value['node']['content_token']})
            return {'items': items, 'total': len(values), 'limit': limit, 'offset': offset}
        return call(search)

    @server.tool(description='批量读取指定节点完整定义。' if locale == 'zh' else 'Read full definitions for up to ten explicit node IDs in one call.')
    def get_nodes(definition_ids: Annotated[list[str], Field(min_length=1, max_length=10)]) -> dict[str, Any]:
        return call(lambda client: {'items': [node_display(client.get_node(identity), locale) for identity in definition_ids]})

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
