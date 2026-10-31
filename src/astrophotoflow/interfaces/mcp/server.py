import httpx
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from astrophotoflow.interfaces.mcp.tools import canvas, imports, library, organization
from astrophotoflow.client import AssetClient, ServiceApiError
from astrophotoflow.core.config import ConfigurationError
from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.localization import exception_error
from astrophotoflow.contracts.localization import Locale


EN_INSTRUCTIONS = "Manage the local AstroPhotoFlow library through its shared HTTP service. Read current revisions before editing. Registration, original readiness and preview readiness are separate. Discover bundle nodes with list_nodes/get_node and read their parameters and examples. get_canvas reads the actual online graph without changing it. When the user explicitly requests an edit, add data or use edit_canvas directly with the exact active page/workflow/graph IDs and current content_token; no control handoff is required. Stop if the target or content changes; do not automatically follow another graph or retry stale writes. Canvas editing does not execute the workflow. Query unknown application results with the same operation_id; never automatically replay them. Permanent cleanup requires a current trash preview and user authorization. Node display text uses display.en. Reconnect after changing the workspace language to refresh cached tool descriptions."
ZH_INSTRUCTIONS = "通过共享HTTP服务管理本机AstroPhotoFlow工作台。编辑前读取当前revision。登记、原件就绪和预览就绪是独立状态。使用list_nodes/get_node发现Bundle节点并读取参数及示例，优先采用display.zh展示说明。get_canvas只读取实际在线图。用户明确要求修改时，直接使用准确活动页面／工作流／画布ID和当前content_token添加素材或调用edit_canvas，不需要接管／交回。目标或内容变化立即停止，不自动跟随其他图或重试过期写入。画布编辑不会执行工作流。未知结果先查询同一operation_id，不自动重放。永久清理需要最新回收站预览和用户授权。修改workspace语言后重新连接，以刷新客户端缓存的工具说明。"


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
    for domain in (imports, library, organization, canvas):
        domain.register(instance, lambda operation: _call(operation, locale), locale)
    return instance


def run() -> None:
    with AssetClient() as client:
        locale = client.get_workspace_locale().locale
    create_server(locale).run()


server = create_server()
