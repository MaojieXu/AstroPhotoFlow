import hashlib
import json
import os
import subprocess
import tempfile
import asyncio
import codecs
from dataclasses import dataclass, field
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from importlib.resources import files
from pathlib import Path
from typing import Any, Awaitable, Callable
from uuid import UUID

import httpx
import psutil
from pydantic import JsonValue

from astrophotoflow.contracts.software import (
    SirilCommand, SoftwareOperation, SoftwarePackage, SoftwarePackageState, SoftwarePreparation,
    ParameterDefinition, ProducedFile, SoftwareInvocation, SoftwareObservation, SoftwareResult, SoftwareCancelResult, SoftwareUse,
)
from astrophotoflow.contracts.common import ErrorDetail
from astrophotoflow.contracts.bundles import NamedProcessPlan, ProcessPlan
from astrophotoflow.core.config import Settings
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.software import bundles


_PACKAGE_LOCKS: dict[str, asyncio.Lock] = {}


@dataclass
class _Call:
    invocation: SoftwareInvocation
    observation: SoftwareObservation
    process: asyncio.subprocess.Process | None = None
    cancelled: bool = False
    descendants: dict[int, float] = field(default_factory=dict)
    inspection_unknown: bool = False


_CALLS: dict[UUID, _Call] = {}
_LIVE_PREVIEWS: dict[UUID, tuple[str, asyncio.subprocess.Process | None]] = {}


class _ObservationFailed(RuntimeError):
    pass


def _resource(name: str) -> str:
    return files("astrophotoflow").joinpath("vendor", name).read_text(encoding="utf-8-sig")


def _manifest() -> dict[str, Any]:
    return json.loads(_resource("siril-1.4.4-manifest.json"))


def _state_path(settings, package_id):
    return settings.workspace / "software" / package_id / "state.json"


def _write_package_state(settings, package_id, state):
    path = _state_path(settings, package_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(".part")
    part.write_text(state.model_dump_json(indent=2) + "\n", encoding="utf-8")
    os.replace(part, path)


def _state(package):
    return SoftwarePackageState.model_validate(package.model_dump(include=set(SoftwarePackageState.model_fields)))


@asynccontextmanager
async def maintain_package(package_id: str):
    bundles.release(package_id)
    lock = _PACKAGE_LOCKS.setdefault(package_id, asyncio.Lock())
    if lock.locked() or get_usage(package_id) or get_preview_usage(package_id):
        raise ApiError(409, "SOFTWARE_BUSY", "软件包当前正在维护、运行或预览。")
    await lock.acquire()
    try:
        yield
    finally:
        lock.release()


def get_package(settings: Settings, package_id: str) -> SoftwarePackage:
    release = bundles.release(package_id)
    manifest, operations, _ = bundles.metadata(settings.workspace, package_id)
    path = _state_path(settings, package_id)
    state = SoftwarePackageState.model_validate_json(path.read_text(encoding="utf-8")) if path.is_file() else SoftwarePackageState(
        installed_version=None, install_path=None, availability="not_installed", reason="尚未安装 Bundle。",
        operation=None, operation_state="idle", phase=None, progress=None, last_error=None, node_definition_ids=[])
    root = path.parent / "bundle"
    lock_path = path.parent / "bundle-lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8")) if lock_path.is_file() else {}
    restart_required = False
    active_lock = _PACKAGE_LOCKS.get(package_id)
    if state.operation_state == 'running' and (active_lock is None or not active_lock.locked()):
        state = state.model_copy(update={'operation_state': 'unknown', 'availability': 'unknown',
                                        'reason': '上次安装或卸载被中断，无法确认结果。'})
    if state.installed_version is not None:
        if not root.is_dir():
            state = state.model_copy(update={"availability": "not_ready", "reason": "现有安装尚未迁移到独立 Bundle，请安装 Bundle；保留原程序。"})
        elif not bundles.contained(root, manifest.executable).is_file():
            state = state.model_copy(update={"availability": "not_ready", "reason": "Bundle 程序缺失。"})
        else:
            expected = root / "app"
            if state.install_path is None or state.install_path.resolve() != expected.resolve():
                raise ApiError(409, "BUNDLE_STATE_CONFLICT", "Bundle 安装位置与状态记录不一致。")
            observation = path.parent / "native-load.json"
            loaded = json.loads(observation.read_text(encoding="utf-8")) if observation.is_file() else {}
            try:
                native_alive = psutil.Process(loaded["pid"]).create_time() == loaded["create_time"]
            except (KeyError, psutil.Error):
                native_alive = False
            if loaded.get("commit") != lock.get("commit") or not loaded.get("ready") or not native_alive:
                restart_required = True
                state = state.model_copy(update={"availability": "not_ready", "reason": loaded.get("reason") or "Bundle 已安装，等待工作台重启加载节点。"})
                restart_path = path.parent / 'bundle-restart.json'
                if restart_path.is_file():
                    from astrophotoflow.core.workbench import restart_result
                    restart_id = UUID(json.loads(restart_path.read_text(encoding='utf-8'))['operation_id'])
                    result = restart_result(settings.workspace / 'config.toml', restart_id)
                    if result is not None and result.state in {'failed', 'unknown', 'rejected'}:
                        state = state.model_copy(update={'reason': 'Bundle 已安装，但重启未完成：' + (result.detail or '、'.join(result.blockers)) + '；请在工作台设置中重启。'})
            elif state.operation_state not in {"unknown", "running"}:
                state = state.model_copy(update={"availability": "ready", "reason": None})
    token = hashlib.sha256(json.dumps({"release": release, "state": state.model_dump(mode="json")}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return SoftwarePackage(package_id=package_id, name=manifest.name,
        available_versions=[release["manifest"]["software_version"]], package_token=token,
        bundle_version=lock.get("bundle_version"), bundle_commit=lock.get("commit"), restart_required=restart_required,
        migration_required=state.installed_version is not None and not root.is_dir(), **state.model_dump())


def list_packages(settings: Settings):
    return [get_package(settings, key) for key in bundles.catalog()]


def get_package_source(package_id: str, version: str):
    release = bundles.release(package_id)
    if version != release["manifest"]["software_version"]:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "未找到发布版本。")
    return release["repository"] + " @ " + release["tag"] + " (" + (release["commit"] or "unreleased") + ")"


def get_bundled_definitions(settings, package_id, version):
    release = bundles.release(package_id)
    if version != release["manifest"]["software_version"]:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "未找到发布版本。")
    return release["nodes"]


def get_operation(settings, package_id, version, operation_id):
    manifest, _, _ = bundles.metadata(settings.workspace, package_id)
    if version != manifest.software_version:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "未找到软件版本。")
    package = get_package(settings, package_id)
    return bundles.operation(settings.workspace, package_id, operation_id, package.availability == "ready", package.reason)


def get_bundle_metadata(settings, package_id):
    return bundles.metadata(settings.workspace, package_id)


def set_package_node_definition_ids(settings, package_id, definition_ids):
    state = _state(get_package(settings, package_id))
    _write_package_state(settings, package_id, state.model_copy(update={"node_definition_ids": definition_ids}))


async def install_package(settings, package_id, version, expected_package_token):
    release = bundles.release(package_id)
    package = get_package(settings, package_id)
    if version != release["manifest"]["software_version"] or package.package_token != expected_package_token:
        raise ApiError(409, "SOFTWARE_CONTENT_CONFLICT", "软件状态或发布版本发生变化。")
    if os.name != "nt":
        raise ApiError(503, "SOFTWARE_NOT_READY", "当前 Bundle 只支持 Windows。")
    if get_usage(package_id) or get_preview_usage(package_id):
        raise ApiError(409, "SOFTWARE_BUSY", "软件仍在运行。")
    directory = settings.workspace / "software" / package_id
    directory.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".bundle-install-", dir=directory))
    state = _state(package)
    _write_package_state(settings, package_id, state.model_copy(update={"operation": "install", "operation_state": "running", "phase": "cloning", "last_error": None}))
    activated = False
    old_lock = (directory / 'bundle-lock.json').read_bytes() if (directory / 'bundle-lock.json').is_file() else None
    old_load = (directory / 'native-load.json').read_bytes() if (directory / 'native-load.json').is_file() else None
    try:
        manifest, commit = await asyncio.to_thread(bundles.checkout, package_id, stage / "bundle", tool_root=settings.workspace / "software/.tools")
        destination = directory / "bundle"
        previous = directory / "previous-bundle"
        if previous.exists():
            raise ApiError(409, "BUNDLE_STATE_CONFLICT", "上次版本仍待处理，未覆盖现有程序。")
        if destination.exists():
            destination.rename(previous)
        try:
            (stage / "bundle").rename(destination)
        except OSError:
            if previous.exists():
                previous.rename(destination)
            raise
        activated = True
        lock = {"repository": release["repository"], "tag": release["tag"], "commit": commit, "bundle_version": manifest.bundle_version}
        (directory / "bundle-lock.json").write_text(json.dumps(lock, indent=2), encoding="utf-8")
        (directory / "native-load.json").unlink(missing_ok=True)
        _write_package_state(settings, package_id, state.model_copy(update={
            "installed_version": manifest.software_version, "install_path": destination / "app",
            "availability": "ready", "reason": None, "operation": "install", "operation_state": "completed", "phase": None, "last_error": None}))
        return get_package(settings, package_id)
    except (ApiError, OSError, ValueError, httpx.HTTPError, subprocess.SubprocessError) as exc:
        if activated:
            (directory / 'bundle').rename(stage / 'failed-bundle')
            if (directory / 'previous-bundle').exists():
                (directory / 'previous-bundle').rename(directory / 'bundle')
            for name, content in [('bundle-lock.json', old_lock), ('native-load.json', old_load)]:
                if content is None:
                    (directory / name).unlink(missing_ok=True)
                else:
                    (directory / name).write_bytes(content)
        _write_package_state(settings, package_id, state.model_copy(update={
            "availability": state.availability,
            "operation": "install", "operation_state": "failed", "phase": None,
            "last_error": ErrorDetail(code="INSTALL_FAILED", message=str(exc), fields=[])}))
        raise ApiError(503, "SOFTWARE_NOT_READY", f"Bundle 安装失败：{exc}") from exc
    finally:
        bundles.remove_checkout(stage, directory)


async def uninstall_package(settings, package_id, expected_package_token):
    package = get_package(settings, package_id)
    if package.package_token != expected_package_token:
        raise ApiError(409, "SOFTWARE_CONTENT_CONFLICT", "软件状态变化，请重新确认。")
    if get_usage(package_id) or get_preview_usage(package_id):
        raise ApiError(409, "SOFTWARE_BUSY", "软件仍在运行或预览。")
    directory = settings.workspace.resolve() / "software" / package_id
    previous = _state(package)
    _write_package_state(settings, package_id, previous.model_copy(update={"operation": "uninstall", "operation_state": "running", "phase": "removing"}))
    try:
        for name in ("bundle", "app", "previous-bundle"):
            target = directory / name
            if target.exists():
                await asyncio.to_thread(bundles.remove_checkout, target, directory)
    except (OSError, ValueError) as exc:
        _write_package_state(settings, package_id, previous.model_copy(update={
            "operation": "uninstall", "operation_state": "failed", "phase": None,
            "availability": "unknown", "reason": "卸载未完整结束。",
            "last_error": ErrorDetail(code="UNINSTALL_FAILED", message=str(exc), fields=[])}))
        raise ApiError(503, "SOFTWARE_NOT_READY", f"Bundle 卸载失败：{exc}") from exc
    for name in ("bundle-lock.json", "native-load.json"):
        (directory / name).unlink(missing_ok=True)
    _write_package_state(settings, package_id, _state(package).model_copy(update={
        "installed_version": None, "install_path": None, "availability": "not_installed", "reason": "尚未安装 Bundle。",
        "operation": "uninstall", "operation_state": "completed", "phase": None, "last_error": None}))
    return get_package(settings, package_id)


def prepare_package(settings, package_id):
    return SoftwarePreparation(package=get_package(settings, package_id), user_action=None, ui_kind=None, ui_target=None)


def _command_rows(command_bytes, assessment_bytes, expected_hash=None):
    commands = json.loads(command_bytes)
    assessments = json.loads(assessment_bytes)
    if assessments["package_id"] != "siril" or assessments["version"] != "1.4.4":
        raise ValueError("Siril command assessments are not bound to the fixed package version.")
    actual_hash = hashlib.sha256(command_bytes).hexdigest()
    if assessments["source_commands_file_sha256"].casefold() != actual_hash or expected_hash is not None and actual_hash != expected_hash.casefold():
        raise ValueError("Siril command assessments do not match the official command catalog.")
    assessment_rows = assessments["commands"]
    assessment_by_command = {item["command"]: item["assessment"] for item in assessment_rows}
    command_names = {item["command"] for item in commands}
    if len(assessment_by_command) != len(assessment_rows) or set(assessment_by_command) != command_names:
        raise ValueError("Siril command assessment entries must match the official command catalog exactly.")
    return [
        SirilCommand.model_validate({**item, "assessment": assessment_by_command[item["command"]]})
        for item in commands
    ]


def list_siril_commands() -> list[SirilCommand]:
    manifest = _manifest()
    vendor = files('astrophotoflow').joinpath('vendor')
    return _command_rows(vendor.joinpath(manifest['commands_file']).read_bytes(),
                         vendor.joinpath(manifest['command_assessments_file']).read_bytes(), manifest['commands_file_sha256'])


def get_command_catalog(package_id: str, version: str, settings=None) -> list[SirilCommand]:
    if package_id != "siril" or version != "1.4.4":
        raise ApiError(404, "RESOURCE_NOT_FOUND", "未找到请求的软件命令目录。")
    if settings is not None:
        root = settings.workspace / 'software' / package_id / 'bundle'
        if root.is_dir():
            manifest, _, _ = bundles.metadata(settings.workspace, package_id)
            if manifest.commands is None or manifest.assessments is None:
                raise ApiError(404, 'RESOURCE_NOT_FOUND', '已安装 Bundle 没有提供命令参考目录。')
            return _command_rows(bundles.contained(root, manifest.commands).read_bytes(),
                                 bundles.contained(root, manifest.assessments).read_bytes())
    release = bundles.release(package_id)
    manifest = release['manifest']
    references = release.get('reference_files')
    if references is not None:
        return _command_rows(references[manifest['commands']].encode('utf-8'), references[manifest['assessments']].encode('utf-8'))
    return list_siril_commands()


def get_usage(package_id: str) -> list[SoftwareUse]:
    for call_id, call in list(_CALLS.items()):
        if call.observation.runtime_ref is not None and (call.process is None or call.process.returncode is not None):
            active = _runtime_active(call.observation.runtime_ref)
            call.observation = call.observation.model_copy(update={"active": active})
            if active is False:
                _CALLS.pop(call_id, None)
    return [SoftwareUse(
        call_id=call.invocation.call_id, run_id=call.invocation.run_id,
        node_execution_id=call.invocation.node_execution_id,
        state="unknown" if call.observation.active is None or call.observation.state == 'unknown' else "running",
    ) for call in _CALLS.values() if call.invocation.package_id == package_id
        and call.observation.active is not False]


def get_preview_usage(package_id: str) -> list[UUID]:
    for key, (_, process) in list(_LIVE_PREVIEWS.items()):
        if process is not None and process.returncode is not None:
            _LIVE_PREVIEWS.pop(key, None)
    return [key for key, (package, _) in _LIVE_PREVIEWS.items() if package == package_id]


async def _stop_preview(process):
    if process.returncode is None:
        try:
            process.terminate()
        except ProcessLookupError:
            pass
    await asyncio.shield(process.wait())


async def preview_operation(settings: Settings, source: Path, directory: Path, parameters, *, package_id: str, operation_id: str, prepare_sample: bool = False) -> Path:
    package = get_package(settings, package_id)
    if package.availability != "ready":
        raise ApiError(503, "SOFTWARE_NOT_READY", package.reason or "请先在软件包页面安装 Siril。")
    lock = _PACKAGE_LOCKS.get(package_id)
    if lock is not None and lock.locked():
        raise ApiError(409, "SOFTWARE_BUSY", "Siril 正在维护。")
    root = (settings.data_dir / "previews").resolve()
    if not directory.resolve().is_relative_to(root) or (not prepare_sample and not source.resolve().is_relative_to(root)):
        raise ApiError(422, "INVALID_REFERENCE", "实时预览仅接受平台生成的显示样本。")
    job_id = UUID(directory.name)
    _LIVE_PREVIEWS[job_id] = (package_id, None)
    process = None
    try:
        directory.mkdir(parents=True, exist_ok=False)
        plan = bundles.adapter_plan(settings.workspace, package_id, operation_id, {'image': [source]}, parameters,
                                    directory, preview=True, prepare_sample=prepare_sample)
        target = plan.outputs['image'].files[0].path if isinstance(plan, NamedProcessPlan) else plan.outputs[0]
        environment = None
        if isinstance(plan, NamedProcessPlan):
            plan.temporary_directory.mkdir(parents=True, exist_ok=True)
            environment = {**os.environ, **plan.environment, **{name: str(plan.temporary_directory) for name in ('TEMP', 'TMP', 'TMPDIR')}}
            if plan.thread_limit is not None:
                environment.update(OPENBLAS_NUM_THREADS=str(plan.thread_limit), OMP_NUM_THREADS=str(plan.thread_limit))
        source_stamp = source.stat()
        log = directory / "preview.log"
        with log.open("wb") as stream:
            spawn = asyncio.create_task(asyncio.create_subprocess_exec(
                str(bundles.contained(settings.workspace / "software" / package_id / "bundle", bundles.metadata(settings.workspace, package_id)[0].executable)), *plan.arguments, cwd=directory,
                stdout=stream, stderr=asyncio.subprocess.STDOUT, env=environment,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            ))
            try:
                process = await asyncio.shield(spawn)
            except asyncio.CancelledError:
                process = await asyncio.shield(spawn)
                await _stop_preview(process)
                raise
            _LIVE_PREVIEWS[job_id] = (package_id, process)
            code = await process.wait()
        if code != 0 or not target.is_file():
            detail = log.read_text(encoding="utf-8", errors="replace")[-2000:]
            raise ApiError(422, "SIRIL_PREVIEW_FAILED", "Siril 实时预览未完成：" + detail)
        if prepare_sample:
            after = source.stat()
            if (source_stamp.st_size, source_stamp.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ApiError(409, "SOURCE_CHANGED", "准备预览时原件发生变化。")
            plan.linear_sample.replace(directory.parent / "linear.fit")
        return target
    except asyncio.CancelledError:
        if process is not None:
            await _stop_preview(process)
        raise
    finally:
        if process is None or process.returncode is not None:
            _LIVE_PREVIEWS.pop(job_id, None)


def validate_parameters(settings, package_id, operation_id, values):
    manifest, _, _ = bundles.metadata(settings.workspace, package_id)
    operation = get_operation(settings, package_id, manifest.software_version, operation_id)
    if set(values) != {item.name for item in operation.parameters}:
        raise ApiError(422, "VALIDATION_ERROR", "参数与 Bundle 操作定义不一致。")
    for parameter in operation.parameters:
        try:
            ParameterDefinition.model_validate({**parameter.model_dump(), "default": values[parameter.name]})
        except ValueError as exc:
            raise ApiError(422, "VALIDATION_ERROR", f"参数无效：{parameter.name}") from exc
    return operation


def _validate_invocation(settings: Settings, invocation: SoftwareInvocation):
    if any(use.state == "unknown" for use in get_usage(invocation.package_id)):
        raise ApiError(409, "SOFTWARE_BUSY", "软件包仍有无法确认停止的调用。")
    operation = get_operation(settings, invocation.package_id, invocation.version, invocation.operation_id)
    if not operation.ready:
        raise ApiError(503, "SOFTWARE_NOT_READY", operation.reason or "Siril 尚未就绪。")
    if invocation.operation_content_token != operation.content_token:
        raise ApiError(409, "SOFTWARE_CONTENT_CONFLICT", "软件操作定义已变化，请重新提交。")
    package = get_package(settings, invocation.package_id)
    manifest, _, _ = bundles.metadata(settings.workspace, invocation.package_id)
    if invocation.bundle_commit != package.bundle_commit and (manifest.host_api == 2 or invocation.bundle_commit is not None):
        raise ApiError(409, 'SOFTWARE_CONTENT_CONFLICT', '调用受理后 Bundle 实现已变化，请查询本次状态，不得采用新版替换在途实现。')
    if set(invocation.parameters) != {item.name for item in operation.parameters}:
        raise ApiError(422, "VALIDATION_ERROR", "Siril 参数与准确操作定义不匹配。")
    for parameter in operation.parameters:
        try:
            ParameterDefinition.model_validate({**parameter.model_dump(), "default": invocation.parameters[parameter.name]})
        except ValueError as exc:
            raise ApiError(422, "VALIDATION_ERROR", f"Siril 参数无效：{parameter.name}") from exc
    definitions = {item.name: item for item in operation.inputs}
    required = {name for name, item in definitions.items() if item.required}
    if not set(invocation.inputs).issubset(definitions) or not required.issubset(invocation.inputs):
        raise ApiError(422, "INVALID_REFERENCE", "具名输入与软件操作定义不匹配。")
    if not set(invocation.supporting_inputs).issubset(invocation.inputs):
        raise ApiError(422, "INVALID_REFERENCE", "序列附属文件没有对应的输入。")
    root = settings.workspace.resolve() / "runs" / str(invocation.run_id) / "work"
    if root.resolve() != root:
        raise ApiError(422, "INVALID_WORK_DIRECTORY", "运行目录指向了工作区以外的位置。")
    work = invocation.work_directory.resolve()
    if work != root and not work.is_relative_to(root):
        raise ApiError(422, "INVALID_WORK_DIRECTORY", "软件只能写入本次运行的工作目录。")
    for name, items in invocation.inputs.items():
        definition = definitions[name]
        if not items or (definition.cardinality == "one" and len(items) != 1):
            raise ApiError(422, "INVALID_REFERENCE", f"输入成员数量不符合操作定义：{name}")
        for item in items:
            if item.format not in definition.formats:
                raise ApiError(422, "UNSUPPORTED_SELECTION", f"输入格式不符合操作定义：{name}")
            metadata = item.scientific_metadata or {}
            if definition.colour_layout is not None and metadata.get('colour_layout') not in (None, definition.colour_layout):
                raise ApiError(422, 'UNSUPPORTED_SELECTION', f'输入颜色布局与操作要求不一致：{name}。')
            default_hdu = definition.data_kind != 'file' and item.selection.kind == 'fits_hdu' and item.selection.hdu_index == 0 and metadata.get('selected_hdu') == 0
            if item.selection.kind != "whole_file" and not definition.supports_hdu and not default_hdu:
                raise ApiError(422, "UNSUPPORTED_SELECTION", f"操作不支持指定 HDU：{name}")
            if definition.data_kind == 'image' and item.selection.kind == 'whole_file' and metadata.get('frame_count', 1) is not None and metadata.get('frame_count', 1) > 1:
                raise ApiError(422, 'UNSUPPORTED_SELECTION', f'该单图输入不能静默读取序列容器的首帧：{name}；请使用适用的序列操作或明确选择主HDU。')
            if manifest.host_api == 2 and definition.data_kind != 'file' and item.format == 'fits' and 'hdu_count' in metadata and (metadata.get('selected_hdu') is None or metadata.get('frame_count') is None and not default_hdu):
                raise ApiError(422, 'UNSUPPORTED_SELECTION', f'该输入没有已确认的二维灰度或RGB图像布局：{name}。')
            whole_container = item.selection.kind == 'whole_file' and (
                definition.data_kind in {'sequence', 'file'} or
                any(file.read_path.suffix.lower() == '.seq' for file in invocation.supporting_inputs.get(name, [])) or
                item.read_path.name.lower().endswith(('.fit.fz', '.fits.fz', '.fts.fz')) and metadata.get('frame_count') == 1)
            if metadata.get("selected_hdu") not in (None, 0) and not definition.supports_hdu and not whole_container:
                raise ApiError(422, "UNSUPPORTED_SELECTION", f"操作不支持扩展 HDU：{name}")
    for item in [item for group in [*invocation.inputs.values(), *invocation.supporting_inputs.values()] for item in group]:
        stat_result = item.read_path.stat()
        if (stat_result.st_size, stat_result.st_mtime_ns) != (item.byte_size, item.mtime_ns):
            raise ApiError(409, "SOURCE_CHANGED", "科学输入在准入后发生变化。")
        if item.read_path.resolve().is_relative_to(work):
            raise ApiError(422, "INVALID_REFERENCE", "科学输入不能位于即将创建的调用输出目录内。")
    return package, work, operation


def _capture_descendants(call):
    runtime = call.observation.runtime_ref
    if call.process is None or runtime is None or call.process.returncode is not None:
        return False
    try:
        parent = psutil.Process(call.process.pid)
        if parent.create_time() != runtime['create_time']:
            return False
        for child in parent.children(recursive=True):
            call.descendants[child.pid] = child.create_time()
        call.inspection_unknown = False
    except psutil.NoSuchProcess:
        pass
    except psutil.AccessDenied:
        call.inspection_unknown = True
    children = [{'pid': pid, 'create_time': created} for pid, created in sorted(call.descendants.items())]
    updated = {**runtime, 'children': children, 'children_unknown': call.inspection_unknown}
    changed = updated != runtime
    call.observation = call.observation.model_copy(update={'runtime_ref': updated})
    return changed


async def _watch_process(call, task, log, reader, observe):
    decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
    pending = ''
    with log.open('rb') as stream:
        while True:
            await asyncio.wait({task}, timeout=0.25)
            changed = _capture_descendants(call)
            pending += decoder.decode(stream.read())
            end = pending.rfind('\n')
            if reader is not None and end >= 0:
                progress = reader(pending[:end + 1])
                if progress.phase is not None or progress.progress is not None:
                    phase = progress.phase if progress.phase is not None else call.observation.phase
                    changed = changed or (phase, progress.progress) != (call.observation.phase, call.observation.progress)
                    call.observation = call.observation.model_copy(update={'phase': phase, 'progress': progress.progress})
                pending = pending[end + 1:]
            elif reader is None:
                pending = ''
            if changed:
                call.observation = call.observation.model_copy(update={'observed_at': datetime.now(timezone.utc)})
                try:
                    await observe(call.observation)
                except Exception as exc:
                    raise _ObservationFailed(str(exc)) from exc
            if task.done():
                return task.result()


async def _stop_call(call):
    _capture_descendants(call)
    children = []
    for pid, created in call.descendants.items():
        try:
            child = psutil.Process(pid)
            if child.create_time() == created:
                child.terminate()
                children.append(child)
        except psutil.NoSuchProcess:
            pass
        except psutil.AccessDenied:
            call.inspection_unknown = True
    if call.process is not None and call.process.returncode is None:
        try:
            call.process.terminate()
        except ProcessLookupError:
            pass
    waits = [asyncio.to_thread(psutil.wait_procs, children, timeout=5)] if children else []
    if call.process is not None:
        waits.append(call.process.wait())
    try:
        await asyncio.wait_for(asyncio.gather(*waits), timeout=5)
    except TimeoutError:
        return None
    if call.inspection_unknown:
        return None
    return _runtime_active(call.observation.runtime_ref) if call.observation.runtime_ref else None


async def invoke_operation(settings: Settings, invocation: SoftwareInvocation,
                           observe: Callable[[SoftwareObservation], Awaitable[None]]) -> SoftwareResult:
    package, work, operation = _validate_invocation(settings, invocation)
    lock = _PACKAGE_LOCKS.setdefault(invocation.package_id, asyncio.Lock())
    if lock.locked():
        raise ApiError(409, "SOFTWARE_BUSY", "软件包正在维护。")
    if invocation.call_id in _CALLS:
        raise ApiError(409, "SOFTWARE_BUSY", "该调用已受理，不能重复启动。")
    started = datetime.now(timezone.utc)
    log = work / "siril.log"
    observation = SoftwareObservation(
        run_id=invocation.run_id, node_execution_id=invocation.node_execution_id, call_id=invocation.call_id,
        observed_at=started, active=True, runtime_ref=None, state="starting", phase="starting", log_path=log,
    )
    call = _Call(invocation, observation)
    _CALLS[invocation.call_id] = call
    outputs = {item.name: [] for item in operation.outputs}
    supporting_outputs = {}
    code = None
    error = None
    state = "failed"
    task = None
    try:
        await observe(observation)
        work.mkdir(parents=True, exist_ok=False)
        plan = bundles.adapter_plan(settings.workspace, invocation.package_id, invocation.operation_id,
                                    {name: [item.read_path for item in items] for name, items in invocation.inputs.items()},
                                    invocation.parameters, work,
                                    supporting_sources={name: [item.read_path for item in items] for name, items in invocation.supporting_inputs.items()},
                                    source_groups={name: [[item.read_path for item in items if item.reference_index == index]
                                                        for index in sorted({item.reference_index for item in items})]
                                                   for name, items in invocation.inputs.items()},
                                    supporting_groups={name: [[item.read_path for item in invocation.supporting_inputs.get(name, []) if item.reference_index == index]
                                                             for index in sorted({item.reference_index for item in items})]
                                                       for name, items in invocation.inputs.items()},
                                    source_metadata={name: [item.model_dump(mode='json', include={'reference_index', 'selection', 'scientific_metadata'}) for item in items]
                                                     for name, items in invocation.inputs.items()})
        environment = None
        if isinstance(plan, NamedProcessPlan):
            if set(plan.outputs) != set(outputs):
                raise ValueError("Bundle 输出计划与操作端口不匹配。")
            plan.temporary_directory.mkdir(parents=True, exist_ok=True)
            environment = {**os.environ, **plan.environment, **{name: str(plan.temporary_directory) for name in ('TEMP', 'TMP', 'TMPDIR')}}
            if plan.thread_limit is not None:
                environment.update(OPENBLAS_NUM_THREADS=str(plan.thread_limit), OMP_NUM_THREADS=str(plan.thread_limit))
        executable = bundles.contained(settings.workspace / "software" / invocation.package_id / "bundle",
                                       bundles.metadata(settings.workspace, invocation.package_id)[0].executable)
        if call.cancelled:
            state = "cancelled"
        else:
            with log.open("wb") as stream:
                call.process = await asyncio.create_subprocess_exec(
                    str(executable), *plan.arguments,
                    cwd=work, stdout=stream, stderr=asyncio.subprocess.STDOUT, env=environment,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                try:
                    process = psutil.Process(call.process.pid)
                    runtime_ref = {"pid": process.pid, "create_time": process.create_time(),
                                   "executable": str(executable)}
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    runtime_ref = None
                call.observation = observation.model_copy(update={
                    "observed_at": datetime.now(timezone.utc), "state": "running", "phase": "processing",
                    "runtime_ref": runtime_ref,
                })
                task = asyncio.create_task(call.process.wait())
                try:
                    await observe(call.observation)
                except Exception as exc:
                    error = ErrorDetail(code="OBSERVATION_FAILED", message=f"处理已启动，但状态记录失败：{exc}", fields=[])
                if call.cancelled and call.process.returncode is None:
                    await _stop_call(call)
                code = await _watch_process(call, task, log, bundles.progress_reader(settings.workspace, invocation.package_id), observe)
            if call.cancelled:
                state = "cancelled"
            elif code != 0:
                if isinstance(plan, ProcessPlan):
                    collected = bundles.collect_result(settings.workspace, invocation.package_id, invocation.operation_id, plan, work, log)
                    outputs = {name: [ProducedFile.model_validate(file.model_dump()) for file in files] for name, files in collected.outputs.items()}
                detail = bundles.failure_reason(settings.workspace, invocation.package_id, log)
                error = ErrorDetail(code="SOFTWARE_EXECUTION_FAILED", message=f'程序退出代码 {code}：{detail}', fields=[])
            elif error is None:
                collected = await asyncio.to_thread(bundles.collect_result, settings.workspace, invocation.package_id,
                                                    invocation.operation_id, plan, work, log)
                for definition in operation.outputs:
                    files = collected.outputs[definition.name]
                    if (definition.required and not files) or (definition.cardinality == 'one' and len(files) > 1):
                        raise ValueError('Bundle 输出成员数量不符合定义：' + definition.name)
                    if any(file.format not in definition.formats for file in files):
                        raise ValueError('Bundle 输出格式不符合定义：' + definition.name)
                if isinstance(plan, ProcessPlan) and len(collected.outputs['image']) != len(plan.outputs):
                    raise ValueError('Bundle 没有产生完整输出。')
                outputs = {name: [ProducedFile.model_validate(file.model_dump()) for file in files] for name, files in collected.outputs.items()}
                supporting_outputs = {name: [ProducedFile.model_validate(file.model_dump()) for file in files] for name, files in collected.supporting_outputs.items()}
                state = "completed"
            elif error.code == 'OBSERVATION_FAILED':
                state = 'unknown'
    except asyncio.CancelledError:
        call.cancelled = True
        await asyncio.shield(_stop_call(call))
        state = "cancelled"
        code = call.process.returncode if call.process else None
    except _ObservationFailed as exc:
        if call.process is not None and call.process.returncode is None:
            code = await asyncio.shield(call.process.wait())
        state = 'unknown'
        error = ErrorDetail(code='OBSERVATION_FAILED', message='实际调用状态记录失败，请先查询已有结果和日志：' + str(exc), fields=[])
    except Exception as exc:
        if call.process is not None and call.process.returncode is None:
            code = await asyncio.shield(call.process.wait())
        error = ErrorDetail(code="SOFTWARE_EXECUTION_FAILED", message=str(exc), fields=[])
    finally:
        active = _runtime_active(call.observation.runtime_ref) if call.observation.runtime_ref else call.process is not None and call.process.returncode is None
        if active is not False:
            state = 'unknown'
        call.observation = call.observation.model_copy(update={
            "observed_at": datetime.now(timezone.utc), "active": active,
            "state": "unknown" if active else state, "phase": None, "exit_code": code, "error": error,
        })
        if active is False:
            _CALLS.pop(invocation.call_id, None)
    try:
        await observe(call.observation)
    except Exception as exc:
        state = "unknown"
        error = ErrorDetail(code="OBSERVATION_FAILED", message=f"处理结果记录失败：{exc}", fields=[])
    return SoftwareResult(
        call_id=invocation.call_id, state=state, started_at=started, ended_at=datetime.now(timezone.utc),
        exit_code=code, outputs=outputs, supporting_outputs=supporting_outputs, log_path=log, error=error,
    )


def _runtime_active(runtime) -> bool | None:
    unknown = runtime.get('children_unknown', False)
    try:
        process = psutil.Process(runtime["pid"])
        if process.create_time() == runtime["create_time"] and \
            Path(process.exe()).resolve() == Path(runtime["executable"]).resolve() and process.is_running():
            return True
    except psutil.NoSuchProcess:
        pass
    except psutil.AccessDenied:
        unknown = True
    for child in runtime.get('children', []):
        try:
            process = psutil.Process(child['pid'])
            if process.create_time() == child['create_time'] and process.is_running():
                return True
        except psutil.NoSuchProcess:
            pass
        except psutil.AccessDenied:
            unknown = True
    return None if unknown else False


async def inspect_operation(settings: Settings, invocation: SoftwareInvocation,
                            previous: SoftwareObservation | None) -> SoftwareObservation:
    call = _CALLS.get(invocation.call_id)
    if call is not None:
        if call.observation.runtime_ref is not None:
            _capture_descendants(call)
            call.observation = call.observation.model_copy(update={"active": _runtime_active(call.observation.runtime_ref)})
        return call.observation
    if previous is None or previous.active is False:
        return previous or SoftwareObservation(
            run_id=invocation.run_id, node_execution_id=invocation.node_execution_id, call_id=invocation.call_id,
            observed_at=datetime.now(timezone.utc), active=None, runtime_ref=None, state="unknown",
        )
    runtime = previous.runtime_ref
    active = None
    if runtime is not None:
        active = _runtime_active(runtime)
    observation = previous.model_copy(update={"observed_at": datetime.now(timezone.utc), "active": active, "state": "unknown", "phase": None})
    if active is not False:
        _CALLS[invocation.call_id] = _Call(invocation, observation)
    return observation


async def cancel_operation(call_id: UUID) -> SoftwareCancelResult:
    call = _CALLS.get(call_id)
    if call is None:
        return SoftwareCancelResult(call_id=call_id, request_state="unknown", stop_state="unknown",
                                    observed_at=datetime.now(timezone.utc), reason="当前没有可核对的调用句柄，不能据此断言已经停止。")
    if call.process is None and call.observation.state == "unknown":
        return SoftwareCancelResult(call_id=call_id, request_state="unknown", stop_state="unknown",
                                    observed_at=datetime.now(timezone.utc), reason="原调用句柄已丢失，不能代替实际停止证据。")
    call.cancelled = True
    process = call.process
    if process is None:
        if call.observation.runtime_ref is not None:
            return SoftwareCancelResult(call_id=call_id, request_state="unknown", stop_state="unknown",
                                        observed_at=datetime.now(timezone.utc), reason="服务重启后不再持有原调用句柄，需先核对实际进程。")
        return SoftwareCancelResult(call_id=call_id, request_state="sent", stop_state="running",
                                    observed_at=datetime.now(timezone.utc), reason="已请求在实际启动前停止。")
    active = await _stop_call(call)
    return SoftwareCancelResult(call_id=call_id, request_state="sent",
                                stop_state='stopped' if active is False else 'running' if active is True else 'unknown',
                                observed_at=datetime.now(timezone.utc),
                                reason=None if active is False else '停止请求已发送，尚未确认整个调用进程树退出。')
