"""HTTP display-preview scheduling and status adaptation."""
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

import astrophotoflow.interfaces.http.dependencies as deps
from astrophotoflow.contracts.previews import DisplayPreviewState
from astrophotoflow.contracts.thumbnails import ThumbnailBatchCreate, ThumbnailBatchOut, ThumbnailRetry
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.public import library_preview_version, project_preview_version, read_dataset_thumbnail

router = APIRouter(prefix="/api/v1", responses=deps.ERROR_RESPONSES)


@router.post("/thumbnail-batches", response_model=ThumbnailBatchOut, dependencies=[Depends(deps.authenticate)], operation_id="create_thumbnail_batch_api_v1_thumbnail_batches_post")
def create_thumbnail_batch(body: ThumbnailBatchCreate, request: Request, admission: deps.TaskAdmission):
    return request.app.state.thumbnails.submit(body)


@router.get("/thumbnail-batches/{request_id}", response_model=ThumbnailBatchOut, dependencies=[Depends(deps.authenticate)], operation_id="get_thumbnail_batch_api_v1_thumbnail_batches_request_id_get")
def get_thumbnail_batch(request_id: UUID, request: Request, limit: deps.Limit = 50, offset: deps.Offset = 0):
    return request.app.state.thumbnails.status(request_id, limit, offset)


@router.post("/thumbnail-batches/{request_id}/retry", response_model=ThumbnailBatchOut, dependencies=[Depends(deps.authenticate)], operation_id="retry_thumbnail_batch_api_v1_thumbnail_batches_request_id_retry_post")
def retry_thumbnail_batch(request_id: UUID, body: ThumbnailRetry, request: Request, admission: deps.TaskAdmission):
    return request.app.state.thumbnails.retry(request_id, body.item_ids)


@router.get("/datasets/{dataset_id}/versions/{dataset_version_id}/members/{asset_version_id}/thumbnail",
            response_class=Response, dependencies=[Depends(deps.authenticate)],
            responses={200: {"content": {"image/jpeg": {"schema": {"type": "string", "format": "binary"}}}}},
            operation_id="get_dataset_member_thumbnail_api_v1_datasets_versions_members_thumbnail_get")
def dataset_member_thumbnail(dataset_id: UUID, dataset_version_id: UUID, asset_version_id: UUID, request: Request):
    try:
        content = read_dataset_thumbnail(request.app.state.database, request.app.state.settings,
                                        str(dataset_id), str(dataset_version_id), str(asset_version_id))
    except ApiError as exc:
        if exc.status_code == 404:
            request.app.state.thumbnails.ensure_dataset(dataset_id, dataset_version_id)
            request.app.state.thumbnails.prioritize([asset_version_id])
        raise
    return Response(content.content, media_type=content.mime_type, headers={"Cache-Control": "private, max-age=60"})

@router.post("/library/assets/{asset_id}/versions/{version_id}/previews/display", response_model=DisplayPreviewState,
             responses={202: {"model": DisplayPreviewState}}, dependencies=[Depends(deps.authenticate)], operation_id='request_display_api_v1_library_assets__asset_id__versions__version_id__previews_display_post')
def request_display(asset_id: UUID, version_id: UUID, request: Request, response: Response, admission: deps.TaskAdmission, session: deps.ReadSession):
    state = request.app.state.display_previews.schedule(library_preview_version(session, asset_id, version_id))
    response.status_code = 202 if state["status"] == "generating" else 200
    return state

@router.get("/library/assets/{asset_id}/versions/{version_id}/previews/display/status", response_model=DisplayPreviewState,
            dependencies=[Depends(deps.authenticate)], operation_id='display_status_api_v1_library_assets__asset_id__versions__version_id__previews_display_status_get')
def display_status(asset_id: UUID, version_id: UUID, request: Request, session: deps.ReadSession):
    return request.app.state.display_previews.status(library_preview_version(session, asset_id, version_id))

@router.post("/library/assets/{asset_id}/versions/{version_id}/previews/display/auto-stretch", response_model=DisplayPreviewState,
            responses={202: {"model": DisplayPreviewState}}, dependencies=[Depends(deps.authenticate)], operation_id='auto_stretch_api_v1_library_assets__asset_id__versions__version_id__previews_display_auto_stretch_post')
def auto_stretch(asset_id: UUID, version_id: UUID, request: Request, response: Response, admission: deps.TaskAdmission, session: deps.ReadSession):
    state = request.app.state.display_previews.schedule(library_preview_version(session, asset_id, version_id), auto=True)
    response.status_code = 202 if state["status"] == "generating" else 200
    return state

@router.post("/projects/{project_id}/asset-references/{reference_id}/previews/display", response_model=DisplayPreviewState,
             responses={202: {"model": DisplayPreviewState}}, dependencies=[Depends(deps.authenticate)], operation_id='request_project_display_api_v1_projects__project_id__asset_references__reference_id__previews_display_post')
def request_project_display(project_id: UUID, reference_id: UUID, request: Request, response: Response, admission: deps.TaskAdmission, session: deps.ReadSession):
    state = request.app.state.display_previews.schedule(project_preview_version(session, project_id, reference_id))
    response.status_code = 202 if state["status"] == "generating" else 200
    return state

@router.get("/projects/{project_id}/asset-references/{reference_id}/previews/display/status", response_model=DisplayPreviewState,
            dependencies=[Depends(deps.authenticate)], operation_id='project_display_status_api_v1_projects__project_id__asset_references__reference_id__previews_display_status_get')
def project_display_status(project_id: UUID, reference_id: UUID, request: Request, session: deps.ReadSession):
    return request.app.state.display_previews.status(project_preview_version(session, project_id, reference_id))

@router.post("/projects/{project_id}/asset-references/{reference_id}/previews/display/auto-stretch", response_model=DisplayPreviewState,
            responses={202: {"model": DisplayPreviewState}}, dependencies=[Depends(deps.authenticate)], operation_id='project_auto_stretch_api_v1_projects__project_id__asset_references__reference_id__previews_display_auto_stretch_post')
def project_auto_stretch(project_id: UUID, reference_id: UUID, request: Request, response: Response, admission: deps.TaskAdmission, session: deps.ReadSession):
    state = request.app.state.display_previews.schedule(project_preview_version(session, project_id, reference_id), auto=True)
    response.status_code = 202 if state["status"] == "generating" else 200
    return state
