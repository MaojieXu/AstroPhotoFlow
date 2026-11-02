from copy import deepcopy

from astrophotoflow.modules.software.metadata import catalog as maintained_bundle_catalog
from astrophotoflow.modules.software.metadata import contained, read_bundle, read_bundle_locales

"""Read fixed package, operation and command capabilities."""
import hashlib
import json

import psutil

from astrophotoflow.contracts.bundles import BundleManifest
from astrophotoflow.contracts.software import SoftwareCommand, SoftwarePackage, SoftwarePackageState, SoftwarePreparation
from astrophotoflow.core.config import Settings
from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.localization import error_message, workspace_locale
from astrophotoflow.modules.software import bundles, development
from astrophotoflow.modules.software.packages.maintenance import PACKAGE_LOCKS
from astrophotoflow.modules.software.packages.state import state_from_package, state_path, write_package_state


def get_package(settings: Settings, package_id: str) -> SoftwarePackage:
    from astrophotoflow.modules.software.releases import version_key
    release = bundles.release(package_id)
    installed_root = settings.workspace / 'software' / package_id / 'bundle'
    manifest = read_bundle(installed_root)[0] if installed_root.is_dir() else BundleManifest.model_validate(release['manifest'])
    path = state_path(settings, package_id)
    state = SoftwarePackageState.model_validate_json(path.read_text(encoding="utf-8")) if path.is_file() else SoftwarePackageState(
        installed_version=None, install_path=None, availability="not_installed", reason="尚未安装 Bundle。",
        operation=None, operation_state="idle", phase=None, progress=None, last_error=None, node_definition_ids=[])
    root = path.parent / "bundle"
    reason_key = 'bundle_not_installed' if state.availability == 'not_installed' else None
    lock_path = path.parent / "bundle-lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8")) if lock_path.is_file() else {}
    restart_required = False
    active_lock = PACKAGE_LOCKS.get(package_id)
    if state.operation_state == 'running' and (active_lock is None or not active_lock.locked()):
        reason_key = 'bundle_interrupted'
        state = state.model_copy(update={'operation_state': 'unknown', 'availability': 'unknown',
                                        'reason': '上次安装或卸载被中断，无法确认结果。'})
    if state.installed_version is not None:
        if not root.is_dir():
            reason_key = 'bundle_migration_needed'
            state = state.model_copy(update={"availability": "not_ready", "reason": "现有安装尚未迁移到独立 Bundle，请安装 Bundle；保留原程序。"})
        elif not contained(root, manifest.executable).is_file():
            reason_key = 'bundle_executable_missing'
            state = state.model_copy(update={"availability": "not_ready", "reason": "Bundle 程序缺失。"})
        else:
            expected = root / "app"
            if state.install_path is None or state.install_path.resolve() != expected.resolve():
                raise ApiError(409, "BUNDLE_STATE_CONFLICT", "Bundle 安装位置与状态记录不一致。", message_key='the_bundle_installation_location_does_not_match_its_state_record')
            observation = path.parent / "native-load.json"
            loaded = json.loads(observation.read_text(encoding="utf-8")) if observation.is_file() else {}
            try:
                native_alive = psutil.Process(loaded["pid"]).create_time() == loaded["create_time"]
            except (KeyError, psutil.Error):
                native_alive = False
            if loaded.get("commit") != lock.get("commit") or not loaded.get("ready") or not native_alive:
                reason_key = 'bundle_waiting_for_nodes' if not loaded.get('reason') else None
                state = state.model_copy(update={"availability": "not_ready", "reason": loaded.get("reason") or "Bundle 已安装，等待节点热加载。"})
            elif state.operation_state not in {"unknown", "running"}:
                reason_key = None
                state = state.model_copy(update={"availability": "ready", "reason": None})
    token = hashlib.sha256(json.dumps({"release": release, "state": state.model_dump(mode="json")}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    display_state = state.model_dump()
    if reason_key:
        display_state['reason'] = error_message(workspace_locale(settings.workspace), '', reason_key)
    source = development.source_state(settings.workspace, package_id)
    if source is not None and source.state == 'ready':
        observation = development.observation_path(settings.workspace, package_id)
        loaded = json.loads(observation.read_text(encoding='utf-8')) if observation.is_file() else {}
        try:
            alive = psutil.Process(loaded['pid']).create_time() == loaded['create_time']
        except (KeyError, psutil.Error):
            alive = False
        matches = loaded.get('root') == str(source.root) and loaded.get('fingerprint') == source.fingerprint
        if not alive or not matches or not loaded.get('ready'):
            diagnostic = loaded.get('reason') if alive and matches else None
            source = source.model_copy(update={'state': 'failed' if diagnostic else 'building',
                'error': diagnostic or 'Waiting for development nodes to load.'})
    return SoftwarePackage(package_id=package_id, name=manifest.name, development_source=source,
        available_versions=[release["manifest"]["software_version"]], package_token=token,
        bundle_version=lock.get("bundle_version"), bundle_commit=lock.get("commit"), restart_required=restart_required,
        update_available=state.installed_version is not None and root.is_dir()
            and version_key(release['manifest']['bundle_version']) > version_key(manifest.bundle_version),
        migration_required=state.installed_version is not None and not root.is_dir(), **display_state)


def list_packages(settings: Settings):
    return [get_package(settings, key) for key in maintained_bundle_catalog()]


def get_package_source(package_id: str, version: str, *, selected_release=None):
    release = selected_release if selected_release is not None else bundles.release(package_id)
    if version != release["manifest"]["software_version"]:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "未找到发布版本。", message_key='the_release_version_was_not_found')
    return release["repository"] + " @ " + release["tag"] + " (" + (release["commit"] or "unreleased") + ")"


def get_bundled_definitions(settings, package_id, version, *, selected_release=None):
    release = selected_release if selected_release is not None else bundles.release(package_id)
    if version != release["manifest"]["software_version"]:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "未找到发布版本。", message_key='the_release_version_was_not_found')
    return deepcopy(release["nodes"])


def get_operation(settings, package_id, version, operation_id):
    manifest, _, _ = bundles.metadata(settings.workspace, package_id)
    if version != manifest.software_version:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "未找到软件版本。", message_key='the_software_version_was_not_found')
    package = get_package(settings, package_id)
    return bundles.operation(settings.workspace, package_id, operation_id, package.effective_availability == "ready", package.effective_reason)


def list_operations(settings, package_id):
    _, entries, _ = bundles.metadata(settings.workspace, package_id)
    package = get_package(settings, package_id)
    return [bundles.operation_from_entry(entry, package.effective_availability == 'ready', package.effective_reason) for entry in entries]


def get_bundle_metadata(settings, package_id):
    return bundles.metadata(settings.workspace, package_id)


def get_bundle_display(settings, package_id):
    root = development.source_root(settings.workspace, package_id)
    if root.is_dir():
        manifest, operations, _ = bundles.metadata(settings.workspace, package_id)
        return read_bundle_locales(root, manifest, operations)
    return bundles.release(package_id).get('localizations', {})


def set_package_node_definition_ids(settings, package_id, definition_ids):
    state = state_from_package(get_package(settings, package_id))
    write_package_state(settings, package_id, state.model_copy(update={"node_definition_ids": definition_ids}))


def list_releases(settings, package_id):
    from astrophotoflow.modules.software.releases import list_releases as discover
    return discover(settings, package_id)


def resolve_release(settings, package_id, bundle_version, release_token):
    if bundle_version is None:
        return bundles.release(package_id)
    from astrophotoflow.modules.software.releases import resolve_release as resolve
    return resolve(settings, package_id, bundle_version, release_token)


def prepare_package(settings, package_id):
    return SoftwarePreparation(package=get_package(settings, package_id), user_action=None, ui_kind=None, ui_target=None)


def command_rows(command_bytes, assessment_bytes=None) -> list[SoftwareCommand]:
    commands = json.loads(command_bytes)
    assessments = json.loads(assessment_bytes)["commands"] if assessment_bytes is not None else []
    by_command = {row["command"]: row["assessment"] for row in assessments}
    if len(by_command) != len(assessments):
        raise ValueError("Duplicate command assessments in Bundle reference.")
    rows = [SoftwareCommand.model_validate({**item, "assessment": by_command.get(item["command"], item.get("assessment", {}))})
            for item in commands]
    names = {row.command for row in rows}
    if len(names) != len(rows) or not set(by_command).issubset(names):
        raise ValueError("Invalid command identities in Bundle reference.")
    return rows


def get_command_catalog(package_id: str, version: str, settings=None) -> list[SoftwareCommand]:
    if settings is not None:
        manifest, _, _ = bundles.metadata(settings.workspace, package_id)
        root = development.source_root(settings.workspace, package_id)
    else:
        manifest = BundleManifest.model_validate(bundles.release(package_id)['manifest'])
        root = None
    if version != manifest.software_version:
        raise ApiError(404, 'RESOURCE_NOT_FOUND', '未找到请求的软件命令目录。', message_key='the_requested_software_command_reference_was_not_found')
    if manifest.commands is None:
        raise ApiError(404, 'RESOURCE_NOT_FOUND', 'Bundle 没有提供命令参考目录。', message_key='the_installed_bundle_does_not_provide_a_command_reference')
    if root is not None and root.is_dir():
        command_bytes = contained(root, manifest.commands).read_bytes()
        assessment_bytes = contained(root, manifest.assessments).read_bytes() if manifest.assessments else None
    else:
        references = bundles.release(package_id)['reference_files']
        command_bytes = references[manifest.commands].encode('utf-8')
        assessment_bytes = references[manifest.assessments].encode('utf-8') if manifest.assessments else None
    return command_rows(command_bytes, assessment_bytes)


def list_package_ids() -> list[str]:
    return list(maintained_bundle_catalog())
