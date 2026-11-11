"""Software call HTTP protocol and native task admission; no graph scheduler."""
import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import FileResponse

from astrophotoflow.contracts.software import NativeBundleCall, SoftwareCallResult
from astrophotoflow.core.errors import ApiError
from astrophotoflow.interfaces.application import software_calls as calls
from astrophotoflow.interfaces.http.dependencies import ERROR_RESPONSES, authenticate
from astrophotoflow.modules.software.public import software_call_log

router=APIRouter(dependencies=[Depends(authenticate)],responses=ERROR_RESPONSES)

@router.get('/api/v1/runs/{prompt_id}/calls',response_model=list[SoftwareCallResult],operation_id='list_call_results_api_v1_runs__prompt_id__calls_get')
async def list_call_results(prompt_id:UUID,request:Request,node_id:str|None=None,limit:int=Query(default=50,ge=1,le=100),offset:int=Query(default=0,ge=0)):
    return await calls.list_software_calls(request.app.state.settings,request.app.state.software_calls,prompt_id,node_id,limit,offset)

@router.get('/api/v1/runs/{prompt_id}/calls/{call_id}',response_model=SoftwareCallResult,operation_id='call_result_api_v1_runs__prompt_id__calls__call_id__get')
async def call_result(prompt_id:UUID,call_id:UUID,request:Request):
    return await calls.get_software_call(request.app.state.settings,request.app.state.software_calls,prompt_id,call_id)

@router.get('/api/v1/runs/{prompt_id}/calls/{call_id}/log',response_class=Response,responses={200:{'content':{'text/plain':{'schema':{'type':'string'}}}}},operation_id='call_log_api_v1_runs__prompt_id__calls__call_id__log_get')
def call_log(prompt_id:UUID,call_id:UUID,request:Request):
    return FileResponse(software_call_log(request.app.state.settings,prompt_id,call_id),media_type='text/plain',filename='process.log')

@router.post('/internal/native/bundles/calls',include_in_schema=False)
async def start(body:NativeBundleCall,request:Request):
    state=request.app.state
    async with state.maintenance_lock:
        if state.maintenance or state.shutdown_started:raise ApiError(409,'WORKBENCH_MAINTENANCE','Workbench is under maintenance.', message_key='workbench_under_maintenance')
        if any(not task.done() for task in state.software_tasks.values()):raise ApiError(409,'SOFTWARE_BUSY','Software maintenance is in progress.', message_key='software_maintenance_active')
        record,created=calls.prepare_native_call(state.settings,body)
        if created:
            task=asyncio.create_task(calls.execute_native_call(state.database,state.settings,body,admission_lock=state.maintenance_lock))
            state.software_calls[body.call_id]=task
            task.add_done_callback(lambda _task:state.software_calls.pop(body.call_id,None))
        return record

@router.get('/internal/native/bundles/calls/{prompt_id}/{call_id}',include_in_schema=False)
async def status(prompt_id:UUID,call_id:UUID,request:Request):
    state=request.app.state
    return await calls.observe_software_call(state.settings,state.software_calls,prompt_id,call_id)

@router.post('/internal/native/bundles/calls/{prompt_id}/{call_id}/cancel',include_in_schema=False)
async def cancel(prompt_id:UUID,call_id:UUID,request:Request):
    state=request.app.state
    return await calls.cancel_native_call(state.settings,state.software_calls,prompt_id,call_id)
