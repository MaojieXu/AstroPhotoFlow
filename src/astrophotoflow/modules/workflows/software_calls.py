import asyncio
import json
import os
from pathlib import Path
from uuid import UUID

from fastapi import Depends, Request

from astrophotoflow.contracts.inputs import OutputLocator, ResolvedOutputInput
from astrophotoflow.contracts.software import NativeSirilCall, SoftwareInvocation, SoftwareObservation
from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.http import authenticate
from astrophotoflow.modules.data.public import check_output, render_output_preview, resolve_canvas_inputs
from astrophotoflow.modules.software.public import cancel_operation, get_operation, inspect_operation, invoke_operation


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
        raise ApiError(404, "RESOURCE_NOT_FOUND", "未找到本次 Siril 调用。")
    value = json.loads(path.read_text(encoding="utf-8"))
    return value


def _resolve_previous(settings, body: NativeSirilCall):
    locator = body.reference
    if locator.run_id != body.prompt_id or locator.output_index != 0:
        raise ApiError(422, "INVALID_REFERENCE", "只接受同次原生运行内已检查的科学输出。")
    directory = settings.workspace / "runs" / str(body.prompt_id) / "siril"
    matches = [json.loads(path.read_text(encoding="utf-8")) for path in directory.glob("*.json")]
    matches = [record for record in matches if record["request"]["node_id"] == locator.node_execution_id and record["state"] == "completed"]
    if len(matches) != 1:
        raise ApiError(409, "INVALID_REFERENCE", "上游输出尚未就绪或存在多个调用，无法确认采用哪次输出。")
    record = matches[0]
    selected = record["checked_outputs"]
    if locator.member_index is not None:
        if locator.member_index >= len(selected):
            raise ApiError(422, "INVALID_REFERENCE", "上游成员超出固定输出范围。")
        selected = [selected[locator.member_index]]
    items = []
    for index, previous in enumerate(selected):
        checked = check_output(settings, run_directory=Path(previous["run_directory"]),
                               path=Path(previous["path"]), expected_format="fits")
        if checked.content_hash != previous["content_hash"]:
            raise ApiError(409, "SOURCE_CHANGED", "上游科学结果已变化。")
        items.append(ResolvedOutputInput(
            kind="run_output", reference_index=0, locator=locator.model_copy(update={"member_index": index}),
            read_path=checked.path, format="fits", selection={"kind": "whole_file"}, byte_size=checked.byte_size,
            content_hash=checked.content_hash, mtime_ns=checked.path.stat().st_mtime_ns,
            scientific_metadata=checked.scientific_metadata,
        ))
    return items


async def _run(app, settings, body: NativeSirilCall):
    path = _record_path(settings, body.prompt_id, body.call_id)
    record = _read(settings, body.prompt_id, body.call_id)
    work = settings.workspace / "runs" / str(body.prompt_id) / "work" / str(body.call_id)
    try:
        if body.reference.kind == "run_output":
            items = await asyncio.to_thread(_resolve_previous, settings, body)
        else:
            resolved = await asyncio.to_thread(resolve_canvas_inputs, app.state.database, settings, body.reference,
                                               run_directory=work.parent / (str(body.call_id) + "-inputs"))
            items = resolved.items
        operation = get_operation(settings, "siril", "1.4.4", "autostretch")
        invocation = SoftwareInvocation(
            run_id=body.prompt_id, node_execution_id=body.node_id, call_id=body.call_id,
            package_id="siril", version="1.4.4", operation_id="autostretch", operation_content_token=operation.content_token,
            inputs={"image": items}, parameters={"linked": body.linked, "shadowsclip": body.shadowsclip, "targetbg": body.targetbg},
            work_directory=work,
        )
        record["invocation"] = invocation.model_dump(mode="json")

        async def observe(observation):
            record["state"] = observation.state
            record["observation"] = observation.model_dump(mode="json")
            _save(path, record)

        result = await invoke_operation(settings, invocation, observe)
        record["result"] = result.model_dump(mode="json")
        record["state"] = "running" if result.state == "completed" else result.state
        if result.state == "completed":
            for produced in result.outputs["image"]:
                checked = await asyncio.to_thread(check_output, settings, run_directory=work, path=produced.path, expected_format="fits")
                record["checked_outputs"].append(checked.model_dump(mode="json"))
            record["output"] = OutputLocator(kind="run_output", run_id=body.prompt_id, node_execution_id=body.node_id,
                                               output_index=0).model_dump(mode="json")
            _save(path, record)
            preview_directory = settings.workspace / "output" / "apf-siril" / str(body.prompt_id) / str(body.call_id)
            preview_directory.mkdir(parents=True, exist_ok=True)
            first = result.outputs["image"][0]
            try:
                checked = await asyncio.to_thread(check_output, settings, run_directory=work, path=first.path, expected_format="fits")
                await asyncio.to_thread(render_output_preview, checked, preview_directory / "preview.jpg", max_edge=1024, auto_stretch=False)
                record["images"] = [{"filename": "preview.jpg", "subfolder": f"apf-siril/{body.prompt_id}/{body.call_id}", "type": "output"}]
            except (ApiError, OSError, ValueError) as exc:
                record["preview_error"] = str(exc)
            record["state"] = "completed"
    except asyncio.CancelledError:
        record["state"] = "cancelled"
    except (ApiError, OSError, ValueError) as exc:
        record["state"] = "failed"
        record["error"] = {"code": exc.code if isinstance(exc, ApiError) else "SOFTWARE_EXECUTION_FAILED", "message": str(exc)}
    finally:
        _save(path, record)


def register_siril_calls(app, settings):
    app.state.siril_calls = {}

    @app.post("/internal/native/siril/calls", dependencies=[Depends(authenticate)], include_in_schema=False)
    async def start(body: NativeSirilCall):
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
            operation = get_operation(settings, "siril", "1.4.4", "autostretch")
            if not operation.ready:
                raise ApiError(503, "SOFTWARE_NOT_READY", operation.reason or "请先安装 Siril。")
            record = {"request": body.model_dump(mode="json"), "state": "starting", "result": None,
                      "invocation": None, "observation": None, "checked_outputs": [], "output": None,
                      "images": [], "error": None, "preview_error": None}
            _save(path, record)
            task = asyncio.create_task(_run(app, settings, body))
            app.state.siril_calls[body.call_id] = task
            task.add_done_callback(lambda _task: app.state.siril_calls.pop(body.call_id, None))
            return record

    @app.get("/internal/native/siril/calls/{prompt_id}/{call_id}", dependencies=[Depends(authenticate)], include_in_schema=False)
    async def status(prompt_id: UUID, call_id: UUID):
        record = _read(settings, prompt_id, call_id)
        if record["state"] in {"starting", "running"} and call_id not in app.state.siril_calls:
            record["state"] = "unknown"
        return record

    @app.post("/internal/native/siril/calls/{prompt_id}/{call_id}/cancel", dependencies=[Depends(authenticate)], include_in_schema=False)
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
            await inspect_operation(settings, SoftwareInvocation.model_validate(record["invocation"]),
                                    SoftwareObservation.model_validate(record["observation"]))
        record["state"] = "unknown"
        _save(path, record)
