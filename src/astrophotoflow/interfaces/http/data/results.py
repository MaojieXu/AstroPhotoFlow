"""Data execution HTTP adaptation; source bytes and checked facts stay in data."""
from uuid import UUID

from fastapi import APIRouter, Depends, Request

import astrophotoflow.modules.data.public as data
from astrophotoflow.contracts.data_nodes import DataNodeResult, NativeDataExecute
from astrophotoflow.interfaces.http.dependencies import ERROR_RESPONSES, TaskAdmission, authenticate

router=APIRouter(dependencies=[Depends(authenticate)],responses=ERROR_RESPONSES)

@router.post('/internal/native/data',response_model=DataNodeResult,operation_id='native_data_internal_native_data_post')
def native_data(body:NativeDataExecute,request:Request,admission:TaskAdmission)->DataNodeResult:
    return data.execute_data_node(request.app.state.database,request.app.state.settings,body)

@router.get('/api/v1/data-nodes/{run_id}/{execution_id}',response_model=DataNodeResult,operation_id='get_data_api_v1_data_nodes__run_id___execution_id__get')
def get_data(run_id:UUID,execution_id:UUID,request:Request)->DataNodeResult:
    return data.get_data_result(request.app.state.settings,run_id,execution_id)
