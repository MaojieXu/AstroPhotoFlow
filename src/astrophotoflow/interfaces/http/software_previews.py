"""HTTP binary preview/consumer protocol; execution assembly belongs to application."""
import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from astrophotoflow.contracts.software import BundlePreviewRequest
from astrophotoflow.core.errors import ApiError
from astrophotoflow.interfaces.application.software_previews import start_preview
from astrophotoflow.interfaces.http.dependencies import ERROR_RESPONSES, authenticate

router = APIRouter(prefix='/api/v1/software',dependencies=[Depends(authenticate)],responses=ERROR_RESPONSES)


@router.post("/preview", response_class=Response,
             responses={200: {"content": {"image/png": {"schema": {"type": "string", "format": "binary"}}}}}, operation_id='preview_api_v1_software_preview_post')
async def preview(body: BundlePreviewRequest, request: Request):
    manager = request.app.state.bundle_previews
    async with request.app.state.maintenance_lock:
        if request.app.state.maintenance or request.app.state.shutdown_started:
            raise ApiError(409, 'WORKBENCH_MAINTENANCE', '工作台正在维护。', message_key='the_workbench_is_undergoing_maintenance')
        operation = start_preview(manager, body)
    try:
        while not operation.done():
            await asyncio.wait({operation}, timeout=0.1)
            if await request.is_disconnected():
                operation.cancel()
                await asyncio.gather(operation, return_exceptions=True)
                raise ApiError(409, "PREVIEW_CANCELLED", "实时预览请求已关闭。", message_key='this_live_preview_request_is_closed')
        return Response(await operation, media_type="image/png", headers={"Cache-Control": "no-store"})
    except asyncio.CancelledError:
        operation.cancel()
        await asyncio.gather(operation, return_exceptions=True)
        raise


@router.delete("/preview/{consumer_id}", status_code=204, response_class=Response, operation_id='release_api_v1_software_preview__consumer_id__delete')
async def release(consumer_id: UUID, request: Request):
    await request.app.state.bundle_previews.cancel(consumer_id)
    return Response(status_code=204)


