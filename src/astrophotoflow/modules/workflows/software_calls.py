import asyncio
import json
import os
from pathlib import Path
from uuid import UUID

from fastapi import Depends, Query, Request, Response
from fastapi.responses import FileResponse
from pydantic import TypeAdapter

from astrophotoflow.contracts.inputs import CheckedOutput, OutputLocator, ResolvedOutputInput
from astrophotoflow.contracts.bundles import AnalysisResult
from astrophotoflow.contracts.media import MediaSelection, MediaState
from astrophotoflow.contracts.nodes import NodeDefinition
from astrophotoflow.contracts.software import NativeBundleCall, RunCallResult, SoftwareInvocation, SoftwareObservation, SoftwareOperation
from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.http import TaskAdmission, authenticate
from astrophotoflow.modules.data.public import LeasedFileResponse, check_output, render_output_preview, resolve_canvas_inputs
from astrophotoflow.modules.nodes.public import get_definition
from astrophotoflow.modules.software.public import get_bundle_metadata, validate_parameters, cancel_operation, get_package, inspect_operation, invoke_operation


def _record_path(settings, prompt_id: UUID, call_id: UUID) -> Path:
    return settings.workspace / "runs" / str(prompt_id) / "siril" / f"{call_id}.json"


def _save(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(".part")
    part.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(part, path)


def _read(settings, prompt_id: UUID, call_id: UUID):
    path = _record_path(settings, prompt_id, call_id)
    if not path.is_file():
        raise ApiError(404, "RESOURCE_NOT_FOUND", "未找到本次软件调用。")
    value = json.loads(path.read_text(encoding="utf-8"))
    return value


def _record_ports(record):
    if 'ports' in record:
        return record['ports']
    files = record.get('checked_outputs', [])
    return [{'name': 'image', 'type': 'APF_SCIENCE', 'files': files, 'supporting_files': []}] if files else []


def _checked_file(settings, prompt_id, call_id, output_index, member_index, *, full=False):
    record = _read(settings, prompt_id, call_id)
    if record['state'] != 'completed':
        raise ApiError(409, 'OUTPUT_NOT_READY', '该调用尚未完成完整输出检查。')
    ports = _record_ports(record)
    if output_index < 0 or output_index >= len(ports) or member_index < 0 or member_index >= len(ports[output_index]['files']):
        raise ApiError(404, 'RESOURCE_NOT_FOUND', '没有该输出端口或固定成员。')
    port = ports[output_index]
    checked = CheckedOutput.model_validate_json(json.dumps(port['files'][member_index]))
    work = (settings.workspace / 'runs' / str(prompt_id) / 'work' / str(call_id)).resolve()
    if checked.run_directory.resolve() != work or not checked.path.resolve().is_relative_to(work):
        raise ApiError(422, 'INVALID_REFERENCE', '输出位置不属于该调用。')
    try:
        stamp = checked.path.stat()
        if not checked.path.is_file() or stamp.st_size != checked.byte_size or checked.mtime_ns is not None and stamp.st_mtime_ns != checked.mtime_ns:
            raise ApiError(409, 'SOURCE_CHANGED', '完整结果在检查后发生变化。')
        if full or checked.mtime_ns is None:
            current = check_output(settings, run_directory=work, path=checked.path, expected_format=checked.format,
                                   allow_empty=checked.format == 'other' and checked.byte_size == 0,
                                   colour_layout=(checked.scientific_metadata or {}).get('colour_layout'))
            if current.content_hash != checked.content_hash:
                raise ApiError(409, 'SOURCE_CHANGED', '完整结果内容已变化。')
            checked = current
    except OSError as exc:
        raise ApiError(410, 'OUTPUT_UNAVAILABLE', '完整结果已不在运行工作目录中；旧预览不代表原文件仍可用。') from exc
    return checked, record, port


def _media_urls(state, base):
    state = state.model_copy(deep=True)
    for field in ('overview_url', 'tile_url', 'video_url'):
        value = getattr(state, field)
        if value:
            setattr(state, field, f'/astrophotoflow{base}/viewer/{state.key}/{value}')
    return state


def _analysis_values(path):
    return TypeAdapter(list[AnalysisResult]).validate_json(path.read_bytes())


async def _observed_call(settings, active, prompt_id, call_id):
    record = await asyncio.to_thread(_read, settings, prompt_id, call_id)
    orphan = record['state'] in {'starting', 'running'} and call_id not in active
    if orphan or record['state'] == 'unknown':
        record['state'] = 'unknown'
        if record.get('invocation') and record.get('observation'):
            observed = await inspect_operation(settings, SoftwareInvocation.model_validate_json(json.dumps(record['invocation'])),
                                               SoftwareObservation.model_validate_json(json.dumps(record['observation'])))
            record['observation'] = observed.model_dump(mode='json')
        _save(_record_path(settings, prompt_id, call_id), record)
    return record


def _call_summary(record, prompt_id, call_id):
    operation = record.get('operation') or record.get('invocation') or {}
    bundle = record.get('bundle') or {}
    error = record.get('error') or (record.get('result') or {}).get('error')
    return RunCallResult.model_validate_json(json.dumps(dict(prompt_id=str(prompt_id), call_id=str(call_id), node_id=record['request']['node_id'], state=record['state'],
        workflow_id=record['request'].get('workflow_id'), package_id=operation.get('package_id'), software_version=operation.get('version'),
        bundle_version=bundle.get('version'), bundle_commit=bundle.get('commit'), operation_id=operation.get('operation_id'),
        definition_token=record['request'].get('definition_token'),
        ports=[dict(name=port['name'], type=port['type'], members=len(port['files']), formats=[file['format'] for file in port['files']],
                    names=[Path(file['path']).name for file in port['files']]) for port in _record_ports(record)],
        preview_error=record.get('preview_error'), observation=record.get('observation'), error={'fields': [], **error} if error else None), ensure_ascii=False))


def _resolve_previous(settings, body: NativeBundleCall, locator: OutputLocator, expected):
    expected_type = expected.type
    if locator.run_id != body.prompt_id:
        raise ApiError(422, "INVALID_REFERENCE", "只接受同次原生运行内已检查的科学输出。")
    directory = settings.workspace / "runs" / str(body.prompt_id) / "siril"
    matches = [json.loads(path.read_text(encoding="utf-8")) for path in directory.glob("*.json")]
    matches = [record for record in matches if record["request"]["node_id"] == locator.node_execution_id and record["state"] == "completed"]
    if len(matches) != 1:
        raise ApiError(409, "INVALID_REFERENCE", "上游输出尚未就绪或存在多个调用，无法确认采用哪次输出。")
    record = matches[0]
    ports = record.get('ports')
    if ports is None:
        if locator.output_index != 0 or expected_type != 'APF_SCIENCE':
            raise ApiError(422, 'INVALID_REFERENCE', '旧调用没有请求的具名输出。')
        selected, supporting = record['checked_outputs'], []
    else:
        if locator.output_index >= len(ports) or ports[locator.output_index]['type'] != expected_type:
            raise ApiError(422, 'INVALID_REFERENCE', '上游输出端口不存在或类型不匹配。')
        port = ports[locator.output_index]
        selected, supporting = port['files'], port['supporting_files']
    if locator.member_index is not None:
        if locator.member_index >= len(selected):
            raise ApiError(422, "INVALID_REFERENCE", "上游成员超出固定输出范围。")
        selected = [selected[locator.member_index]]
        supporting = []

    def resolve(index, previous):
        checked = check_output(settings, run_directory=Path(previous["run_directory"]),
                               path=Path(previous["path"]), expected_format=previous['format'],
                               allow_empty=previous['format'] == 'other' and previous['byte_size'] == 0,
                               colour_layout=(previous.get('scientific_metadata') or {}).get('colour_layout') or expected.colour_layout)
        if checked.content_hash != previous["content_hash"]:
            raise ApiError(409, "SOURCE_CHANGED", "上游科学结果已变化。")
        return ResolvedOutputInput(
            kind="run_output", reference_index=0, locator=locator.model_copy(update={"member_index": locator.member_index if locator.member_index is not None else index}),
            read_path=checked.path, format=checked.format, selection={"kind": "whole_file"}, byte_size=checked.byte_size,
            content_hash=checked.content_hash, mtime_ns=checked.path.stat().st_mtime_ns,
            scientific_metadata=checked.scientific_metadata,
        )
    return [resolve(index, previous) for index, previous in enumerate(selected)], [
        resolve(index, previous) for index, previous in enumerate(supporting)
    ]


def _binding(settings, body):
    saved = get_definition(settings.workspace, body.definition_id)
    if saved.content_token != body.definition_token:
        raise ApiError(409, "NODE_CONTENT_CONFLICT", "节点定义已变化，请重新加载节点。")
    binding = saved.definition.execution
    if set(body.parameters) != {p.name for p in saved.definition.parameters}:
        raise ApiError(422, "VALIDATION_ERROR", "节点参数与定义不一致。")
    values = {name: body.parameters[source.name] if source.kind == "parameter" else source.value for name, source in binding.parameters.items()}
    operation = validate_parameters(settings, binding.package_id, binding.operation_id, values)
    return saved.definition, operation, values


def _references(definition, body, operation):
    if body.reference is not None:
        if len(definition.inputs) != 1:
            raise ApiError(422, 'INVALID_REFERENCE', '多输入节点需要具名输入。')
        references = {definition.inputs[0].name: body.reference}
    else:
        references = body.inputs
    if not set(references).issubset({port.name for port in definition.inputs}):
        raise ApiError(422, 'INVALID_REFERENCE', '输入端口与节点定义不匹配。')
    result = {name: references[port] for name, port in definition.execution.inputs.items() if port in references}
    if any(item.required and item.name not in result for item in operation.inputs):
        raise ApiError(422, 'INVALID_REFERENCE', '节点缺少必要输入。')
    for item in operation.inputs:
        if item.name in result and isinstance(result[item.name], list) != item.multiple_connections:
            raise ApiError(422, 'INVALID_REFERENCE', '输入连接数量形式与端口定义不匹配。')
    return result


async def _run(app, settings, body: NativeBundleCall):
    path = _record_path(settings, body.prompt_id, body.call_id)
    record = _read(settings, body.prompt_id, body.call_id)
    work = settings.workspace / "runs" / str(body.prompt_id) / "work" / str(body.call_id)
    try:
        definition = NodeDefinition.model_validate(record['definition'])
        operation = SoftwareOperation.model_validate(record['operation'])
        parameters = record['parameters']
        inputs, supporting = {}, {}
        for name, reference_value in _references(definition, body, operation).items():
            expected = next(item for item in operation.inputs if item.name == name)
            inputs[name], supporting[name] = [], []
            for group_index, reference in enumerate(reference_value if isinstance(reference_value, list) else [reference_value]):
                if reference.kind == 'run_output':
                    items, supporting_items = await asyncio.to_thread(_resolve_previous, settings, body, reference, expected)
                else:
                    if expected.type not in {'APF_SCIENCE', 'APF_FILE'}:
                        raise ApiError(422, 'INVALID_REFERENCE', '该端口需要本次运行中已固定的文件输出。')
                    resolved = await asyncio.to_thread(resolve_canvas_inputs, app.state.database, settings, reference,
                                                       run_directory=work.parent / (str(body.call_id) + '-inputs') / name / str(group_index),
                                                       colour_layout=expected.colour_layout)
                    items, supporting_items = resolved.items, []
                inputs[name].extend(item.model_copy(update={'reference_index': group_index}) for item in items)
                supporting[name].extend(item.model_copy(update={'reference_index': group_index}) for item in supporting_items)
        invocation = SoftwareInvocation(
            run_id=body.prompt_id, node_execution_id=body.node_id, call_id=body.call_id,
            package_id=operation.package_id, version=operation.version, operation_id=operation.operation_id, operation_content_token=operation.content_token,
            bundle_commit=record['bundle']['commit'],
            inputs=inputs, supporting_inputs=supporting, parameters=parameters,
            work_directory=work,
        )
        record["invocation"] = invocation.model_dump(mode="json")

        async def observe(observation):
            record["state"] = 'running' if observation.state == 'completed' else observation.state
            record["observation"] = observation.model_dump(mode="json")
            _save(path, record)

        result = await invoke_operation(settings, invocation, observe)
        record["result"] = result.model_dump(mode="json")
        record["state"] = "running" if result.state == "completed" else result.state
        _save(path, record)
        if result.state == "completed":
            preview_directory = settings.workspace / "output" / "apf-siril" / str(body.prompt_id) / str(body.call_id)
            preview_directory.mkdir(parents=True, exist_ok=True)
            for index, port in enumerate(definition.outputs):
                output_name = definition.execution.outputs[port.name]
                output_definition = next(item for item in operation.outputs if item.name == output_name)
                checked_files, checked_supporting = [], []
                for produced_files, checked_group in [(result.outputs[output_name], checked_files),
                                                      (result.supporting_outputs.get(output_name, []), checked_supporting)]:
                    for produced in produced_files:
                        checked = await asyncio.to_thread(check_output, settings, run_directory=work,
                                                          path=produced.path, expected_format=produced.format,
                                                          allow_empty=produced.allow_empty,
                                                          expected_frames=produced.frame_count,
                                                          colour_layout=output_definition.colour_layout if produced.format == 'fits' else None)
                        checked_group.append(checked.model_dump(mode='json'))
                        if checked_group is checked_files and port.type == 'APF_ANALYSIS':
                            await asyncio.to_thread(_analysis_values, checked.path)
                record['ports'].append({'name': port.name, 'type': port.type, 'files': checked_files,
                                        'supporting_files': checked_supporting})
                record['outputs'].append(OutputLocator(kind='run_output', run_id=body.prompt_id,
                    node_execution_id=body.node_id, output_index=index).model_dump(mode='json'))
                if port.type == 'APF_SCIENCE' and checked_files:
                    try:
                        filename = f'preview-{index}.jpg'
                        first = result.outputs[output_name][0]
                        checked = await asyncio.to_thread(check_output, settings, run_directory=work,
                                                          path=first.path, expected_format=first.format,
                                                          colour_layout=output_definition.colour_layout if first.format == 'fits' else None)
                        await asyncio.to_thread(render_output_preview, checked, preview_directory / filename,
                                                max_edge=1024, auto_stretch=record['output_display'] == 'auto')
                        record['images'].append({'filename': filename,
                            'subfolder': f'apf-siril/{body.prompt_id}/{body.call_id}', 'type': 'output'})
                    except (ApiError, OSError, ValueError) as exc:
                        record['preview_error'] = str(exc)
            record["state"] = "completed"
    except asyncio.CancelledError:
        record["state"] = "cancelled"
    except Exception as exc:
        record["state"] = "failed"
        record["error"] = {"code": exc.code if isinstance(exc, ApiError) else "SOFTWARE_EXECUTION_FAILED", "message": str(exc), 'fields': []}
    finally:
        _save(path, record)


def register_siril_calls(app, settings):
    app.state.siril_calls = {}

    @app.get('/api/v1/runs/{prompt_id}/calls', response_model=list[RunCallResult], dependencies=[Depends(authenticate)])
    async def list_call_results(prompt_id: UUID, node_id: str | None = None, limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0)):
        values = []
        seen = 0
        directory = settings.workspace / 'runs' / str(prompt_id) / 'siril'
        for path in sorted(directory.glob('*.json')):
            call_id = UUID(path.stem)
            record = await _observed_call(settings, app.state.siril_calls, prompt_id, call_id)
            if node_id is not None and record['request']['node_id'] != node_id:
                continue
            if seen >= offset and len(values) < limit:
                values.append(_call_summary(record, prompt_id, call_id))
            seen += 1
            if len(values) == limit:
                break
        return values

    @app.get('/api/v1/runs/{prompt_id}/calls/{call_id}', response_model=RunCallResult, dependencies=[Depends(authenticate)])
    async def call_result(prompt_id: UUID, call_id: UUID):
        return _call_summary(await _observed_call(settings, app.state.siril_calls, prompt_id, call_id), prompt_id, call_id)

    @app.get('/api/v1/runs/{prompt_id}/calls/{call_id}/log', dependencies=[Depends(authenticate)])
    def call_log(prompt_id: UUID, call_id: UUID):
        _read(settings, prompt_id, call_id)
        path = settings.workspace / 'runs' / str(prompt_id) / 'work' / str(call_id) / 'siril.log'
        if not path.is_file():
            raise ApiError(404, 'RESOURCE_NOT_FOUND', '该调用还没有程序日志。')
        return FileResponse(path, media_type='text/plain', filename='process.log')

    output_route = '/api/v1/runs/{prompt_id}/calls/{call_id}/outputs/{output_index}/members/{member_index}'

    @app.get(output_route + '/analysis', response_model=list[AnalysisResult], dependencies=[Depends(authenticate)])
    def output_analysis(prompt_id: UUID, call_id: UUID, output_index: int, member_index: int):
        checked, _, port = _checked_file(settings, prompt_id, call_id, output_index, member_index, full=True)
        if port['type'] != 'APF_ANALYSIS':
            raise ApiError(422, 'INVALID_REFERENCE', '该输出端口不是分析结果。')
        return _analysis_values(checked.path)

    @app.get(output_route + '/file', dependencies=[Depends(authenticate)])
    def output_file(prompt_id: UUID, call_id: UUID, output_index: int, member_index: int, admission: TaskAdmission):
        checked, _, _ = _checked_file(settings, prompt_id, call_id, output_index, member_index, full=True)
        return FileResponse(checked.path, filename=checked.path.name, media_type='application/octet-stream')

    @app.get(output_route + '/thumbnail', dependencies=[Depends(authenticate)])
    def output_thumbnail(prompt_id: UUID, call_id: UUID, output_index: int, member_index: int, admission: TaskAdmission):
        checked, record, _ = _checked_file(settings, prompt_id, call_id, output_index, member_index)
        path, release = app.state.media_views.thumbnail_output(checked, direct=record.get('output_display', 'direct') == 'direct')
        return LeasedFileResponse(path, release, media_type='image/jpeg', headers={'Cache-Control': 'private, max-age=3600'})

    @app.post(output_route + '/viewer', response_model=MediaState, dependencies=[Depends(authenticate)])
    def prepare_output_view(body: MediaSelection, prompt_id: UUID, call_id: UUID, output_index: int, member_index: int,
                            request: Request, response: Response, admission: TaskAdmission):
        checked, record, _ = _checked_file(settings, prompt_id, call_id, output_index, member_index, full=True)
        state = app.state.media_views.prepare_output(checked, body, direct=record.get('output_display', 'direct') == 'direct')
        response.status_code = 202 if state.status == 'generating' else 200
        return _media_urls(state, request.url.path.removesuffix('/viewer'))

    @app.delete(output_route + '/viewer/consumer/{consumer_id}', status_code=204, dependencies=[Depends(authenticate)])
    def release_output_view(prompt_id: UUID, call_id: UUID, output_index: int, member_index: int, consumer_id: UUID):
        _read(settings, prompt_id, call_id)
        app.state.media_views.cancel_consumer(str(consumer_id))
        return Response(status_code=204)

    @app.get(output_route + '/viewer/{key}/status', response_model=MediaState, dependencies=[Depends(authenticate)])
    def output_view_status(prompt_id: UUID, call_id: UUID, output_index: int, member_index: int, key: str, request: Request):
        checked, _, _ = _checked_file(settings, prompt_id, call_id, output_index, member_index)
        state = app.state.media_views.output_status(checked, key)
        return _media_urls(state, request.url.path.split('/viewer/')[0])

    @app.get(output_route + '/viewer/{key}/tiles/{level}/{x}/{y}', dependencies=[Depends(authenticate)])
    async def output_view_tile(prompt_id: UUID, call_id: UUID, output_index: int, member_index: int,
                               key: str, level: int, x: int, y: int, request: Request, admission: TaskAdmission):
        checked, _, _ = await asyncio.to_thread(_checked_file, settings, prompt_id, call_id, output_index, member_index)
        service = app.state.media_views
        job, release = service.acquire_output(checked, key)
        future = None
        try:
            future = service.tile_future(job, level, x, y, tracked=True)
            pending = asyncio.wrap_future(future)
            while not pending.done():
                await asyncio.wait({pending}, timeout=0.1)
                if await request.is_disconnected():
                    raise asyncio.CancelledError()
            return Response(pending.result(), media_type='image/png', headers={'Cache-Control': 'private, max-age=3600'})
        finally:
            if future is not None:
                service.release_tile(job, level, x, y, future)
            if future is not None and not future.done():
                future.add_done_callback(lambda _: release())
            else:
                release()

    @app.get(output_route + '/viewer/{key}/{file}', dependencies=[Depends(authenticate)])
    def output_view_file(prompt_id: UUID, call_id: UUID, output_index: int, member_index: int, key: str, file: str, admission: TaskAdmission):
        checked, _, _ = _checked_file(settings, prompt_id, call_id, output_index, member_index)
        if file not in {'overview', 'video'}:
            raise ApiError(404, 'RESOURCE_NOT_FOUND', '没有该显示文件。')
        job, release = app.state.media_views.acquire_output(checked, key)
        try:
            if file == 'video' and job['state']['kind'] != 'video':
                raise ApiError(404, 'RESOURCE_NOT_FOUND', '该显示结果不是视频。')
            path = job['folder'] / 'overview.jpg' if file == 'overview' else job['folder'] / 'playback.mp4' if job['state']['proxy'] else job['path']
            return LeasedFileResponse(path, release, media_type='image/jpeg' if file == 'overview' else job['state']['mime_type'])
        except Exception:
            release()
            raise

    @app.post("/internal/native/bundles/calls", dependencies=[Depends(authenticate)], include_in_schema=False)
    async def start(body: NativeBundleCall):
        async with app.state.maintenance_lock:
            if app.state.maintenance or app.state.shutdown_started:
                raise ApiError(409, "WORKBENCH_MAINTENANCE", "工作台正在维护。")
            path = _record_path(settings, body.prompt_id, body.call_id)
            if path.exists():
                record = _read(settings, body.prompt_id, body.call_id)
                if record["request"] != body.model_dump(mode="json"):
                    raise ApiError(409, "SOFTWARE_CONTENT_CONFLICT", "调用 ID 已用于另一份输入。")
                return record
            if any(not task.done() for task in app.state.software_tasks.values()):
                raise ApiError(409, "SOFTWARE_BUSY", "软件包正在维护。")
            definition, operation, parameters = _binding(settings, body)
            _references(definition, body, operation)
            if not operation.ready:
                raise ApiError(503, "SOFTWARE_NOT_READY", operation.reason or "请先安装 Siril。")
            _, entries, _ = get_bundle_metadata(settings, operation.package_id)
            entry = next(item for item in entries if item['operation']['operation_id'] == operation.operation_id)
            package = get_package(settings, operation.package_id)
            record = {"request": body.model_dump(mode="json"), "state": "starting", "result": None,
                      "invocation": None, "observation": None, "ports": [], "outputs": [],
                      'definition': definition.model_dump(mode='json'), 'operation': operation.model_dump(mode='json'),
                      'parameters': parameters,
                      'bundle': {'version': package.bundle_version, 'commit': package.bundle_commit},
                      'output_display': entry.get('output_display', 'direct'),
                      "images": [], "error": None, "preview_error": None}
            _save(path, record)
            task = asyncio.create_task(_run(app, settings, body))
            app.state.siril_calls[body.call_id] = task
            task.add_done_callback(lambda _task: app.state.siril_calls.pop(body.call_id, None))
            return record

    @app.get("/internal/native/bundles/calls/{prompt_id}/{call_id}", dependencies=[Depends(authenticate)], include_in_schema=False)
    async def status(prompt_id: UUID, call_id: UUID):
        record = _read(settings, prompt_id, call_id)
        if record["state"] in {"starting", "running"} and call_id not in app.state.siril_calls:
            record["state"] = "unknown"
        return record

    @app.post("/internal/native/bundles/calls/{prompt_id}/{call_id}/cancel", dependencies=[Depends(authenticate)], include_in_schema=False)
    async def cancel(prompt_id: UUID, call_id: UUID):
        record = _read(settings, prompt_id, call_id)
        result = await cancel_operation(call_id)
        task = app.state.siril_calls.get(call_id)
        if task is not None and record["invocation"] is None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            record["state"] = "cancelled"
            _save(_record_path(settings, prompt_id, call_id), record)
        return result


async def recover_siril_calls(settings):
    for path in (settings.workspace / "runs").glob("*/siril/*.json"):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record["state"] not in {"starting", "running", "unknown"}:
            continue
        if record.get("invocation") and record.get("observation"):
            await inspect_operation(settings, SoftwareInvocation.model_validate_json(json.dumps(record["invocation"])),
                                    SoftwareObservation.model_validate_json(json.dumps(record["observation"])))
        record["state"] = "unknown"
        _save(path, record)
