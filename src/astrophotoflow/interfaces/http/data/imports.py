from __future__ import annotations

import asyncio
from threading import Event
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request

import astrophotoflow.interfaces.http.dependencies as deps
import astrophotoflow.modules.data.public as data
from astrophotoflow.contracts.imports import (
    AssetTaskOut,
    AssetTaskPage,
    ImportAccepted,
    ImportCreate,
    ImportRootEntryPage,
    ImportRootOut,
    ImportTaskStateOut,
    LocalSelectionOut,
    LocalSelectionRequest,
    RetryCreate,
    UploadImportCreate,
    UploadReceipt,
)
from astrophotoflow.interfaces.http.dependencies import ERROR_RESPONSES

router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)

@router.post('/imports', status_code=202, dependencies=[Depends(deps.authenticate)], response_model=ImportAccepted, operation_id='create_import_api_v1_imports_post')
def create_import(body: ImportCreate, request: Request, background: BackgroundTasks, admission: deps.TaskAdmission, session: deps.WriteSession) -> ImportAccepted:
    result = data.create_import(session=session, settings=request.app.state.settings, body=body)
    background.add_task(data.run_import_task, request.app.state.database, request.app.state.settings, str(result.task_id), request.app.state.import_workers)
    return result

@router.post('/uploads', status_code=202, dependencies=[Depends(deps.authenticate)], response_model=ImportAccepted, operation_id='create_upload_api_v1_uploads_post')
def create_upload(body: UploadImportCreate, request: Request, admission: deps.TaskAdmission, session: deps.WriteSession) -> ImportAccepted:
    result = data.create_upload(session=session, settings=request.app.state.settings, body=body)
    return result

@router.put('/uploads/{task_id}/{index}', dependencies=[Depends(deps.authenticate)], response_model=UploadReceipt,
            openapi_extra={"requestBody": {"required": True, "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
            }}}, operation_id='upload_file_api_v1_uploads__task_id___index__put')
async def upload_file(task_id: UUID, index: int, request: Request) -> UploadReceipt:
    result = await data.upload_file(database=request.app.state.database, settings=request.app.state.settings, task_id=task_id, index=index, chunks=request.stream())
    return result

@router.post('/uploads/{task_id}/start', status_code=202, dependencies=[Depends(deps.authenticate)], response_model=ImportAccepted, operation_id='start_upload_import_api_v1_uploads__task_id__start_post')
def start_upload_import(task_id: UUID, request: Request, background: BackgroundTasks, admission: deps.TaskAdmission, session: deps.WriteSession) -> ImportAccepted:
    result = data.start_upload_import(session=session, task_id=task_id)
    background.add_task(data.run_import_task, request.app.state.database, request.app.state.settings, str(result.task_id), request.app.state.import_workers)
    return result

@router.post('/uploads/{task_id}/fail', dependencies=[Depends(deps.authenticate)], response_model=ImportTaskStateOut, operation_id='fail_upload_api_v1_uploads__task_id__fail_post')
def fail_upload(task_id: UUID, request: Request, session: deps.WriteSession) -> ImportTaskStateOut:
    result = data.fail_upload(session=session, settings=request.app.state.settings, task_id=task_id)
    return result

@router.get('/asset-tasks', dependencies=[Depends(deps.authenticate)], response_model=AssetTaskPage, operation_id='list_asset_tasks_api_v1_asset_tasks_get')
def list_asset_tasks(session: deps.ReadSession, limit: deps.Limit=50, offset: deps.Offset=0, status: Literal['queued', 'running', 'cancelling', 'completed', 'completed_with_errors', 'failed', 'cancelled', 'interrupted', 'all']='all') -> AssetTaskPage:
    result = data.list_asset_tasks(session=session, limit=limit, offset=offset, status=status)
    return result

@router.get('/asset-tasks/{task_id}', dependencies=[Depends(deps.authenticate)], response_model=AssetTaskOut, operation_id='get_asset_task_api_v1_asset_tasks__task_id__get')
def get_asset_task(task_id: UUID, session: deps.ReadSession, items_limit: Annotated[int, Query(ge=1, le=200)]=50, items_offset: Annotated[int, Query(ge=0)]=0) -> AssetTaskOut:
    result = data.get_asset_task(session=session, task_id=task_id, items_limit=items_limit, items_offset=items_offset)
    return result

@router.post('/asset-tasks/{task_id}/cancel', status_code=202, dependencies=[Depends(deps.authenticate)], response_model=ImportTaskStateOut, operation_id='cancel_asset_task_api_v1_asset_tasks__task_id__cancel_post')
def cancel_asset_task(task_id: UUID, request: Request, session: deps.WriteSession) -> ImportTaskStateOut:
    result = data.cancel_asset_task(session=session, task_id=task_id)
    return result

@router.post('/asset-tasks/{task_id}/resume', status_code=202, dependencies=[Depends(deps.authenticate)], response_model=ImportAccepted, operation_id='resume_asset_task_api_v1_asset_tasks__task_id__resume_post')
def resume_asset_task(task_id: UUID, request: Request, background: BackgroundTasks, admission: deps.TaskAdmission, session: deps.WriteSession) -> ImportAccepted:
    result = data.resume_asset_task(session=session, task_id=task_id)
    background.add_task(data.run_import_task, request.app.state.database, request.app.state.settings, str(result.task_id), request.app.state.import_workers)
    return result

@router.post('/asset-tasks/{task_id}/retry', status_code=202, dependencies=[Depends(deps.authenticate)], response_model=ImportAccepted, operation_id='retry_asset_task_api_v1_asset_tasks__task_id__retry_post')
def retry_asset_task(task_id: UUID, body: RetryCreate, request: Request, background: BackgroundTasks, admission: deps.TaskAdmission, session: deps.WriteSession) -> ImportAccepted:
    result = data.retry_asset_task(session=session, task_id=task_id, body=body)
    background.add_task(data.run_import_task, request.app.state.database, request.app.state.settings, str(result.task_id), request.app.state.import_workers)
    return result


@router.post("/imports/select-local", response_model=LocalSelectionOut, dependencies=[Depends(deps.authenticate)], operation_id='select_local_import_api_v1_imports_select_local_post')
async def select_local_import(body: LocalSelectionRequest, request: Request) -> LocalSelectionOut:
    cancelled = Event()
    chooser = asyncio.create_task(asyncio.to_thread(data.select_local_import, request.app.state.settings, body, cancelled))
    try:
        while not chooser.done():
            if await request.is_disconnected():
                cancelled.set()
            await asyncio.wait({chooser}, timeout=0.1)
        return await chooser
    finally:
        cancelled.set()


@router.get("/import-roots", response_model=list[ImportRootOut], dependencies=[Depends(deps.authenticate)], operation_id='import_roots_api_v1_import_roots_get')
def import_roots(request: Request) -> list[ImportRootOut]:
    return data.list_import_roots(request.app.state.settings)


@router.get("/import-roots/{root_id}/entries", response_model=ImportRootEntryPage, dependencies=[Depends(deps.authenticate)], operation_id='import_root_entries_api_v1_import_roots__root_id__entries_get')
def import_root_entries(root_id: str, request: Request, path: str = "", limit: deps.Limit = 100,
                        offset: deps.Offset = 0, q: str | None = None) -> ImportRootEntryPage:
    return data.list_import_root_entries(request.app.state.settings, root_id, path, limit, offset, q)
