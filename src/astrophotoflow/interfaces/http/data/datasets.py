from typing import Annotated

from fastapi import Query

from astrophotoflow.contracts.datasets import DatasetMemberPage, DatasetMemberQuery, DatasetQuery

"""Dataset HTTP adaptation via the data public entry."""

from uuid import UUID

from fastapi import APIRouter, Depends

import astrophotoflow.interfaces.http.dependencies as deps
import astrophotoflow.modules.data.public as data
from astrophotoflow.contracts.datasets import (
    DatasetCreate,
    DatasetMemberParametersUpdate,
    DatasetMemberParametersUpdateOut,
    DatasetMembersCreate,
    DatasetOut,
    DatasetPage,
    DatasetPatch,
    DatasetVersionOut,
    DatasetVersionPage,
)

router = APIRouter(prefix="/api/v1", responses=deps.ERROR_RESPONSES)


@router.post('/datasets', response_model=DatasetOut, status_code=201, dependencies=[Depends(deps.authenticate)], operation_id='create_dataset_api_v1_datasets_post')
def create_dataset(body: DatasetCreate, session: deps.WriteSession) -> DatasetOut:
    return data.create_dataset(body=body, session=session)

@router.get('/datasets', response_model=DatasetPage, dependencies=[Depends(deps.authenticate)], operation_id='list_datasets_api_v1_datasets_get')
def list_datasets(session: deps.ReadSession, query: Annotated[DatasetQuery, Query()]) -> DatasetPage:
    return data.list_datasets(session=session, **query.model_dump())

@router.get('/datasets/{dataset_id}', response_model=DatasetOut, dependencies=[Depends(deps.authenticate)], operation_id='get_dataset_api_v1_datasets__dataset_id__get')
def get_dataset(dataset_id: UUID, session: deps.ReadSession) -> DatasetOut:
    return data.get_dataset(dataset_id=dataset_id, session=session)

@router.patch('/datasets/{dataset_id}', response_model=DatasetOut, dependencies=[Depends(deps.authenticate)], operation_id='patch_dataset_api_v1_datasets__dataset_id__patch')
def patch_dataset(dataset_id: UUID, body: DatasetPatch, session: deps.WriteSession) -> DatasetOut:
    return data.update_dataset(dataset_id=dataset_id, body=body, session=session)

@router.get('/datasets/{dataset_id}/versions', response_model=DatasetVersionPage, dependencies=[Depends(deps.authenticate)], operation_id='list_dataset_versions_api_v1_datasets__dataset_id__versions_get')
def list_dataset_versions(dataset_id: UUID, session: deps.ReadSession, limit: deps.Limit=50, offset: deps.Offset=0) -> DatasetVersionPage:
    return data.list_dataset_versions(dataset_id=dataset_id, session=session, limit=limit, offset=offset)

@router.get('/datasets/{dataset_id}/versions/{version_id}', response_model=DatasetVersionOut, dependencies=[Depends(deps.authenticate)], operation_id='get_dataset_version_api_v1_datasets__dataset_id__versions__version_id__get')
def get_dataset_version(dataset_id: UUID, version_id: UUID, session: deps.ReadSession) -> DatasetVersionOut:
    return data.get_dataset_version(dataset_id=dataset_id, version_id=version_id, session=session)

@router.patch('/datasets/{dataset_id}/member-parameters', response_model=DatasetMemberParametersUpdateOut, dependencies=[Depends(deps.authenticate)], operation_id='update_dataset_member_parameters_api_v1_datasets__dataset_id__member_parameters_patch')
def update_dataset_member_parameters(dataset_id: UUID, body: DatasetMemberParametersUpdate, session: deps.WriteSession) -> DatasetMemberParametersUpdateOut:
    return data.update_dataset_member_parameters(dataset_id=dataset_id, body=body, session=session)

@router.post('/datasets/{dataset_id}/versions', response_model=DatasetVersionOut, status_code=201, dependencies=[Depends(deps.authenticate)], operation_id='create_dataset_version_api_v1_datasets__dataset_id__versions_post')
def create_dataset_version(dataset_id: UUID, body: DatasetMembersCreate, session: deps.WriteSession) -> DatasetVersionOut:
    return data.publish_dataset_version(dataset_id=dataset_id, body=body, session=session)


@router.get('/datasets/{dataset_id}/versions/{version_id}/members', response_model=DatasetMemberPage,
            operation_id='listDatasetMembers', dependencies=[Depends(deps.authenticate)])
def list_dataset_members(
    dataset_id: UUID,
    version_id: UUID,
    session: deps.ReadSession,
    query: Annotated[DatasetMemberQuery, Query()],
) -> DatasetMemberPage:
    return data.list_dataset_members(session=session, dataset_id=dataset_id, version_id=version_id, query=query)
