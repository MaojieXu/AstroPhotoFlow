"""Install and remove complete packages with rollback."""
import asyncio
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

import httpx

from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.localization import error_message, exception_error, workspace_locale
from astrophotoflow.modules.software import bundles
from astrophotoflow.modules.software.packages.catalog import get_package
from astrophotoflow.modules.software.packages.state import state_from_package, write_package_state


def rename_bundle(source, destination):
    # Version probes and Windows scanners can briefly hold executable handles.
    # Keep the swap synchronous so cancellation cannot strand its rollback.
    for attempt in range(6):
        try:
            source.rename(destination)
            return
        except OSError as exc:
            if getattr(exc, 'winerror', None) not in {5, 32, 33} or attempt == 5:
                raise
            time.sleep(0.05 * 2 ** attempt)


async def install_package(settings, package_id, version, expected_package_token, *, selected_release=None):
    release = selected_release if selected_release is not None else bundles.release(package_id)
    package = get_package(settings, package_id)
    if version != release["manifest"]["software_version"] or package.package_token != expected_package_token:
        raise ApiError(409, "SOFTWARE_CONTENT_CONFLICT", "软件状态或发布版本发生变化。", message_key='the_software_state_or_release_version_has_changed')
    if os.name != "nt":
        raise ApiError(503, "SOFTWARE_NOT_READY", "当前 Bundle 只支持 Windows。", message_key='this_bundle_supports_windows_only')
    directory = settings.workspace / "software" / package_id
    directory.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".bundle-install-", dir=directory))
    state = state_from_package(package)
    def report_progress(phase, progress):
        write_package_state(settings, package_id, state.model_copy(update={
            "operation": "install", "operation_state": "running", "phase": phase, "progress": progress, "last_error": None}), progress_only=True)

    activated = False
    old_lock = (directory / 'bundle-lock.json').read_bytes() if (directory / 'bundle-lock.json').is_file() else None
    old_load = (directory / 'native-load.json').read_bytes() if (directory / 'native-load.json').is_file() else None
    try:
        report_progress("cloning", 0.0)
        options = {'release_record': selected_release} if selected_release is not None else {}
        manifest, commit = await asyncio.to_thread(bundles.checkout, package_id, stage / "bundle", tool_root=settings.workspace / "software/.tools", on_progress=report_progress, **options)
        destination = directory / "bundle"
        previous = directory / "previous-bundle"
        if previous.exists():
            raise ApiError(409, "BUNDLE_STATE_CONFLICT", "上次版本仍待处理，未覆盖现有程序。", message_key='the_previous_version_is_still_pending_the_existing_installation_was_not_ove')
        if destination.exists():
            rename_bundle(destination, previous)
        try:
            rename_bundle(stage / "bundle", destination)
        except OSError:
            if previous.exists():
                rename_bundle(previous, destination)
            raise
        activated = True
        lock = {"repository": release["repository"], "tag": release["tag"], "commit": commit, "bundle_version": manifest.bundle_version}
        (directory / "bundle-lock.json").write_text(json.dumps(lock, indent=2), encoding="utf-8")
        (directory / "native-load.json").unlink(missing_ok=True)
        write_package_state(settings, package_id, state.model_copy(update={
            "installed_version": manifest.software_version, "install_path": destination / "app",
            "availability": "ready", "reason": None, "operation": "install", "operation_state": "completed", "phase": None, "progress": None, "last_error": None}))
        installed = get_package(settings, package_id)
    except (ApiError, OSError, ValueError, httpx.HTTPError, subprocess.SubprocessError) as exc:
        if activated:
            rename_bundle(directory / 'bundle', stage / 'failed-bundle')
            if (directory / 'previous-bundle').exists():
                rename_bundle(directory / 'previous-bundle', directory / 'bundle')
            for name, content in [('bundle-lock.json', old_lock), ('native-load.json', old_load)]:
                if content is None:
                    (directory / name).unlink(missing_ok=True)
                else:
                    (directory / name).write_bytes(content)
        failure = exception_error(workspace_locale(settings.workspace), exc, code='INSTALL_FAILED', message_key='install_failed')
        write_package_state(settings, package_id, state.model_copy(update={
            "availability": state.availability,
            "operation": "install", "operation_state": "failed", "phase": None, "progress": None,
            "last_error": failure.model_copy(update={'code': 'SOFTWARE_STATE_SAVE_FAILED' if isinstance(exc, ApiError) and exc.code == 'SOFTWARE_STATE_SAVE_FAILED' else 'INSTALL_FAILED'})}))
        if isinstance(exc, ApiError) and exc.code == "SOFTWARE_STATE_SAVE_FAILED":
            raise
        raise ApiError(503, "SOFTWARE_NOT_READY", f"Bundle 安装失败：{exc}", fields=failure.fields,
                       message_key='bundle_installation_failed_p0', message_params={'p0': exc if isinstance(exc, ApiError) else failure.message}) from exc
    finally:
        bundles.remove_checkout(stage, directory)
    if previous.exists():
        await asyncio.to_thread(bundles.remove_checkout, previous, directory)
    return installed


async def uninstall_package(settings, package_id, expected_package_token):
    package = get_package(settings, package_id)
    if package.package_token != expected_package_token:
        raise ApiError(409, "SOFTWARE_CONTENT_CONFLICT", "软件状态变化，请重新确认。", message_key='the_software_state_has_changed_confirm_it_again')
    directory = settings.workspace.resolve() / "software" / package_id
    previous = state_from_package(package)
    write_package_state(settings, package_id, previous.model_copy(update={"operation": "uninstall", "operation_state": "running", "phase": "removing"}))
    try:
        for name in ("bundle", "app", "previous-bundle"):
            target = directory / name
            if target.exists():
                await asyncio.to_thread(bundles.remove_checkout, target, directory)
    except (OSError, ValueError) as exc:
        write_package_state(settings, package_id, previous.model_copy(update={
            "operation": "uninstall", "operation_state": "failed", "phase": None,
            "availability": "unknown", "reason": error_message(workspace_locale(settings.workspace), '', 'uninstall_failed'),
            "last_error": exception_error(workspace_locale(settings.workspace), exc, code='UNINSTALL_FAILED', message_key='uninstall_failed')}))
        raise ApiError(503, "SOFTWARE_NOT_READY", f"Bundle 卸载失败：{exc}", fields=exception_error(workspace_locale(settings.workspace), exc, code='UNINSTALL_FAILED', message_key='uninstall_failed').fields, message_key='bundle_uninstallation_failed_p0', message_params={'p0': exc if isinstance(exc, ApiError) else error_message(workspace_locale(settings.workspace), '', 'uninstall_failed')}) from exc
    for name in ("bundle-lock.json", "native-load.json"):
        (directory / name).unlink(missing_ok=True)
    write_package_state(settings, package_id, state_from_package(package).model_copy(update={
        "installed_version": None, "install_path": None, "availability": "not_installed", "reason": "尚未安装 Bundle。",
        "operation": "uninstall", "operation_state": "completed", "phase": None, "last_error": None}))
    return get_package(settings, package_id)
