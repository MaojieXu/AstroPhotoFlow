"""Schedule accepted batch work after the HTTP transaction finishes."""
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request

import astrophotoflow.interfaces.http.dependencies as deps
import astrophotoflow.modules.data.public as data
from astrophotoflow.contracts.import_batches import BatchOut, ImportBatchProjectRetry, ImportBatchSubmit, ImportBatchWait

router = APIRouter(prefix='/api/v1/import-batches', dependencies=[Depends(deps.authenticate)], responses=deps.ERROR_RESPONSES)


@router.post('', response_model=BatchOut, status_code=202, operation_id='submit_api_v1_import_batches_post')
def submit(body: ImportBatchSubmit, request: Request, background: BackgroundTasks,
           admission: deps.TaskAdmission, session: deps.WriteSession):
    accepted = data.submit_import_batch(session, request.app.state.settings, body)
    for task_id in accepted.scheduled_task_ids:
        background.add_task(data.run_import_task, request.app.state.database, request.app.state.settings,
                            task_id, request.app.state.import_workers)
    return accepted.result


@router.get('/{request_id}', response_model=BatchOut, operation_id='status_api_v1_import_batches__request_id__get')
def status(request_id: UUID, session: deps.ReadSession):
    return data.get_import_batch(session, request_id)


@router.post('/wait', response_model=BatchOut, operation_id='wait_batch_api_v1_import_batches_wait_post')
def wait_batch(body: ImportBatchWait, request: Request):
    return data.wait_import_batch(request.app.state.database, body)


@router.post('/{request_id}/project-references', response_model=BatchOut, operation_id='retry_project_links_api_v1_import_batches__request_id__project_references_post')
def retry_project_links(request_id: UUID, body: ImportBatchProjectRetry, request: Request,
                        background: BackgroundTasks, session: deps.WriteSession):
    result, root_task_id = data.prepare_batch_project_retry(session, request_id, body)
    background.add_task(data.finalize_task_batch, request.app.state.database, root_task_id)
    return result
