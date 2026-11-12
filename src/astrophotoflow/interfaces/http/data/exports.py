import asyncio
from threading import Event
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from astrophotoflow.contracts.data_nodes import ExportReceipt, ExportRequest, ExportSelection
from astrophotoflow.contracts.workbench import DirectorySelectionResult
from astrophotoflow.core.errors import ApiError
from astrophotoflow.interfaces.http.dependencies import ERROR_RESPONSES, TaskAdmission, authenticate
from astrophotoflow.modules.data.public import get_checked_result, get_data_result, select_export_destination

router = APIRouter(prefix='/api/v1/exports', dependencies=[Depends(authenticate)], responses=ERROR_RESPONSES)


@router.post('/select-local', response_model=DirectorySelectionResult, operation_id='selectExportDestination')
async def choose_destination(body: ExportSelection, request: Request):
    cancelled = Event()
    selection = asyncio.create_task(asyncio.to_thread(select_export_destination, request.app.state.settings, body, cancelled))
    try:
        while not selection.done():
            if await request.is_disconnected(): cancelled.set()
            await asyncio.wait({selection}, timeout=0.1)
        return {'path': await selection}
    finally:
        cancelled.set()


@router.post('', status_code=202, response_model=ExportReceipt, response_model_exclude_unset=True, operation_id='submit_api_v1_exports_post')
def submit(body: ExportRequest, request: Request, admission: TaskAdmission):
    service = request.app.state.data_exports
    previous = service.existing(body)
    if previous is not None: return previous
    record = get_data_result(request.app.state.settings, body.source.run_id, body.source.execution_id)
    if record.state != 'completed':
        raise ApiError(409, 'OUTPUT_NOT_READY', 'Select a completed Data result before exporting.', message_key='export_completed_result_required')
    # The worker rechecks complete bytes against these frozen hashes. Acceptance stays short.
    return service.submit(body, get_checked_result(request.app.state.settings,body.source.run_id,body.source.execution_id).ports[0].members)


@router.get('/{request_id}', response_model=ExportReceipt, response_model_exclude_unset=True, operation_id='status_api_v1_exports__request_id__get')
def status(request_id: UUID, request: Request):
    return request.app.state.data_exports.get(request_id)


@router.post('/{request_id}/cancel', response_model=ExportReceipt, response_model_exclude_unset=True, operation_id='cancel_api_v1_exports__request_id__cancel_post')
def cancel(request_id: UUID, request: Request):
    return request.app.state.data_exports.cancel(request_id)
