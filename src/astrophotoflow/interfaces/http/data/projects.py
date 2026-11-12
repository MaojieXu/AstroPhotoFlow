from typing import Annotated, Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request, Response
import astrophotoflow.interfaces.http.dependencies as deps
import astrophotoflow.modules.data.public as data
from astrophotoflow.contracts.assets import FitsHduPage, FitsHeaderOut
from astrophotoflow.contracts.metadata import FrameClass
from astrophotoflow.contracts.projects import (
    ProjectAssetReferenceOut,
    ProjectAssetReferencePage,
    ProjectCreate,
    ProjectDatasetReferenceCreate,
    ProjectDatasetReferenceOut,
    ProjectDatasetReferencePage,
    ProjectOut,
    ProjectPage,
    ProjectPatch,
    ProjectQuery,
    ProjectReferenceCreate,
    ProjectReferenceDelete,
    ProjectReferenceDeleteResult,
)
from astrophotoflow.interfaces.http.dependencies import Limit, Offset, Order, ReadSession, SortBy, WriteSession, authenticate
from astrophotoflow.interfaces.http.responses import preview_response

router = APIRouter(prefix="/api/v1", responses=deps.ERROR_RESPONSES)


@router.get("/projects", response_model=ProjectPage, dependencies=[Depends(authenticate)], operation_id="list_projects_api_v1_projects_get")
def list_projects(session: ReadSession, query: Annotated[ProjectQuery, Query()]) -> ProjectPage:
    return data.list_projects(session=session, **query.model_dump())


@router.post(
    "/projects",
    response_model=ProjectOut,
    status_code=201,
    dependencies=[Depends(authenticate)],
    operation_id="create_project_api_v1_projects_post",
)
def create_project(body: ProjectCreate, session: WriteSession) -> ProjectOut:
    return data.create_project(body=body, session=session)


@router.get("/projects/{project_id}", response_model=ProjectOut, dependencies=[Depends(authenticate)], operation_id="getProject")
def read_project(project_id: UUID, session: ReadSession) -> ProjectOut:
    return data.get_project(project_id=project_id, session=session)


@router.patch(
    "/projects/{project_id}",
    response_model=ProjectOut,
    dependencies=[Depends(authenticate)],
    operation_id="patch_project_api_v1_projects__project_id__patch",
)
def patch_project(project_id: UUID, body: ProjectPatch, session: WriteSession) -> ProjectOut:
    return data.update_project(project_id=project_id, body=body, session=session)


@router.get(
    "/projects/{project_id}/assets",
    response_model=ProjectAssetReferencePage,
    dependencies=[Depends(authenticate)],
    operation_id="list_project_assets_api_v1_projects__project_id__assets_get",
)
def list_project_assets(
    project_id: UUID,
    session: ReadSession,
    limit: Limit = 50,
    offset: Offset = 0,
    sort_by: SortBy = "created_at",
    order: Order = "desc",
    q: str | None = None,
    role: Literal["raw", "calibration", "intermediate", "final"] | None = None,
    frame_type: Literal["light", "bias", "dark", "flat", "dark_flat"] | None = None,
    calibration_level: Literal["individual", "master"] | None = None,
    camera_id: UUID | None = None,
    optical_system_id: UUID | None = None,
    filter_id: UUID | None = None,
    frame_class: FrameClass | None = None,
) -> ProjectAssetReferencePage:
    return data.list_project_assets(
        project_id=project_id,
        session=session,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        order=order,
        q=q,
        role=role,
        frame_type=frame_type,
        calibration_level=calibration_level,
        camera_id=camera_id,
        optical_system_id=optical_system_id,
        filter_id=filter_id,
        frame_class=frame_class,
    )


@router.get(
    "/projects/{project_id}/asset-references/{reference_id}",
    response_model=ProjectAssetReferenceOut,
    dependencies=[Depends(authenticate)],
    operation_id="get_project_asset_reference_api_v1_projects__project_id__asset_references__reference_id__get",
)
def get_project_asset_reference(project_id: UUID, reference_id: UUID, session: ReadSession) -> ProjectAssetReferenceOut:
    return data.get_project_asset_reference(project_id=project_id, reference_id=reference_id, session=session)


@router.get(
    "/projects/{project_id}/dataset-references",
    response_model=ProjectDatasetReferencePage,
    dependencies=[Depends(deps.authenticate)],
    operation_id="list_project_dataset_references_api_v1_projects__project_id__dataset_references_get",
)
def list_project_dataset_references(
    project_id: UUID,
    session: deps.ReadSession,
    limit: deps.Limit = 50,
    offset: deps.Offset = 0,
    sort_by: deps.SortBy = "created_at",
    order: deps.Order = "desc",
) -> ProjectDatasetReferencePage:
    return data.list_project_dataset_references(
        project_id=project_id, session=session, limit=limit, offset=offset, sort_by=sort_by, order=order
    )


@router.get(
    "/projects/{project_id}/datasets",
    response_model=ProjectDatasetReferencePage,
    dependencies=[Depends(deps.authenticate)],
    operation_id="list_project_datasets_api_v1_projects__project_id__datasets_get",
)
def list_project_datasets(
    project_id: UUID, session: deps.ReadSession, limit: deps.Limit = 50, offset: deps.Offset = 0
) -> ProjectDatasetReferencePage:
    return data.list_project_datasets(project_id=project_id, session=session, limit=limit, offset=offset)


@router.post(
    "/projects/{project_id}/dataset-references",
    response_model=ProjectDatasetReferenceOut,
    status_code=201,
    dependencies=[Depends(deps.authenticate)],
    operation_id="add_project_dataset_reference_api_v1_projects__project_id__dataset_references_post",
)
def add_project_dataset_reference(
    project_id: UUID, body: ProjectDatasetReferenceCreate, session: deps.WriteSession
) -> ProjectDatasetReferenceOut:
    return data.add_project_dataset_reference(project_id=project_id, body=body, session=session)


@router.get(
    "/projects/{project_id}/dataset-references/{reference_id}",
    response_model=ProjectDatasetReferenceOut,
    dependencies=[Depends(deps.authenticate)],
    operation_id="get_project_dataset_reference_api_v1_projects__project_id__dataset_references__reference_id__get",
)
def get_project_dataset_reference(project_id: UUID, reference_id: UUID, session: deps.ReadSession) -> ProjectDatasetReferenceOut:
    return data.get_project_dataset_reference(project_id=project_id, reference_id=reference_id, session=session)


@router.delete(
    "/projects/{project_id}/dataset-references/{reference_id}",
    response_model=ProjectReferenceDeleteResult,
    dependencies=[Depends(deps.authenticate)],
    operation_id="remove_project_dataset_reference_api_v1_projects__project_id__dataset_references__reference_id__delete",
)
def remove_project_dataset_reference(
    project_id: UUID, reference_id: UUID, body: ProjectReferenceDelete, session: deps.WriteSession
) -> ProjectReferenceDeleteResult:
    return data.remove_project_dataset_reference(project_id=project_id, reference_id=reference_id, body=body, session=session)


@router.post(
    "/projects/{project_id}/asset-references",
    response_model=ProjectAssetReferenceOut,
    status_code=201,
    dependencies=[Depends(deps.authenticate)],
    operation_id="add_project_asset_reference_api_v1_projects__project_id__asset_references_post",
)
def add_project_asset_reference(project_id: UUID, body: ProjectReferenceCreate, session: deps.WriteSession) -> ProjectAssetReferenceOut:
    return data.add_project_asset_reference(project_id=project_id, body=body, session=session)


@router.delete(
    "/projects/{project_id}/asset-references/{reference_id}",
    response_model=ProjectReferenceDeleteResult,
    dependencies=[Depends(deps.authenticate)],
    operation_id="remove_project_asset_reference_api_v1_projects__project_id__asset_references__reference_id__delete",
)
def remove_project_asset_reference(
    project_id: UUID, reference_id: UUID, body: ProjectReferenceDelete, session: deps.WriteSession
) -> ProjectReferenceDeleteResult:
    return data.remove_project_asset_reference(project_id=project_id, reference_id=reference_id, body=body, session=session)


@router.get(
    "/projects/{project_id}/asset-references/{reference_id}/hdus",
    response_model=FitsHduPage,
    dependencies=[Depends(deps.authenticate)],
    operation_id="list_project_reference_hdus_api_v1_projects__project_id__asset_references__reference_id__hdus_get",
)
def list_project_reference_hdus(
    project_id: UUID, reference_id: UUID, session: deps.ReadSession, limit: deps.Limit = 200, offset: deps.Offset = 0
) -> FitsHduPage:
    return data.list_project_reference_hdus(project_id=project_id, reference_id=reference_id, session=session, limit=limit, offset=offset)


@router.get(
    "/projects/{project_id}/asset-references/{reference_id}/hdus/{hdu_index}/header",
    response_model=FitsHeaderOut,
    dependencies=[Depends(deps.authenticate)],
    operation_id="get_project_reference_header_api_v1_projects__project_id__asset_references__reference_id__hdus__hdu_index__header_get",
)
def get_project_reference_header(project_id: UUID, reference_id: UUID, hdu_index: int, session: deps.ReadSession) -> FitsHeaderOut:
    return data.get_project_reference_header(project_id=project_id, reference_id=reference_id, hdu_index=hdu_index, session=session)


@router.get(
    "/projects/{project_id}/asset-references/{reference_id}/previews/{size}",
    response_class=Response,
    responses={200: {"content": {"image/jpeg": {"schema": {"type": "string", "format": "binary"}}}}},
    dependencies=[Depends(deps.authenticate)],
    operation_id="get_project_reference_preview_api_v1_projects__project_id__asset_references__reference_id__previews__size__get",
)
def get_project_reference_preview(project_id: UUID, reference_id: UUID, size: str, request: Request, session: deps.ReadSession) -> Response:
    reference = data.get_project_preview_reference(session, project_id, reference_id)
    return preview_response(request, reference, size)
