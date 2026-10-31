import httpx
from fastapi import APIRouter, Depends, Request

from astrophotoflow.contracts.workflows import CanvasAddRequest, CanvasAddResult, CanvasPageOut, NativeCanvasCommand
from astrophotoflow.core import http as deps
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.public import prepare_canvas_data
from uuid import UUID
from astrophotoflow.contracts.workflows import CanvasGraphRequest, NativeCanvasGraphCommand
from astrophotoflow.modules.nodes.catalog import describe_node


router = APIRouter(prefix="/api/v1/canvas", responses=deps.ERROR_RESPONSES)


async def _native(request: Request, method: str, path: str, body=None):
    url = request.app.state.settings.allowed_origins[0] + "/astrophotoflow/internal/canvas" + path
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.request(method, url, json=body, headers={
                "Authorization": f"Bearer {request.app.state.token}",
            })
    except httpx.HTTPError as exc:
        raise ApiError(503, "CANVAS_CONNECTION_UNKNOWN", "无法核对画布结果；请查询同一 operation_id，不要自动重发。", message_key='cannot_confirm_the_canvas_result_query_the_same_operation_id_do_not_automat') from exc
    result = response.json()
    if not response.is_success:
        error = result["error"]
        raise ApiError(response.status_code, error["code"], error["message"], fields=error.get('fields', []), message_key='forwarded_service_error', message_params={'message': error['message']})
    return result


@router.get("/pages", response_model=list[CanvasPageOut], dependencies=[Depends(deps.authenticate)])
async def list_canvas_pages(request: Request):
    return await _native(request, "GET", "/pages")


@router.post("/requests", response_model=CanvasAddResult, dependencies=[Depends(deps.authenticate)])
async def add_canvas_data(body: CanvasAddRequest, request: Request):
    async with request.app.state.maintenance_lock:
        if request.app.state.maintenance or request.app.state.shutdown_started:
            raise ApiError(409, "WORKBENCH_MAINTENANCE", "工作台正在维护，暂不接受画布写入。", message_key='the_workbench_is_undergoing_maintenance_and_cannot_accept_canvas_writes')
        data = prepare_canvas_data(request.app.state.database, body.source)
        command = NativeCanvasCommand(request=body, data=data)
        return await _native(request, "POST", "/requests", command.model_dump(mode="json"))


@router.get("/requests/{operation_id}", response_model=CanvasAddResult, dependencies=[Depends(deps.authenticate)])
async def get_canvas_request(operation_id: UUID, request: Request):
    return await _native(request, "GET", f"/requests/{operation_id}")


@router.post('/graph', response_model=CanvasAddResult, dependencies=[Depends(deps.authenticate)])
async def edit_canvas(body: CanvasGraphRequest, request: Request):
    async with request.app.state.maintenance_lock:
        if request.app.state.maintenance or request.app.state.shutdown_started:
            raise ApiError(409, 'WORKBENCH_MAINTENANCE', '工作台正在维护。', message_key='the_workbench_is_undergoing_maintenance')
        definition = None
        if body.edit.action == 'add_node':
            capability = describe_node(request.app.state.settings, body.edit.definition_id)
            if not capability.available:
                raise ApiError(409, 'SOFTWARE_NOT_READY', capability.reason or '节点依赖尚未就绪。', message_key='node_software_not_ready', fields=[{'path': 'diagnostic', 'message': capability.reason or '节点依赖尚未就绪。'}])
            definition = capability.node
        command = NativeCanvasGraphCommand(request=body, definition=definition)
        return await _native(request, 'POST', '/requests', command.model_dump(mode='json'))
