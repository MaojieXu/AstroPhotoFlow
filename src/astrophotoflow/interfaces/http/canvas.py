"""Canvas HTTP adapters and native write admission."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from astrophotoflow.contracts.canvas import CanvasAddRequest, CanvasAddResult, CanvasGraphRequest, CanvasPageOut
from astrophotoflow.core.errors import ApiError
from astrophotoflow.interfaces.application import canvas
from astrophotoflow.interfaces.application.canvas import CanvasDependencies
from astrophotoflow.interfaces.http import dependencies as deps
from astrophotoflow.interfaces.native.client import NativeClient

router = APIRouter(prefix="/api/v1/canvas", responses=deps.ERROR_RESPONSES)


def canvas_dependencies(request: Request) -> CanvasDependencies:
    state = request.app.state
    if not state.settings.allowed_origins:
        raise ApiError(503, "CANVAS_CONNECTION_UNKNOWN", "原生画布地址尚未配置。", message_key='native_canvas_unconfigured')
    native = NativeClient(state.http_client, state.settings.allowed_origins[0], state.token)
    return CanvasDependencies(state.settings, state.database, native)


Canvas = Annotated[CanvasDependencies, Depends(canvas_dependencies)]


@router.get("/pages", response_model=list[CanvasPageOut], dependencies=[Depends(deps.authenticate)], operation_id="list_canvas_pages_api_v1_canvas_pages_get")
async def list_canvas_pages(context: Canvas) -> list[CanvasPageOut]:
    return await context.native.list_pages()


@router.post("/requests", response_model=CanvasAddResult, dependencies=[Depends(deps.authenticate)], operation_id="add_canvas_data_api_v1_canvas_requests_post")
async def add_canvas_data(body: CanvasAddRequest, context: Canvas, _admission: deps.TaskAdmission) -> CanvasAddResult:
    return await canvas.add_canvas_data(context, body)


@router.get("/requests/{operation_id}", response_model=CanvasAddResult, dependencies=[Depends(deps.authenticate)], operation_id="get_canvas_request_api_v1_canvas_requests__operation_id__get")
async def get_canvas_request(operation_id: UUID, context: Canvas) -> CanvasAddResult:
    return await context.native.receipt(operation_id)


@router.post("/graph", response_model=CanvasAddResult, dependencies=[Depends(deps.authenticate)], operation_id="edit_canvas_api_v1_canvas_graph_post")
async def edit_canvas(body: CanvasGraphRequest, context: Canvas, _admission: deps.TaskAdmission) -> CanvasAddResult:
    return await canvas.edit_canvas(context, body)
