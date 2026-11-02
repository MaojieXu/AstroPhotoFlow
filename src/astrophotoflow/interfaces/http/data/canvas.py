"""HTTP adapter for fixed data references and canvas inspection."""

from fastapi import APIRouter, Depends, Request

import astrophotoflow.interfaces.http.dependencies as deps
import astrophotoflow.modules.data.public as data
from astrophotoflow.contracts.inputs import (
    CanvasDataOut,
    CanvasDataRequest,
    CanvasInspectOut,
    CanvasInspectRequest,
)

router = APIRouter(prefix="/api/v1", responses=deps.ERROR_RESPONSES)


@router.post("/library/canvas-data", response_model=CanvasDataOut, dependencies=[Depends(deps.authenticate)], operation_id='canvas_data_api_v1_library_canvas_data_post')
def canvas_data(body: CanvasDataRequest, request: Request) -> CanvasDataOut:
    return data.prepare_canvas_data(request.app.state.database, body)


@router.post("/library/canvas-data/inspect", response_model=CanvasInspectOut, dependencies=[Depends(deps.authenticate)], operation_id='inspect_canvas_api_v1_library_canvas_data_inspect_post')
def inspect_canvas(body: CanvasInspectRequest, request: Request) -> CanvasInspectOut:
    return data.inspect_canvas_data(request.app.state.database, body)
