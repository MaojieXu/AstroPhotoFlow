"""HTTP display-preview scheduling and status adaptation."""
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

import astrophotoflow.interfaces.http.dependencies as deps
from astrophotoflow.contracts.previews import DisplayPreviewState
from astrophotoflow.modules.data.public import library_preview_version, project_preview_version

router = APIRouter(prefix="/api/v1", responses=deps.ERROR_RESPONSES)

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
