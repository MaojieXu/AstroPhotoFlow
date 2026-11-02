"""Checked result file/media HTTP surface, independent of software-private records."""
import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import FileResponse

from astrophotoflow.contracts.bundles import AnalysisResult
from astrophotoflow.contracts.media import MediaSelection, MediaState
from astrophotoflow.core.errors import ApiError
from astrophotoflow.interfaces.http.dependencies import ERROR_RESPONSES, TaskAdmission, authenticate
from astrophotoflow.interfaces.http.responses import LeasedFileResponse
from astrophotoflow.modules.data.public import get_result_member, read_result_analysis

router=APIRouter(responses=ERROR_RESPONSES)

def checked_file(settings,prompt,call,port,index,*,full=False):
    checked,member,output=get_result_member(settings,prompt,call,port,index,full=full)
    return checked,{'output_display':member.display},{'type':output.type}

def _media_urls(state, base):
    state = state.model_copy(deep=True)
    for field in ('overview_url', 'tile_url', 'video_url'):
        value = getattr(state, field)
        if value:
            setattr(state, field, f'/astrophotoflow{base}/viewer/{state.key}/{value}')
    return state


output_route = '/api/v1/runs/{prompt_id}/calls/{call_id}/outputs/{output_index}/members/{member_index}'

@router.get(output_route + '/analysis', response_model=list[AnalysisResult], dependencies=[Depends(authenticate)], operation_id='output_analysis_api_v1_runs__prompt_id__calls__call_id__outputs__output_index__members__member_index__analysis_get')
def output_analysis(prompt_id: UUID, call_id: UUID, output_index: int, member_index: int, *, request: Request):
    settings=request.app.state.settings
    checked, _, port = checked_file(settings, prompt_id, call_id, output_index, member_index, full=True)
    if port['type'] != 'APF_ANALYSIS':
        raise ApiError(422, 'INVALID_REFERENCE', '该输出端口不是分析结果。', message_key='this_output_port_is_not_an_analysis_result')
    return read_result_analysis(checked.path)

@router.get(output_route + '/file', response_class=Response, responses={200: {"content": {mime: {"schema": {"type": "string", "format": "binary"}} for mime in ['application/octet-stream']}}}, dependencies=[Depends(authenticate)], operation_id='output_file_api_v1_runs__prompt_id__calls__call_id__outputs__output_index__members__member_index__file_get')
def output_file(prompt_id: UUID, call_id: UUID, output_index: int, member_index: int, admission: TaskAdmission, *, request: Request):
    settings=request.app.state.settings
    checked, _, _ = checked_file(settings, prompt_id, call_id, output_index, member_index, full=True)
    return FileResponse(checked.path, filename=checked.path.name, media_type='application/octet-stream')

@router.get(output_route + '/thumbnail', response_class=Response, responses={200: {"content": {mime: {"schema": {"type": "string", "format": "binary"}} for mime in ['image/jpeg']}}}, dependencies=[Depends(authenticate)], operation_id='output_thumbnail_api_v1_runs__prompt_id__calls__call_id__outputs__output_index__members__member_index__thumbnail_get')
def output_thumbnail(prompt_id: UUID, call_id: UUID, output_index: int, member_index: int, admission: TaskAdmission, *, request: Request):
    settings=request.app.state.settings
    checked, record, _ = checked_file(settings, prompt_id, call_id, output_index, member_index)
    path, release = request.app.state.media_views.thumbnail_output(checked, direct=record.get('output_display', 'direct') == 'direct')
    return LeasedFileResponse(path, release, media_type='image/jpeg', headers={'Cache-Control': 'private, max-age=3600'})

@router.post(output_route + '/viewer', response_model=MediaState, dependencies=[Depends(authenticate)], operation_id='prepare_output_view_api_v1_runs__prompt_id__calls__call_id__outputs__output_index__members__member_index__viewer_post')
def prepare_output_view(body: MediaSelection, prompt_id: UUID, call_id: UUID, output_index: int, member_index: int,
                        request: Request, response: Response, admission: TaskAdmission):
    settings=request.app.state.settings
    checked, record, _ = checked_file(settings, prompt_id, call_id, output_index, member_index, full=True)
    state = request.app.state.media_views.prepare_output(checked, body, direct=record.get('output_display', 'direct') == 'direct')
    response.status_code = 202 if state.status == 'generating' else 200
    return _media_urls(state, request.url.path.removesuffix('/viewer'))

@router.delete(output_route + '/viewer/consumer/{consumer_id}', status_code=204, dependencies=[Depends(authenticate)], operation_id='release_output_view_api_v1_runs__prompt_id__calls__call_id__outputs__output_index__members__member_index__viewer_consumer__consumer_id__delete')
def release_output_view(prompt_id: UUID, call_id: UUID, output_index: int, member_index: int, consumer_id: UUID, *, request: Request):
    settings=request.app.state.settings
    checked_file(settings, prompt_id, call_id, output_index, member_index)
    request.app.state.media_views.cancel_consumer(str(consumer_id))
    return Response(status_code=204)

@router.get(output_route + '/viewer/{key}/status', response_model=MediaState, dependencies=[Depends(authenticate)], operation_id='output_view_status_api_v1_runs__prompt_id__calls__call_id__outputs__output_index__members__member_index__viewer__key__status_get')
def output_view_status(prompt_id: UUID, call_id: UUID, output_index: int, member_index: int, key: str, request: Request):
    settings=request.app.state.settings
    checked, _, _ = checked_file(settings, prompt_id, call_id, output_index, member_index)
    state = request.app.state.media_views.output_status(checked, key)
    return _media_urls(state, request.url.path.split('/viewer/')[0])

@router.get(output_route + '/viewer/{key}/tiles/{level}/{x}/{y}', response_class=Response, responses={200: {"content": {mime: {"schema": {"type": "string", "format": "binary"}} for mime in ['image/png']}}}, dependencies=[Depends(authenticate)], operation_id='output_view_tile_api_v1_runs__prompt_id__calls__call_id__outputs__output_index__members__member_index__viewer__key__tiles__level___x___y__get')
async def output_view_tile(prompt_id: UUID, call_id: UUID, output_index: int, member_index: int,
                           key: str, level: int, x: int, y: int, request: Request, admission: TaskAdmission):
    settings=request.app.state.settings
    checked, _, _ = await asyncio.to_thread(checked_file, settings, prompt_id, call_id, output_index, member_index)
    service = request.app.state.media_views
    job, release = service.acquire_output(checked, key)
    future = None
    try:
        future = service.tiles.tile_future(job, level, x, y, tracked=True)
        pending = asyncio.wrap_future(future)
        while not pending.done():
            await asyncio.wait({pending}, timeout=0.1)
            if await request.is_disconnected():
                raise asyncio.CancelledError()
        return Response(pending.result(), media_type='image/png', headers={'Cache-Control': 'private, max-age=3600'})
    finally:
        if future is not None:
            service.tiles.release_tile(job, level, x, y, future)
        if future is not None and not future.done():
            future.add_done_callback(lambda _: release())
        else:
            release()

@router.get(output_route + '/viewer/{key}/{file}', response_class=Response, responses={200: {"content": {mime: {"schema": {"type": "string", "format": "binary"}} for mime in ['image/jpeg', 'video/*']}}}, dependencies=[Depends(authenticate)], operation_id='output_view_file_api_v1_runs__prompt_id__calls__call_id__outputs__output_index__members__member_index__viewer__key___file__get')
def output_view_file(prompt_id: UUID, call_id: UUID, output_index: int, member_index: int, key: str, file: str, admission: TaskAdmission, *, request: Request):
    settings=request.app.state.settings
    checked, _, _ = checked_file(settings, prompt_id, call_id, output_index, member_index)
    if file not in {'overview', 'video'}:
        raise ApiError(404, 'RESOURCE_NOT_FOUND', '没有该显示文件。', message_key='the_display_file_does_not_exist')
    job, release = request.app.state.media_views.acquire_output(checked, key)
    try:
        if file == 'video' and job['state']['kind'] != 'video':
            raise ApiError(404, 'RESOURCE_NOT_FOUND', '该显示结果不是视频。', message_key='this_display_result_is_not_a_video')
        path = job['folder'] / 'overview.jpg' if file == 'overview' else job['folder'] / 'playback.mp4' if job['state']['proxy'] else job['path']
        return LeasedFileResponse(path, release, media_type='image/jpeg' if file == 'overview' else job['state']['mime_type'])
    except Exception:
        release()
        raise

