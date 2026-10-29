import httpx
from fastapi import APIRouter, Depends, Request

from astrophotoflow.contracts.workflows import CanvasAddRequest, CanvasAddResult, CanvasPageOut, NativeCanvasCommand
from astrophotoflow.core import http as deps
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.public import prepare_canvas_data
from uuid import UUID


router = APIRouter(prefix="/api/v1/canvas", responses=deps.ERROR_RESPONSES)


async def _native(request: Request, method: str, path: str, body=None):
    url = request.app.state.settings.allowed_origins[0] + "/astrophotoflow/internal/canvas" + path
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.request(method, url, json=body, headers={
                "Authorization": f"Bearer {request.app.state.token}",
            })
    except httpx.HTTPError as exc:
        raise ApiError(503, "CANVAS_CONNECTION_UNKNOWN", "无法核对画布结果；请查询同一 operation_id，不要自动重发。") from exc
    result = response.json()
    if not response.is_success:
        error = result["error"]
        raise ApiError(response.status_code, error["code"], error["message"])
    return result


@router.get("/pages", response_model=list[CanvasPageOut], dependencies=[Depends(deps.authenticate)])
async def list_canvas_pages(request: Request):
    return await _native(request, "GET", "/pages")


@router.post("/requests", response_model=CanvasAddResult, dependencies=[Depends(deps.authenticate)])
async def add_canvas_data(body: CanvasAddRequest, request: Request):
    async with request.app.state.maintenance_lock:
        if request.app.state.maintenance or request.app.state.shutdown_started:
            raise ApiError(409, "WORKBENCH_MAINTENANCE", "工作台正在维护，暂不接受画布写入。")
        data = prepare_canvas_data(request.app.state.database, body.source)
        command = NativeCanvasCommand(request=body, data=data)
        return await _native(request, "POST", "/requests", command.model_dump(mode="json"))


@router.get("/requests/{operation_id}", response_model=CanvasAddResult, dependencies=[Depends(deps.authenticate)])
async def get_canvas_request(operation_id: UUID, request: Request):
    return await _native(request, "GET", f"/requests/{operation_id}")
