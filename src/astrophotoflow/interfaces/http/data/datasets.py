from typing import Annotated, Literal
from fastapi import Query
from pydantic import Field
from astrophotoflow.contracts.assets import LibrarySortKey
from astrophotoflow.contracts.datasets import DatasetMemberPage, DatasetMemberQuery, DatasetMemberSummaryPage, DatasetQuery
from astrophotoflow.contracts.image_calibration import ImageDatasetCreate, ImageOperationOut
from astrophotoflow.contracts.image_management import (
    DatasetImageDetail,
    DatasetImageMemberPage,
    DatasetImagePage,
    DatasetMemberSearch,
    DatasetSearch,
    ImageDatasetUpdate,
)


class ImageDatasetHttpQuery(DatasetSearch):
    image_query: bool = Field(default=False, strict=False)
    q: str | None = None


class ImageDatasetMemberHttpQuery(DatasetMemberQuery, DatasetMemberSearch):
    image_query: bool = Field(default=False, strict=False)
    sort_by: LibrarySortKey | Literal["position", "capture_start", "master_created_at"] = "position"


"Dataset HTTP adaptation via the data public entry."
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
)
from astrophotoflow.core.errors import ApiError

router = APIRouter(prefix="/api/v1", responses=deps.ERROR_RESPONSES)


@router.get(
    "/datasets/{dataset_id}/member-summaries",
    response_model=DatasetMemberSummaryPage,
    operation_id="listDatasetMemberSummaries",
    dependencies=[Depends(deps.authenticate)],
)
def list_member_summaries(dataset_id: UUID, session: deps.ReadSession, query: Annotated[DatasetMemberQuery, Query()]):
    return data.list_dataset_members(session, dataset_id, query, summaries=True)


@router.post(
    "/datasets",
    response_model=DatasetOut | ImageOperationOut,
    status_code=201,
    dependencies=[Depends(deps.authenticate)],
    operation_id="create_dataset_api_v1_datasets_post",
)
def create_dataset(body: DatasetCreate | ImageDatasetCreate, session: deps.WriteSession):
    if isinstance(body, ImageDatasetCreate):
        return ImageOperationOut.model_validate(data.create_image_dataset(session, body), strict=False)
    return data.create_dataset(body=body, session=session)


@router.get(
    "/datasets",
    response_model=DatasetImagePage | DatasetPage,
    dependencies=[Depends(deps.authenticate)],
    operation_id="list_datasets_api_v1_datasets_get",
)
def list_datasets(session: deps.ReadSession, query: Annotated[ImageDatasetHttpQuery, Query()]):
    if query.image_query:
        return DatasetImagePage.model_validate(
            data.search_image_datasets(session, DatasetSearch.model_validate(query.model_dump(exclude={"image_query", "q"}))), strict=False
        )
    return data.list_datasets(
        session=session, **{key: value for key, value in query.model_dump().items() if key in DatasetQuery.model_fields}
    )


@router.get(
    "/datasets/{dataset_id}",
    response_model=DatasetOut,
    dependencies=[Depends(deps.authenticate)],
    operation_id="get_dataset_api_v1_datasets__dataset_id__get",
)
def get_dataset(dataset_id: UUID, session: deps.ReadSession) -> DatasetOut:
    return data.get_dataset(dataset_id=dataset_id, session=session)


@router.patch(
    "/datasets/{dataset_id}",
    response_model=DatasetOut | DatasetImageDetail,
    dependencies=[Depends(deps.authenticate)],
    operation_id="patch_dataset_api_v1_datasets__dataset_id__patch",
)
def patch_dataset(dataset_id: UUID, body: DatasetPatch | ImageDatasetUpdate, session: deps.WriteSession):
    if isinstance(body, ImageDatasetUpdate):
        return DatasetImageDetail.model_validate(
            data.update_image_dataset(session, dataset_id, body.expected_revision, body.changes), strict=False
        )
    return data.update_dataset(dataset_id=dataset_id, body=body, session=session)


@router.patch(
    "/datasets/{dataset_id}/member-parameters",
    response_model=DatasetMemberParametersUpdateOut,
    dependencies=[Depends(deps.authenticate)],
    operation_id="update_dataset_member_parameters_api_v1_datasets__dataset_id__member_parameters_patch",
)
def update_dataset_member_parameters(
    dataset_id: UUID, body: DatasetMemberParametersUpdate, session: deps.WriteSession
) -> DatasetMemberParametersUpdateOut:
    return data.update_dataset_member_parameters(dataset_id=dataset_id, body=body, session=session)


@router.put(
    "/datasets/{dataset_id}/members",
    response_model=DatasetOut,
    dependencies=[Depends(deps.authenticate)],
    operation_id="replaceDatasetMembers",
)
def replace_dataset_members(dataset_id: UUID, body: DatasetMembersCreate, session: deps.WriteSession) -> DatasetOut:
    return data.update_dataset_members(dataset_id=dataset_id, body=body, session=session)


@router.get(
    "/datasets/{dataset_id}/members",
    response_model=DatasetImageMemberPage | DatasetMemberPage,
    operation_id="listDatasetMembers",
    dependencies=[Depends(deps.authenticate)],
)
def list_dataset_members(dataset_id: UUID, session: deps.ReadSession, query: Annotated[ImageDatasetMemberHttpQuery, Query()]):
    if query.image_query:
        values = {key: value for key, value in query.model_dump().items() if key in DatasetMemberSearch.model_fields}
        for key in ("calibration_status", "frame_class", "frame_type", "camera_id", "telescope_id", "filter_id", "parameter_mode"):
            if isinstance(values.get(key), list):
                if len(values[key]) > 1:
                    raise ApiError(
                        422,
                        "VALIDATION_ERROR",
                        f"{key} accepts one value in image queries.",
                        message_key="accepts_one_value_in_image_queries",
                        message_params={"key": key},
                    )
                values[key] = values[key][0] if values[key] else None
        return DatasetImageMemberPage.model_validate(
            data.list_image_dataset_members(session, dataset_id, DatasetMemberSearch.model_validate(values)), strict=False
        )
    legacy = {key: value for key, value in query.model_dump().items() if key in DatasetMemberQuery.model_fields}
    return data.list_dataset_members(session=session, dataset_id=dataset_id, query=DatasetMemberQuery.model_validate(legacy))
