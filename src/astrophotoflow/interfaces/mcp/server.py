import httpx
import json
from mcp.types import CallToolResult, ImageContent, TextContent
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from astrophotoflow.interfaces.mcp.tools import canvas, imports, library, organization
from astrophotoflow.client import AssetClient, ServiceApiError
from astrophotoflow.core.config import ConfigurationError
from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.localization import exception_error
from astrophotoflow.contracts.localization import Locale
from astrophotoflow.interfaces.mcp.registry import Registry, DATA_NAMES, CANVAS_NAMES
from astrophotoflow.interfaces.mcp.tools import intake, exports
from typing import Any


def _result(value) -> CallToolResult:
    if isinstance(value, ImageContent):
        return CallToolResult(content=[value])
    structured = value if isinstance(value, dict) else {'result': value}
    return CallToolResult(content=[TextContent(type='text', text=json.dumps(structured, ensure_ascii=False))],
                          structuredContent=structured)


EN_INSTRUCTIONS = "Use data_management and node_canvas_management with operation and arguments. Known operations execute directly; discover/describe only when needed. No nested MCP servers or flat legacy tools. Night import: imports.inspect, show groups/issues and obtain user confirmation, imports.submit once, import_tasks.wait for aggregate results. Read current revisions before editing. Registration, originals, metadata and previews are independent. Node definitions: nodes.search/get/get_many. Canvas: canvas.pages/get reads the actual online graph. User-requested edits use canvas.edit/add_data with exact page/workflow/graph IDs and current content_token; no handoff is required. Stop on target/content changes, never follow another graph or retry stale writes. Editing does not execute. Query unknown canvas results with receipts.get and the original operation_id; unknown batch submissions with import_tasks.status and the original request_id. Never blindly replay. Permanent cleanup requires current trash preview and explicit user authorization. Node display uses display.en. Reconnect after tool migration or workspace language changes."
ZH_INSTRUCTIONS = "仅使用data_management和node_canvas_management，通过operation与arguments调用。已知操作直接执行，陌生能力才discover/describe；没有子MCP服务或旧扁平工具。整夜导入：imports.inspect→展示分组与疑义并获得用户确认→imports.submit一次提交→import_tasks.wait聚合结果。编辑前读当前revision；登记、原件、元数据与预览分别报告。nodes.search/get/get_many读取节点资料，优先display.zh。canvas.pages/get读取实际在线图。明确要求编辑后，canvas.edit/add_data使用准确页面／工作流／画布ID和当前content_token，不需接管／交回。目标或内容变化立即停止，不跟随其他图或重试过期写入。编辑不会执行图。未知画布结果以原operation_id查receipts.get，未知导入受理以原request_id查import_tasks.status，不盲目重放。永久清理需当前回收站预检及用户明确授权。迁移工具或切换workspace语言后重新连接。"


def _call(operation, locale: Locale = 'en'):
    try:
        with AssetClient() as client:
            return operation(client)
    except ServiceApiError as exc:
        raise ToolError(str(exc)) from exc
    except ApiError as exc:
        detail = exception_error(locale, exc, code='MCP_REQUEST_FAILED', message_key='request_failed')
        raise ToolError(f'{detail.code}: {detail.message} fields={detail.fields}') from exc
    except (ConfigurationError, httpx.HTTPError, OSError, ValueError, KeyError) as exc:
        detail = exception_error(locale, exc, code='MCP_REQUEST_FAILED', message_key='request_failed')
        raise ToolError(f'{detail.code}: {detail.message} fields={detail.fields}') from exc


def create_server(locale: Locale = 'en') -> MCPServer:
    instance = MCPServer('AstroPhotoFlow', instructions=ZH_INSTRUCTIONS if locale == 'zh' else EN_INSTRUCTIONS)
    data = Registry(DATA_NAMES | intake.NAMES | exports.NAMES)
    graph = Registry(CANVAS_NAMES)
    for domain in (imports, library, organization, intake, exports):
        domain.register(data, lambda operation: _call(operation, locale), locale)
    canvas.register(graph, lambda operation: _call(operation, locale), locale)

    @instance.tool(description=(
        '数据管理：导入、任务、素材／组、项目、设备、校准、预览、回收站及exports保存／导出。已知操作直接调用，例如 operation="projects.list", arguments={"limit":10}。discover 使用 query/group/limit/offset；describe 使用 operations 名称列表。imports.inspect→用户确认→imports.submit→import_tasks.wait。'
        if locale == 'zh' else
        'Manage imports/tasks, assets/groups, projects, equipment, calibration, previews, trash and exports. Call known operations directly: operation="projects.list", arguments={"limit":10}. discover accepts query/group/limit/offset; describe accepts operations: [names]. Import flow: imports.inspect → user confirmation → imports.submit → import_tasks.wait.'
    ))
    def data_management(operation: str, arguments: dict[str, Any]) -> CallToolResult:
        return _result(data.invoke(operation, arguments))

    @instance.tool(description=(
        '节点与在线画布：nodes.search/get/get_many、canvas.pages/get/edit/add_data、receipts.get、runs.list_calls/get_call/analysis。已知操作直接调用；discover 使用 query/group/limit/offset；describe 使用 operations 名称列表。编辑必须核对目标和content_token；未知结果先查回执，不重放。'
        if locale == 'zh' else
        'Nodes and online canvas: nodes.search/get/get_many, canvas.pages/get/edit/add_data, receipts.get, runs.list_calls/get_call/analysis. Call known operations directly; discover accepts query/group/limit/offset; describe accepts operations: [names]. Verify target/content_token before edits; query unknown receipts rather than replaying.'
    ))
    def node_canvas_management(operation: str, arguments: dict[str, Any]) -> CallToolResult:
        return _result(graph.invoke(operation, arguments))
    return instance


def run() -> None:
    with AssetClient() as client:
        locale = client.get_workspace_locale().locale
    create_server(locale).run()


server = create_server()
