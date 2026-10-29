import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
import zipfile
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from importlib.resources import files
from pathlib import Path, PurePosixPath
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
from astrophotoflow.core.config import Settings
from astrophotoflow.core.errors import ApiError


_PACKAGE_ID = "siril"
_VERSION = "1.4.4"
_PACKAGE_LOCKS: dict[str, asyncio.Lock] = {}


@dataclass
class _Call:
    invocation: SoftwareInvocation
    observation: SoftwareObservation
    process: asyncio.subprocess.Process | None = None
    cancelled: bool = False


_CALLS: dict[UUID, _Call] = {}
_LIVE_PREVIEWS: dict[UUID, asyncio.subprocess.Process | None] = {}


def _resource(name: str) -> str:
    return files("astrophotoflow").joinpath("vendor", name).read_text(encoding="utf-8-sig")


def _manifest() -> dict[str, Any]:
    return json.loads(_resource("siril-1.4.4-manifest.json"))


def _write_state(workspace: Path, state: SoftwarePackageState) -> None:
    package_dir = workspace / "software" / _PACKAGE_ID
    package_dir.mkdir(parents=True, exist_ok=True)
    state_path = package_dir / "state.json"
    content = json.dumps(state.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=package_dir, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        os.replace(temporary, state_path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _download_and_verify_archive(url: str, stage: Path, app: Path, phase: Callable[[str], None]) -> Path:
    archive_path = stage / "siril-1.4.4-ucrt64_win.zip"
    with httpx.Client(follow_redirects=True, timeout=httpx.Timeout(120)) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            with archive_path.open("xb") as stream:
                for chunk in response.iter_bytes(1024 * 1024):
                    stream.write(chunk)
    root = app.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        members = []
        for member in archive.infolist():
            archive_path_parts = PurePosixPath(member.filename).parts
            if stat.S_ISLNK(member.external_attr >> 16) or ".." in archive_path_parts or PurePosixPath(member.filename).is_absolute():
                raise ValueError("软件归档包含不安全的文件路径。")
            if not archive_path_parts or archive_path_parts[0] != "siril":
                continue
            target = app.joinpath(*archive_path_parts[1:]).resolve()
            if not target.is_relative_to(root):
                raise ValueError("软件归档包含不安全的文件路径。")
            members.append((member, target))
        phase("installing")
        app.mkdir(exist_ok=False)
        for member, target in members:
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target.open("xb") as destination:
                    shutil.copyfileobj(source, destination, length=1024 * 1024)
    phase("verifying")
    executable = app / "bin" / "siril-cli.exe"
    if not executable.is_file():
        raise ValueError("Siril 1.4.4归档未包含预期的命令行程序。")
    result = subprocess.run([str(executable), "--version"], cwd=executable.parent,
                            capture_output=True, text=True, timeout=30, check=False,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    if result.returncode != 0 or result.stdout.strip().casefold() != "siril 1.4.4":
        raise ValueError("下载的Siril程序未报告准确的1.4.4版本。")
    return app


@asynccontextmanager
async def maintain_package(package_id: str):
    if package_id != _PACKAGE_ID:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "未找到请求的软件包。")
    lock = _PACKAGE_LOCKS.setdefault(package_id, asyncio.Lock())
    if lock.locked():
        raise ApiError(409, "SOFTWARE_BUSY", "软件包当前正在维护。")
    if get_usage(package_id) or get_preview_usage(package_id):
        raise ApiError(409, "SOFTWARE_BUSY", "软件包仍有运行或无法确认停止的调用。")
    await lock.acquire()
    try:
        yield
    finally:
        lock.release()


async def install_package(settings: Settings, package_id: str, version: str,
                          expected_package_token: str) -> SoftwarePackage:
    if package_id != _PACKAGE_ID:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "未找到请求的软件包。")
    if version != _VERSION:
        raise ApiError(422, "VALIDATION_ERROR", "只能安装维护清单中的Siril 1.4.4版本。")
    if os.name != "nt":
        raise ApiError(503, "SOFTWARE_NOT_READY", "Siril 1.4.4 UCRT64便携包仅配置了Windows安装流程。")
    package = get_package(settings, package_id)
    if package.package_token != expected_package_token:
        raise ApiError(409, "SOFTWARE_CONTENT_CONFLICT", "软件包状态已变化，请重新读取后请求安装。")
    if package.availability == "ready":
        raise ApiError(409, "SOFTWARE_CONTENT_CONFLICT", "Siril 1.4.4已经就绪。")
    package_dir = settings.workspace / "software" / package_id
    app_path = package_dir / "app"
    if app_path.exists():
        raise ApiError(409, "SOFTWARE_CONTENT_CONFLICT", "平台软件目录已存在但当前状态不能确认，需先检查现状。")
    previous = SoftwarePackageState(
        installed_version=package.installed_version, install_path=package.install_path,
        availability=package.availability, reason=package.reason, operation="install",
        operation_state="running", phase="downloading", progress=None,
        last_error=None, node_definition_ids=package.node_definition_ids,
    )
    _write_state(settings.workspace, previous)
    stage = Path(tempfile.mkdtemp(prefix=".siril-install-", dir=package_dir))

    def phase(value: str):
        _write_state(settings.workspace, previous.model_copy(update={"phase": value,
            "install_path": app_path if app_path.is_dir() else None,
            "availability": "not_ready" if app_path.is_dir() else "not_installed"}))

    try:
        await asyncio.to_thread(_download_and_verify_archive, _manifest()["download_url"], stage, app_path, phase)
        installed = SoftwarePackageState(
            installed_version=_VERSION, install_path=app_path, availability="ready", reason=None,
            operation="install", operation_state="completed", phase=None, progress=None,
            last_error=None, node_definition_ids=package.node_definition_ids,
        )
        _write_state(settings.workspace, installed)
        return get_package(settings, package_id)
    except (OSError, ValueError, httpx.HTTPError, subprocess.SubprocessError) as exc:
        failed = previous.model_copy(update={
            "operation_state": "failed", "phase": None,
            "install_path": app_path if app_path.is_dir() else None,
            "availability": "not_ready" if app_path.is_dir() else "not_installed",
            "reason": "软件安装未完成，可卸载后重新安装。" if app_path.is_dir() else package.reason,
            "last_error": ErrorDetail(code="INSTALL_FAILED", message=str(exc), fields=[]),
        })
        _write_state(settings.workspace, failed)
        raise ApiError(503, "SOFTWARE_NOT_READY", f"Siril 1.4.4安装失败：{exc}") from exc
    finally:
        shutil.rmtree(stage)


def prepare_package(settings: Settings, package_id: str):
    if package_id != _PACKAGE_ID:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "未找到请求的软件包。")
    package = get_package(settings, package_id)
    lock = _PACKAGE_LOCKS.get(package_id)
    if get_usage(package_id) or (lock is not None and lock.locked()):
        raise ApiError(409, "SOFTWARE_BUSY", "软件包正在调用或维护，暂不重新检查准备状态。")
    if package.installed_version is not None and package.install_path is not None:
        try:
            result = subprocess.run([str(package.install_path / "bin" / "siril-cli.exe"), "--version"],
                                    cwd=package.install_path / "bin", capture_output=True, text=True, timeout=30)
            ready = result.returncode == 0 and result.stdout.strip().casefold() == "siril 1.4.4"
            reason = None if ready else "平台 Siril 程序未报告准确的 1.4.4 版本。"
        except (OSError, subprocess.SubprocessError) as exc:
            ready, reason = False, f"无法检查平台 Siril 程序：{exc}"
        state = SoftwarePackageState.model_validate(package.model_dump(exclude={"package_id", "name", "available_versions", "package_token"}))
        _write_state(settings.workspace, state.model_copy(update={"availability": "ready" if ready else "not_ready", "reason": reason}))
    return SoftwarePreparation(package=get_package(settings, package_id), user_action=None, ui_kind=None, ui_target=None)


async def uninstall_package(settings: Settings, package_id: str, expected_package_token: str) -> SoftwarePackage:
    package = get_package(settings, package_id)
    if package.package_token != expected_package_token:
        raise ApiError(409, "SOFTWARE_CONTENT_CONFLICT", "软件包状态已变化，请重新确认卸载。")
    if get_usage(package_id):
        raise ApiError(409, "SOFTWARE_BUSY", "软件包仍有运行或无法确认停止的调用。")
    app = settings.workspace / "software" / package_id / "app"
    expected = settings.workspace.resolve() / "software" / package_id / "app"
    if app.resolve() != expected or app.is_symlink():
        raise ApiError(409, "SOFTWARE_CONTENT_CONFLICT", "平台程序目录指向其他位置，拒绝卸载。")
    previous = SoftwarePackageState.model_validate(package.model_dump(exclude={"package_id", "name", "available_versions", "package_token"}))
    _write_state(settings.workspace, previous.model_copy(update={"operation": "uninstall", "operation_state": "running", "phase": "removing"}))
    try:
        if app.exists():
            await asyncio.to_thread(shutil.rmtree, app)
    except OSError as exc:
        _write_state(settings.workspace, previous.model_copy(update={
            "availability": "unknown", "operation": "uninstall", "operation_state": "failed", "phase": None,
            "reason": "卸载未完整结束，请检查平台程序目录。",
            "last_error": ErrorDetail(code="UNINSTALL_FAILED", message=str(exc), fields=[]),
        }))
        raise ApiError(503, "SOFTWARE_NOT_READY", f"Siril 卸载失败：{exc}") from exc
    _write_state(settings.workspace, previous.model_copy(update={
        "installed_version": None, "install_path": None, "availability": "not_installed",
        "reason": "该软件尚未通过 AstroPhotoFlow 安装。", "operation": "uninstall",
        "operation_state": "completed", "phase": None, "progress": None, "last_error": None,
    }))
    return get_package(settings, package_id)


def get_package_source(package_id: str, version: str) -> str:
    if package_id != _PACKAGE_ID or version != _VERSION:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "未找到请求的软件包来源。")
    return _manifest()["download_url"]


def set_package_node_definition_ids(settings: Settings, package_id: str, definition_ids: list[UUID]) -> None:
    if package_id != _PACKAGE_ID:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "未找到请求的软件包。")
    package = get_package(settings, package_id)
    state = SoftwarePackageState(
        installed_version=package.installed_version, install_path=package.install_path,
        availability=package.availability, reason=package.reason, operation=package.operation,
        operation_state=package.operation_state, phase=package.phase, progress=package.progress,
        last_error=package.last_error, node_definition_ids=definition_ids,
    )
    _write_state(settings.workspace, state)


def list_siril_commands() -> list[SirilCommand]:
    manifest = _manifest()
    commands = json.loads(_resource(manifest["commands_file"]))
    assessments = json.loads(_resource(manifest["command_assessments_file"]))
    if assessments["package_id"] != _PACKAGE_ID or assessments["version"] != _VERSION:
        raise ValueError("Siril command assessments are not bound to the fixed package version.")
    if assessments["source_commands_file_sha256"].casefold() != manifest["commands_file_sha256"].casefold():
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


def get_command_catalog(package_id: str, version: str) -> list[SirilCommand]:
    if package_id != _PACKAGE_ID or version != _VERSION:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "未找到请求的软件命令目录。")
    return list_siril_commands()


def _operation(ready: bool, reason: str | None) -> SoftwareOperation:
    operation = SoftwareOperation.model_validate({
        "package_id": _PACKAGE_ID,
        "version": _VERSION,
        "operation_id": "autostretch",
        "name": "Auto Stretch",
        "description": "Applies Auto Stretch to each static image in fixed order using Siril. Linked mode preserves channel balance. Writes new FITS files; originals remain unchanged.",
        "syntax": "autostretch [-linked] [shadowsclip [targetbg]]",
        "inputs": [{
            "name": "image", "type": "APF_SCIENCE", "formats": ["fits", "xisf", "image", "raw"],
            "cardinality": "many", "required": True, "supports_hdu": False, "supports_slice": False,
        }],
        "outputs": [{
            "name": "image", "type": "APF_SCIENCE", "formats": ["fits"], "cardinality": "many",
        }],
        "parameters": [
            {"name": "linked", "kind": "boolean", "default": False},
            {"name": "shadowsclip", "kind": "float", "default": -2.8},
            {"name": "targetbg", "kind": "float", "default": 0.25, "minimum": 0, "maximum": 1},
        ],
        "scriptable": True,
        "cancel_supported": None,
        "content_token": "",
        "ready": ready,
        "reason": reason,
    })
    token_payload = operation.model_dump(mode="json", exclude={"content_token", "ready", "reason"})
    token = hashlib.sha256(json.dumps(token_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
    return operation.model_copy(update={"content_token": token})


def get_operation(settings: Settings, package_id: str, version: str, operation_id: str) -> SoftwareOperation:
    if package_id != _PACKAGE_ID or version != _VERSION or operation_id != "autostretch":
        raise ApiError(404, "RESOURCE_NOT_FOUND", "未找到请求的软件操作。")
    package = get_package(settings, package_id)
    reason = package.reason if package.availability != "ready" else None
    return _operation(package.availability == "ready", reason)


def get_bundled_definitions(settings: Settings, package_id: str, version: str) -> list[dict[str, JsonValue]]:
    if package_id != _PACKAGE_ID or version != _VERSION:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "未找到请求的软件配套定义。")
    return json.loads(_resource("siril-1.4.4-node-definitions.json"))


def get_package(settings: Settings, package_id: str) -> SoftwarePackage:
    if package_id != _PACKAGE_ID:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "未找到请求的软件包。")
    manifest = _manifest()
    app_path = settings.workspace / "software" / _PACKAGE_ID / "app"
    state_path = settings.workspace / "software" / _PACKAGE_ID / "state.json"
    if state_path.is_file():
        state = SoftwarePackageState.model_validate_json(state_path.read_text(encoding="utf-8"))
        if state.installed_version is not None and state.installed_version not in [_VERSION]:
            raise ValueError(f"Siril 当前状态记录了清单外版本：{state.installed_version}")
        if state.install_path is not None and state.install_path.resolve() != app_path.resolve():
            raise ValueError("Siril 当前状态记录的安装位置与平台固定位置不一致。")
        if state.availability == "not_installed" and app_path.is_dir():
            state = state.model_copy(update={"availability": "unknown", "reason": "安装目录存在但当前状态记录为未安装，无法确认软件状态。"})
        if state.installed_version is not None and state.install_path is None:
            raise ValueError("已安装的软件状态必须记录安装位置。")
        if state.installed_version is not None and not app_path.is_dir():
            state = state.model_copy(update={"availability": "unknown", "reason": "安装位置不存在，无法确认软件已就绪。"})
        elif state.availability == "ready" and not (app_path / "bin" / "siril-cli.exe").is_file():
            state = state.model_copy(update={"availability": "not_ready", "reason": "平台 Siril CLI 程序缺失。"})
        active_lock = _PACKAGE_LOCKS.get(package_id)
        if state.operation_state == "running" and (active_lock is None or not active_lock.locked()):
            state = state.model_copy(update={
                "availability": "unknown", "operation_state": "unknown",
                "reason": "上次服务状态记录为运行中，但当前没有可核对的安装任务。",
            })
    else:
        if app_path.is_dir():
            state = SoftwarePackageState(
                installed_version=None, install_path=app_path, availability="unknown",
                reason="检测到平台软件目录，但尚无可核对的版本状态记录。", operation=None,
                operation_state="unknown", phase=None, progress=None, last_error=None, node_definition_ids=[],
            )
        else:
            state = SoftwarePackageState(
                installed_version=None, install_path=None, availability="not_installed",
                reason="该软件尚未通过 AstroPhotoFlow 安装。", operation=None,
                operation_state="idle", phase=None, progress=None, last_error=None, node_definition_ids=[],
            )
    content = {
        "package_id": _PACKAGE_ID,
        "name": manifest["name"],
        "available_versions": [_VERSION],
        "installed_version": state.installed_version,
        "install_path": str(state.install_path) if state.install_path is not None else None,
        "operation_contents": [_operation(state.availability == "ready", state.reason).model_dump(
            mode="json", exclude={"content_token", "ready", "reason"}
        )],
    }
    package_token = hashlib.sha256(
        json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return SoftwarePackage(
        package_id=_PACKAGE_ID,
        name=manifest["name"],
        available_versions=[_VERSION],
        installed_version=state.installed_version,
        install_path=state.install_path,
        package_token=package_token,
        availability=state.availability,
        reason=state.reason,
        operation=state.operation,
        operation_state=state.operation_state,
        phase=state.phase,
        progress=state.progress,
        last_error=state.last_error,
        node_definition_ids=state.node_definition_ids,
    )


def list_packages(settings: Settings) -> list[SoftwarePackage]:
    return [get_package(settings, _PACKAGE_ID)]


def get_usage(package_id: str) -> list[SoftwareUse]:
    for call_id, call in list(_CALLS.items()):
        if call.process is None and call.observation.runtime_ref is not None:
            active = _runtime_active(call.observation.runtime_ref)
            call.observation = call.observation.model_copy(update={"active": active})
            if active is False:
                _CALLS.pop(call_id, None)
    return [SoftwareUse(
        call_id=call.invocation.call_id, run_id=call.invocation.run_id,
        node_execution_id=call.invocation.node_execution_id,
        state="unknown" if call.observation.active is None else "running",
    ) for call in _CALLS.values() if call.invocation.package_id == package_id
        and call.observation.active is not False]


def get_preview_usage(package_id: str) -> list[UUID]:
    for key, process in list(_LIVE_PREVIEWS.items()):
        if process is not None and process.returncode is not None:
            _LIVE_PREVIEWS.pop(key, None)
    return list(_LIVE_PREVIEWS) if package_id == "siril" else []


async def _stop_preview(process):
    if process.returncode is None:
        try:
            process.terminate()
        except ProcessLookupError:
            pass
    await asyncio.shield(process.wait())


async def preview_autostretch(settings: Settings, source: Path, directory: Path, parameters, *, prepare_sample: bool = False) -> Path:
    package = get_package(settings, "siril")
    if package.availability != "ready":
        raise ApiError(503, "SOFTWARE_NOT_READY", package.reason or "请先在软件包页面安装 Siril。")
    lock = _PACKAGE_LOCKS.get("siril")
    if lock is not None and lock.locked():
        raise ApiError(409, "SOFTWARE_BUSY", "Siril 正在维护。")
    root = (settings.data_dir / "previews").resolve()
    if not directory.resolve().is_relative_to(root) or (not prepare_sample and not source.resolve().is_relative_to(root)):
        raise ApiError(422, "INVALID_REFERENCE", "实时预览仅接受平台生成的显示样本。")
    job_id = UUID(directory.name)
    _LIVE_PREVIEWS[job_id] = None
    process = None
    try:
        directory.mkdir(parents=True, exist_ok=False)
        # An explicit -i requires an existing INI; omitted keys use Siril defaults.
        (directory / "siril.ini").write_text("[core]\n", encoding="utf-8")
        target = directory / "result.fit"
        command = "autostretch " + ("-linked " if parameters.linked else "") + f"{parameters.shadowsclip:.17g} {parameters.targetbg:.17g}"
        script = directory / "preview.ssf"
        source_stamp = source.stat()
        commands = ["requires 1.4.4", "setext fit", "set32bits", "load " + _siril_path(source)]
        if prepare_sample:
            commands.extend(["resample -maxdim=1024 -interp=area", "save " + _siril_path(directory / "linear.fit")])
        commands.extend([command, "save " + _siril_path(target), "close"])
        script.write_text("\n".join(commands) + "\n", encoding="utf-8")
        log = directory / "preview.log"
        with log.open("wb") as stream:
            spawn = asyncio.create_task(asyncio.create_subprocess_exec(
                str(package.install_path / "bin/siril-cli.exe"), "-o", "-i", str(directory / "siril.ini"),
                "-d", str(directory), "-s", str(script), cwd=directory,
                stdout=stream, stderr=asyncio.subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            ))
            try:
                process = await asyncio.shield(spawn)
            except asyncio.CancelledError:
                process = await asyncio.shield(spawn)
                await _stop_preview(process)
                raise
            _LIVE_PREVIEWS[job_id] = process
            code = await process.wait()
        if code != 0 or not target.is_file():
            detail = log.read_text(encoding="utf-8", errors="replace")[-2000:]
            raise ApiError(422, "SIRIL_PREVIEW_FAILED", "Siril 实时预览未完成：" + detail)
        if prepare_sample:
            after = source.stat()
            if (source_stamp.st_size, source_stamp.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ApiError(409, "SOURCE_CHANGED", "准备预览时原件发生变化。")
            (directory / "linear.fit").replace(directory.parent / "linear.fit")
        return target
    except asyncio.CancelledError:
        if process is not None:
            await _stop_preview(process)
        raise
    finally:
        if process is None or process.returncode is not None:
            _LIVE_PREVIEWS.pop(job_id, None)


def _validate_invocation(settings: Settings, invocation: SoftwareInvocation):
    if any(use.state == "unknown" for use in get_usage(invocation.package_id)):
        raise ApiError(409, "SOFTWARE_BUSY", "软件包仍有无法确认停止的调用。")
    operation = get_operation(settings, invocation.package_id, invocation.version, invocation.operation_id)
    if not operation.ready:
        raise ApiError(503, "SOFTWARE_NOT_READY", operation.reason or "Siril 尚未就绪。")
    if invocation.operation_content_token != operation.content_token:
        raise ApiError(409, "SOFTWARE_CONTENT_CONFLICT", "软件操作定义已变化，请重新提交。")
    if set(invocation.parameters) != {item.name for item in operation.parameters}:
        raise ApiError(422, "VALIDATION_ERROR", "Siril 参数与准确操作定义不匹配。")
    for parameter in operation.parameters:
        try:
            ParameterDefinition.model_validate({**parameter.model_dump(), "default": invocation.parameters[parameter.name]})
        except ValueError as exc:
            raise ApiError(422, "VALIDATION_ERROR", f"Siril 参数无效：{parameter.name}") from exc
    if set(invocation.inputs) != {"image"} or not invocation.inputs["image"]:
        raise ApiError(422, "INVALID_REFERENCE", "Auto Stretch 需要非空的有序静态图像输入。")
    root = settings.workspace.resolve() / "runs" / str(invocation.run_id) / "work"
    if root.resolve() != root:
        raise ApiError(422, "INVALID_WORK_DIRECTORY", "运行目录指向了工作区以外的位置。")
    work = invocation.work_directory.resolve()
    if work != root and not work.is_relative_to(root):
        raise ApiError(422, "INVALID_WORK_DIRECTORY", "软件只能写入本次运行的工作目录。")
    for item in invocation.inputs["image"]:
        if item.format not in {"fits", "xisf", "image", "raw"} or item.selection.kind != "whole_file":
            raise ApiError(422, "UNSUPPORTED_SELECTION", "Auto Stretch 需要完整静态图像，不支持视频、数组或指定切片。")
        if (item.scientific_metadata or {}).get("selected_hdu") not in (None, 0):
            raise ApiError(422, "UNSUPPORTED_SELECTION", "Auto Stretch 首版尚不支持扩展 HDU 图像。")
        stat_result = item.read_path.stat()
        if (stat_result.st_size, stat_result.st_mtime_ns) != (item.byte_size, item.mtime_ns):
            raise ApiError(409, "SOURCE_CHANGED", "科学输入在准入后发生变化。")
        if item.read_path.resolve().is_relative_to(work):
            raise ApiError(422, "INVALID_REFERENCE", "科学输入不能位于即将创建的调用输出目录内。")
    return get_package(settings, invocation.package_id), work


def _siril_path(path: Path) -> str:
    value = path.resolve().as_posix()
    if any(character in value for character in ('"', '\n', '\r')):
        raise ApiError(422, "UNSUPPORTED_SOURCE_PATH", "Siril 脚本不支持此文件名中的引号或换行。")
    return '"' + value + '"'


async def invoke_operation(settings: Settings, invocation: SoftwareInvocation,
                           observe: Callable[[SoftwareObservation], Awaitable[None]]) -> SoftwareResult:
    package, work = _validate_invocation(settings, invocation)
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
    outputs = []
    code = None
    error = None
    state = "failed"
    task = None
    try:
        await observe(observation)
        work.mkdir(parents=True, exist_ok=False)
        (work / "siril.ini").write_text("[core]\n", encoding="utf-8")
        output_paths = [work / f"autostretch-{index:06d}.fit" for index in range(len(invocation.inputs["image"]))]
        parameters = invocation.parameters
        command = "autostretch " + ("-linked " if parameters["linked"] else "") + \
            f'{parameters["shadowsclip"]:.17g} {parameters["targetbg"]:.17g}'
        commands = ["requires 1.4.4", "setext fit", "set32bits"]
        for item, target in zip(invocation.inputs["image"], output_paths, strict=True):
            commands.extend(["load " + _siril_path(item.read_path), command, "save " + _siril_path(target), "close"])
        script = work / "operation.ssf"
        script.write_text("\n".join(commands) + "\n", encoding="utf-8")
        if call.cancelled:
            state = "cancelled"
        else:
            with log.open("wb") as stream:
                call.process = await asyncio.create_subprocess_exec(
                    str(package.install_path / "bin" / "siril-cli.exe"), "-o", "-i", str(work / "siril.ini"), "-d", str(work), "-s", str(script),
                    cwd=work, stdout=stream, stderr=asyncio.subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                try:
                    process = psutil.Process(call.process.pid)
                    runtime_ref = {"pid": process.pid, "create_time": process.create_time(),
                                   "executable": str(package.install_path / "bin" / "siril-cli.exe")}
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
                    call.process.terminate()
                code = await asyncio.shield(task)
            outputs = [ProducedFile(path=path, format="fits") for path in output_paths if path.is_file() and path.stat().st_size > 0]
            if call.cancelled:
                state = "cancelled"
            elif code != 0 or len(outputs) != len(output_paths):
                error = ErrorDetail(code="SOFTWARE_EXECUTION_FAILED", message="Siril 未完整完成操作，请查看本次调用日志。", fields=[])
            elif error is None:
                state = "completed"
    except asyncio.CancelledError:
        call.cancelled = True
        if call.process is not None and call.process.returncode is None:
            call.process.terminate()
            await asyncio.shield(call.process.wait())
        state = "cancelled"
        code = call.process.returncode if call.process else None
    except (OSError, ValueError, psutil.Error, ApiError) as exc:
        if call.process is not None and call.process.returncode is None:
            code = await asyncio.shield(call.process.wait())
        error = ErrorDetail(code="SOFTWARE_EXECUTION_FAILED", message=str(exc), fields=[])
    finally:
        active = call.process is not None and call.process.returncode is None
        call.observation = call.observation.model_copy(update={
            "observed_at": datetime.now(timezone.utc), "active": active,
            "state": "unknown" if active else state, "phase": None, "exit_code": code, "error": error,
        })
        if not active:
            _CALLS.pop(invocation.call_id, None)
    try:
        await observe(call.observation)
    except Exception as exc:
        state = "unknown"
        error = ErrorDetail(code="OBSERVATION_FAILED", message=f"处理结果记录失败：{exc}", fields=[])
    return SoftwareResult(
        call_id=invocation.call_id, state=state, started_at=started, ended_at=datetime.now(timezone.utc),
        exit_code=code, outputs={"image": outputs}, log_path=log, error=error,
    )


def _runtime_active(runtime) -> bool | None:
    try:
        process = psutil.Process(runtime["pid"])
        return process.create_time() == runtime["create_time"] and \
            Path(process.exe()).resolve() == Path(runtime["executable"]).resolve() and process.is_running()
    except psutil.NoSuchProcess:
        return False
    except psutil.AccessDenied:
        return None


async def inspect_operation(settings: Settings, invocation: SoftwareInvocation,
                            previous: SoftwareObservation | None) -> SoftwareObservation:
    call = _CALLS.get(invocation.call_id)
    if call is not None:
        if call.process is None and call.observation.runtime_ref is not None:
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
    if process.returncode is None:
        try:
            process.terminate()
            await asyncio.wait_for(asyncio.shield(process.wait()), timeout=5)
        except ProcessLookupError:
            pass
        except TimeoutError:
            return SoftwareCancelResult(call_id=call_id, request_state="sent", stop_state="unknown",
                                        observed_at=datetime.now(timezone.utc), reason="停止请求已发送，尚未观察到退出。")
    return SoftwareCancelResult(call_id=call_id, request_state="sent", stop_state="stopped" if process.returncode is not None else "unknown",
                                observed_at=datetime.now(timezone.utc))


__all__ = ["get_bundled_definitions", "get_operation", "get_package", "get_package_source", "install_package",
           "list_packages", "list_siril_commands", "maintain_package", "prepare_package", "set_package_node_definition_ids",
           "uninstall_package", "invoke_operation", "inspect_operation", "cancel_operation", "get_usage",
           "preview_autostretch", "get_preview_usage"]
