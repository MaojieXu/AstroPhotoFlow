"""HTTP viewing, tile cancellation and delivery; source ownership stays in data."""

import asyncio
from uuid import UUID
from fastapi import APIRouter, Depends, Request, Response
import astrophotoflow.interfaces.http.dependencies as deps
from astrophotoflow.contracts.media import MediaSelection, MediaState
from astrophotoflow.core.errors import not_found
from astrophotoflow.interfaces.http.responses import LeasedFileResponse
from astrophotoflow.modules.data.public import library_preview_asset, project_preview_asset

router = APIRouter(prefix="/api/v1", responses=deps.ERROR_RESPONSES, dependencies=[Depends(deps.authenticate)])


def _asset(request, session, asset_id=None, project_id=None, reference_id=None):
    return (
        project_preview_asset(session, project_id, reference_id)
        if "/projects/" in request.url.path
        else library_preview_asset(session, asset_id)
    )


def _base(request):
    return str(request.url.path).split("/viewer")[0] + "/viewer"


def _urls(state, base):
    state = state.model_copy(deep=True)
    for field in ("overview_url", "tile_url", "video_url"):
        if value := getattr(state, field):
            setattr(state, field, f"/astrophotoflow{base}/{state.key}/{value}")
    return state


@router.delete(
    "/library/assets/{asset_id}/previews/viewer/consumer/{consumer_id}",
    status_code=204,
    operation_id="cancel_media_consumer_api_v1_library_assets__asset_id__previews_viewer_consumer__consumer_id__delete",
)
@router.delete(
    "/projects/{project_id}/asset-references/{reference_id}/previews/viewer/consumer/{consumer_id}",
    status_code=204,
    operation_id="cancel_media_consumer_api_v1_projects__project_id__asset_references__reference_id__previews_viewer_consumer__consumer_id__delete",
)
def cancel_media_consumer(
    consumer_id: UUID,
    request: Request,
    session: deps.ReadSession,
    asset_id: UUID | None = None,
    project_id: UUID | None = None,
    reference_id: UUID | None = None,
):
    _asset(request, session, asset_id, project_id, reference_id)
    request.app.state.media_views.cancel_consumer(str(consumer_id))
    return Response(status_code=204)


@router.post(
    "/library/assets/{asset_id}/previews/viewer",
    response_model=MediaState,
    operation_id="prepare_media_api_v1_library_assets__asset_id__previews_viewer_post",
)
@router.post(
    "/projects/{project_id}/asset-references/{reference_id}/previews/viewer",
    response_model=MediaState,
    operation_id="prepare_media_api_v1_projects__project_id__asset_references__reference_id__previews_viewer_post",
)
def prepare_media(
    body: MediaSelection,
    request: Request,
    response: Response,
    admission: deps.TaskAdmission,
    session: deps.ReadSession,
    asset_id: UUID | None = None,
    project_id: UUID | None = None,
    reference_id: UUID | None = None,
):
    state = request.app.state.media_views.prepare(_asset(request, session, asset_id, project_id, reference_id), body)
    response.status_code = 202 if state.status == "generating" else 200
    return _urls(state, _base(request))


@router.get(
    "/library/assets/{asset_id}/previews/viewer/{key}/status",
    response_model=MediaState,
    operation_id="media_status_api_v1_library_assets__asset_id__previews_viewer__key__status_get",
)
@router.get(
    "/projects/{project_id}/asset-references/{reference_id}/previews/viewer/{key}/status",
    response_model=MediaState,
    operation_id="media_status_api_v1_projects__project_id__asset_references__reference_id__previews_viewer__key__status_get",
)
def media_status(
    key: str,
    request: Request,
    session: deps.ReadSession,
    asset_id: UUID | None = None,
    project_id: UUID | None = None,
    reference_id: UUID | None = None,
):
    return _urls(request.app.state.media_views.status(_asset(request, session, asset_id, project_id, reference_id), key), _base(request))


@router.get(
    "/library/assets/{asset_id}/previews/viewer/{key}/tiles/{level}/{x}/{y}",
    response_class=Response,
    responses={200: {"content": {mime: {"schema": {"type": "string", "format": "binary"}} for mime in ["image/png"]}}},
    operation_id="media_tile_api_v1_library_assets__asset_id__previews_viewer__key__tiles__level___x___y__get",
)
@router.get(
    "/projects/{project_id}/asset-references/{reference_id}/previews/viewer/{key}/tiles/{level}/{x}/{y}",
    response_class=Response,
    responses={200: {"content": {mime: {"schema": {"type": "string", "format": "binary"}} for mime in ["image/png"]}}},
    operation_id="media_tile_api_v1_projects__project_id__asset_references__reference_id__previews_viewer__key__tiles__level___x___y__get",
)
async def media_tile(
    key: str,
    level: int,
    x: int,
    y: int,
    request: Request,
    admission: deps.TaskAdmission,
    session: deps.ReadSession,
    asset_id: UUID | None = None,
    project_id: UUID | None = None,
    reference_id: UUID | None = None,
):
    if await request.is_disconnected():
        raise asyncio.CancelledError()
    service = request.app.state.media_views
    job, release = service.acquire(_asset(request, session, asset_id, project_id, reference_id), key)
    future = None
    try:
        future = service.tiles.tile_future(job, level, x, y, tracked=True)
        pending = asyncio.wrap_future(future)
        while not pending.done():
            await asyncio.wait({pending}, timeout=0.1)
            if await request.is_disconnected():
                raise asyncio.CancelledError()
        return Response(pending.result(), media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})
    finally:
        if future is not None:
            service.tiles.release_tile(job, level, x, y, future)
        if future is not None and (not future.done()):
            future.add_done_callback(lambda _: release())
        else:
            release()


@router.get(
    "/library/assets/{asset_id}/previews/viewer/{key}/{file}",
    response_class=Response,
    responses={200: {"content": {mime: {"schema": {"type": "string", "format": "binary"}} for mime in ["image/jpeg", "video/*"]}}},
    operation_id="media_file_api_v1_library_assets__asset_id__previews_viewer__key___file__get",
)
@router.get(
    "/projects/{project_id}/asset-references/{reference_id}/previews/viewer/{key}/{file}",
    response_class=Response,
    responses={200: {"content": {mime: {"schema": {"type": "string", "format": "binary"}} for mime in ["image/jpeg", "video/*"]}}},
    operation_id="media_file_api_v1_projects__project_id__asset_references__reference_id__previews_viewer__key___file__get",
)
def media_file(
    key: str,
    file: str,
    request: Request,
    admission: deps.TaskAdmission,
    session: deps.ReadSession,
    asset_id: UUID | None = None,
    project_id: UUID | None = None,
    reference_id: UUID | None = None,
):
    if file not in {"overview", "video"}:
        raise not_found()
    job, release = request.app.state.media_views.acquire(_asset(request, session, asset_id, project_id, reference_id), key)
    try:
        if file == "video" and job["state"]["kind"] != "video":
            raise not_found()
        path = (
            job["folder"] / "overview.jpg"
            if file == "overview"
            else job["folder"] / "playback.mp4"
            if job["state"]["proxy"]
            else job["path"]
        )
        if not path.is_file():
            raise not_found()
        return LeasedFileResponse(path, release, media_type="image/jpeg" if file == "overview" else job["state"]["mime_type"])
    except Exception:
        release()
        raise
