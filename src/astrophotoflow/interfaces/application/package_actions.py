"""Coordinate confirmed package maintenance and native node refresh."""

import asyncio
import logging
from threading import Lock
from urllib.parse import quote
from uuid import UUID, uuid4

import httpx
from fastapi import FastAPI

from astrophotoflow.contracts.nodes import DefinitionWriteResult, NodeDefinition, definition_content_token
from astrophotoflow.contracts.packages import (
    PackageMutationResult,
    PendingSoftwareAction,
    SoftwarePackageDetails,
    SoftwarePlanNodeChange,
    SoftwarePlanSummary,
)
from astrophotoflow.contracts.software import ConfirmSoftwareEvent, SoftwareInstallRequest, SoftwareUninstallRequest
from astrophotoflow.core.config import ConfigurationError, Settings
from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.localization import exception_error, localized_error, workspace_locale
from astrophotoflow.core.workbench import status as workbench_status
from astrophotoflow.modules.nodes.public import list_definitions
from astrophotoflow.modules.software.public import (
    get_bundle_metadata,
    get_bundled_definitions,
    get_package,
    get_package_source,
    install_package,
    maintain_package,
    resolve_release,
    set_package_node_definition_ids,
    uninstall_package,
)

logger = logging.getLogger("astrophotoflow.service")


def register_package_actions(app: FastAPI, settings: Settings, token: str) -> None:
    app.state.software_page_tokens = {}
    app.state.software_actions = {}
    app.state.software_results = {}
    app.state.software_tasks = {}
    app.state.software_action_lock = Lock()
    def bundle_definition_plan(package_id, version, *, uninstall=False, selected_release=None):
        current = list_definitions(settings.workspace)
        current_by_id = {item.definition.definition_id: item for item in current}
        package_current = {
            item.definition.definition_id: item for item in current
            if item.definition.source == "package" and item.definition.execution.package_id == package_id
        }
        if uninstall:
            changes = [SoftwarePlanNodeChange(
                definition_id=item.definition.definition_id, name=item.definition.name, action="retain",
                before_content_token=item.content_token, after_content_token=item.content_token,
            ) for item in package_current.values()]
            changes.sort(key=lambda item: str(item.definition_id))
            return changes
        options = {'selected_release': selected_release} if selected_release is not None else {}
        if get_package(settings, package_id).development_source is not None:
            _, _, declarations = get_bundle_metadata(settings, package_id)
        else:
            declarations = get_bundled_definitions(settings, package_id, version, **options)
        bundled = [NodeDefinition.model_validate(item) for item in declarations]
        changes = []
        definitions_by_id = {}
        for definition in bundled:
            saved = current_by_id.get(definition.definition_id)
            if saved is not None and (saved.definition.source != "package" or saved.definition.execution.package_id != package_id):
                raise ApiError(409, "NODE_CONTENT_CONFLICT", "软件包配套节点ID已属于其他定义。", message_key='a_bundled_node_id_already_belongs_to_another_definition')
            token = definition_content_token(definition)
            changes.append(SoftwarePlanNodeChange(
                definition_id=definition.definition_id,
                name=definition.name,
                action="create" if saved is None else "retain" if saved.content_token == token else "update",
                before_content_token=saved.content_token if saved is not None else None,
                after_content_token=token,
            ))
            definitions_by_id[definition.definition_id] = definition
        for definition_id, saved in package_current.items():
            if definition_id not in definitions_by_id:
                changes.append(SoftwarePlanNodeChange(
                    definition_id=definition_id,
                    name=saved.definition.name,
                    action="retain",
                    before_content_token=saved.content_token,
                    after_content_token=saved.content_token,
                ))
                definitions_by_id[definition_id] = saved.definition
        changes.sort(key=lambda item: str(item.definition_id))
        return changes

    def validate_install_request(package, body: SoftwareInstallRequest | SoftwareUninstallRequest) -> None:
        if isinstance(body, SoftwareUninstallRequest):
            if package.package_token != body.package_token:
                raise ApiError(409, "SOFTWARE_CONTENT_CONFLICT", "软件包状态已变化，请重新读取后卸载。", message_key='the_package_state_has_changed_read_it_again_before_uninstalling')
            if package.install_path is None or package.operation_state in {"running", "unknown"}:
                raise ApiError(409, "SOFTWARE_BUSY", "当前安装或操作状态不能确认，无法卸载。", message_key='the_installation_or_operation_state_is_unknown_uninstallation_is_blocked')
            return
        if body.bundle_version is None and body.version not in package.available_versions:
            raise ApiError(422, "VALIDATION_ERROR", "请求的版本不在软件维护清单中。", message_key='the_requested_version_is_not_in_the_maintained_software_catalog')
        if package.package_token != body.package_token:
            raise ApiError(409, "SOFTWARE_CONTENT_CONFLICT", "软件包状态已变化，请重新读取后请求安装。", message_key='the_package_state_has_changed_read_it_again_before_requesting_installation')
        if package.operation_state == "running":
            raise ApiError(409, "SOFTWARE_BUSY", "软件包已有动作正在执行。", message_key='a_software_action_is_already_running_for_this_package')
        if package.availability not in {"not_installed", "ready", "not_ready"} and not package.migration_required:
            raise ApiError(503, "SOFTWARE_NOT_READY", package.reason or "当前软件状态不允许重新安装。", message_key='software_install_not_allowed', fields=[{'path': 'software', 'message': package.reason}] if package.reason else [])

    def request_software_action(package_id: str, body: SoftwareInstallRequest | SoftwareUninstallRequest) -> PendingSoftwareAction:
        package = get_package(settings, package_id)
        validate_install_request(package, body)
        try:
            workbench = workbench_status(settings.workspace / "config.toml")
        except (OSError, ConfigurationError, ValueError) as exc:
            raise ApiError(503, "WORKBENCH_NOT_READY", "无法确认工作台网页已就绪。", message_key='could_not_confirm_that_the_workbench_webpage_is_ready') from exc
        if not workbench.ready or not workbench.web_url:
            raise ApiError(503, "WORKBENCH_NOT_READY", "必须从已就绪的工作台网页确认软件安装。", message_key='confirm_installation_from_the_ready_workbench_webpage')
        uninstall = isinstance(body, SoftwareUninstallRequest)
        target = None if uninstall else resolve_release(settings, package_id, body.bundle_version, body.release_token)
        if target is not None and target['manifest']['software_version'] != body.version:
            raise ApiError(409, 'BUNDLE_RELEASE_CHANGED', 'The selected software version does not match the release.', message_key='release_changed')
        selected = target if not uninstall and body.bundle_version is not None else None
        node_changes = bundle_definition_plan(package_id, body.version if not uninstall else package.installed_version,
                                              uninstall=uninstall, selected_release=selected)
        operation_id = uuid4()
        plan = SoftwarePlanSummary(
            action="uninstall" if uninstall else "update" if package.installed_version and not package.migration_required else "install",
            package_id=package_id,
            current_version=package.installed_version,
            target_version=None if uninstall else body.version,
            source=None if uninstall else get_package_source(package_id, body.version, **({'selected_release': selected} if selected is not None else {})),
            install_path=settings.workspace / "software" / package_id / "bundle" / "app",
            package_token=body.package_token,
            impact_token=None,
            restart_required=False,
            restart_reason=None,
            node_changes=node_changes,

            current_bundle_version=package.bundle_version,
            target_bundle_version=target['manifest']['bundle_version'] if target else None,
            target_tag=target['tag'] if target else None,
            target_commit=target['commit'] if target else None,
            release_token=body.release_token if not uninstall else None,
        )
        confirmation_url = (
            f"{workbench.web_url.rstrip('/')}/#/workflows?apf_panel=software&"
            f"package_id={quote(package_id, safe='')}&operation_id={operation_id}"
        )
        pending = PendingSoftwareAction(
            operation_id=operation_id, state="awaiting_confirmation", plan=plan,
            confirmation_url=confirmation_url, error=None,
        )
        with app.state.software_action_lock:
            previous = app.state.software_actions.get(package_id)
            if previous is not None and previous.state == "running":
                raise ApiError(409, "SOFTWARE_BUSY", "软件包已有动作正在执行。", message_key='a_software_action_is_already_running_for_this_package')
            package = get_package(settings, package_id)
            validate_install_request(package, body)
            if previous is not None:
                app.state.software_results.pop(previous.operation_id, None)
            app.state.software_actions[package_id] = pending
        return pending

    def get_software_package_details(package_id: str, *, operation_id: UUID | None = None) -> SoftwarePackageDetails:
        package = get_package(settings, package_id)
        with app.state.software_action_lock:
            current_action = app.state.software_actions.get(package_id)
            if operation_id is not None and (current_action is None or current_action.operation_id != operation_id):
                raise ApiError(409, "SOFTWARE_ACTION_EXPIRED", "该软件动作已被替换或服务重启后失效。", message_key='this_software_action_was_replaced_or_invalidated_by_a_service_restart')
            result = app.state.software_results.get(current_action.operation_id) if current_action is not None else None
        return SoftwarePackageDetails(package=package, current_action=current_action, result=result)

    async def execute_software_action(pending: PendingSoftwareAction) -> None:
        definition_results = []
        error = None
        try:
            selected = await asyncio.to_thread(resolve_plan_release, pending)
            async with maintain_package(pending.plan.package_id):
                package = get_package(settings, pending.plan.package_id)
                if package.package_token != pending.plan.package_token:
                    raise ApiError(409, "SOFTWARE_CONTENT_CONFLICT", "确认后软件包状态发生变化，未开始安装。", message_key='the_package_state_changed_after_confirmation_installation_was_not_started')
                if pending.plan.action == "uninstall":
                    installed = await uninstall_package(settings, pending.plan.package_id, pending.plan.package_token)
                else:
                    installed = await install_package(
                        settings, pending.plan.package_id, pending.plan.target_version, pending.plan.package_token,
                        **({'selected_release': selected} if selected is not None else {}),
                    )
                try:
                    response = await app.state.http_client.post(
                        settings.allowed_origins[0] + "/astrophotoflow/internal/bundles/reload",
                        headers={"Authorization": f"Bearer {token}"}, timeout=60,
                    )
                    response.raise_for_status()
                except httpx.HTTPError as exc:
                    raise ApiError(503, "BUNDLE_LOAD_FAILED", "Bundle 文件已更新，但无法确认节点热加载；请查询软件状态。", message_key='bundle_files_were_updated_but_node_hot_loading_could_not_be_confirmed_query') from exc
                installed = get_package(settings, pending.plan.package_id)
                if pending.plan.action != "uninstall" and installed.effective_availability != "ready":
                    raise ApiError(503, "BUNDLE_LOAD_FAILED", installed.effective_reason or "Bundle 节点热加载失败。", message_key='bundle_load_failed', fields=[{'path': 'software', 'message': installed.effective_reason}] if installed.effective_reason else [])
                if pending.plan.action != "uninstall":
                    actual = {item.definition.definition_id: item for item in list_definitions(settings.workspace)
                              if item.definition.source == "package" and item.definition.execution.package_id == pending.plan.package_id}
                    set_package_node_definition_ids(settings, pending.plan.package_id, list(actual))
                    for change in pending.plan.node_changes:
                        if change.action not in {"create", "update"}:
                            continue
                        saved = actual.get(change.definition_id)
                        applied = saved is not None and saved.content_token == change.after_content_token
                        definition_results.append(DefinitionWriteResult(definition_id=change.definition_id,
                            action=change.action, applied=applied, content=saved,
                            error=None if applied else localized_error(workspace_locale(settings.workspace), 'BUNDLE_LOAD_FAILED', 'bundle_node_definition_not_confirmed')))
                write_error = next((item.error for item in definition_results if not item.applied), None)
                if write_error is not None:
                    error = write_error
            result = PackageMutationResult(
                package=installed, definition_results=definition_results, loads=[], error=error,
            )
            final_state = "failed" if error is not None else "completed"
        except ApiError as exc:
            result = PackageMutationResult(
                package=get_package(settings, pending.plan.package_id), definition_results=definition_results,
                loads=[],
                error=exception_error(workspace_locale(settings.workspace), exc, code='INTERNAL_ERROR', message_key='software_install_or_definition_write_failed'),
            )
            final_state = "failed"
        except Exception as exc:
            logger.exception("software install failed package=%s operation=%s", pending.plan.package_id, pending.operation_id)
            result = PackageMutationResult(
                package=get_package(settings, pending.plan.package_id), definition_results=definition_results,
                loads=[], error=exception_error(workspace_locale(settings.workspace), exc, code='INTERNAL_ERROR', message_key='software_install_or_definition_write_failed'),
            )
            final_state = "failed"
        with app.state.software_action_lock:
            app.state.software_results[pending.operation_id] = result
            app.state.software_actions[pending.plan.package_id] = pending.model_copy(
                update={"state": final_state, "error": result.error}
            )


    async def confirm_software_action(body: ConfirmSoftwareEvent, *, page_id: UUID, page_token: str) -> PendingSoftwareAction:
        async with app.state.maintenance_lock:
            return await _confirm_software_action_locked(body, page_id=page_id, page_token=page_token)

    def resolve_plan_release(pending):
        if pending.plan.release_token is None:
            return None
        selected = resolve_release(settings, pending.plan.package_id, pending.plan.target_bundle_version, pending.plan.release_token)
        if selected['commit'] != pending.plan.target_commit or selected['tag'] != pending.plan.target_tag:
            raise ApiError(409, 'BUNDLE_RELEASE_CHANGED', 'The confirmed release target changed.', message_key='release_changed')
        return selected

    def start_software_action(pending: PendingSoftwareAction, *, page_id: UUID, page_token: str,
                              workbench, selected_release=None) -> PendingSoftwareAction:
        expected_base = pending.confirmation_url.split("/#/", 1)[0]
        if not workbench.ready or workbench.web_url != expected_base:
            raise ApiError(409, "SOFTWARE_ACTION_EXPIRED", "工作台网页地址已变化，请重新查看安装计划。", message_key='the_workbench_webpage_address_has_changed_review_the_installation_plan_agai')
        package = get_package(settings, pending.plan.package_id)
        if pending.plan.release_token is not None and selected_release is None:
            raise ApiError(409, 'BUNDLE_RELEASE_CHANGED', 'Release validation is required before confirmation.', message_key='release_changed')
        node_changes = bundle_definition_plan(pending.plan.package_id, pending.plan.target_version,
                                              uninstall=pending.plan.action == "uninstall", selected_release=selected_release)
        with app.state.software_action_lock:
            if app.state.software_page_tokens.get(page_id) != page_token:
                raise ApiError(409, "SOFTWARE_ACTION_EXPIRED", "软件确认页面连接已改变。", message_key='the_software_confirmation_page_connection_has_changed')
            current = app.state.software_actions.get(pending.plan.package_id)
            if current is None or current.operation_id != pending.operation_id or current.state != "awaiting_confirmation":
                raise ApiError(409, "SOFTWARE_ACTION_EXPIRED", "该软件动作已被替换或失效。", message_key='this_software_action_was_replaced_or_has_expired')
            if app.state.maintenance or app.state.shutdown_started:
                raise ApiError(409, "WORKBENCH_MAINTENANCE", "工作台正在维护，无法确认软件安装。", message_key='the_workbench_is_undergoing_maintenance_installation_cannot_be_confirmed')
            if package.package_token != pending.plan.package_token:
                expired = current.model_copy(update={
                    "state": "expired",
                    "error": localized_error(workspace_locale(settings.workspace), 'SOFTWARE_ACTION_EXPIRED', 'action_package_changed'),
                })
                app.state.software_actions[pending.plan.package_id] = expired
                raise ApiError(409, "SOFTWARE_ACTION_EXPIRED", "软件包状态已变化，请重新查看安装计划。", message_key='the_package_state_has_changed_review_the_installation_plan_again')
            if node_changes != pending.plan.node_changes:
                expired = current.model_copy(update={
                    "state": "expired",
                    "error": localized_error(workspace_locale(settings.workspace), 'SOFTWARE_ACTION_EXPIRED', 'action_nodes_changed'),
                })
                app.state.software_actions[pending.plan.package_id] = expired
                raise ApiError(409, "SOFTWARE_ACTION_EXPIRED", "配套节点定义已变化，请重新查看安装计划。", message_key='bundled_node_definitions_have_changed_review_the_installation_plan_again')
            running = current.model_copy(update={"state": "running"})
            app.state.software_actions[pending.plan.package_id] = running
            task = asyncio.create_task(execute_software_action(running))
            app.state.software_tasks[pending.plan.package_id] = task
            return running

    async def _confirm_software_action_locked(body: ConfirmSoftwareEvent, *, page_id: UUID,
                                              page_token: str) -> PendingSoftwareAction:
        with app.state.software_action_lock:
            if app.state.software_page_tokens.get(page_id) != page_token:
                raise ApiError(409, "SOFTWARE_ACTION_EXPIRED", "软件确认页面连接已改变。", message_key='the_software_confirmation_page_connection_has_changed')
            pending = next((item for item in app.state.software_actions.values() if item.operation_id == body.operation_id), None)
            if pending is None or pending.operation_id != body.operation_id:
                raise ApiError(409, "SOFTWARE_ACTION_EXPIRED", "该软件动作已被替换或失效。", message_key='this_software_action_was_replaced_or_has_expired')
            if pending.state != "awaiting_confirmation":
                return pending
            if app.state.maintenance or app.state.shutdown_started:
                raise ApiError(409, "WORKBENCH_MAINTENANCE", "工作台正在维护，无法确认软件安装。", message_key='the_workbench_is_undergoing_maintenance_installation_cannot_be_confirmed')
        workbench = await asyncio.to_thread(workbench_status, settings.workspace / "config.toml")
        selected = await asyncio.to_thread(resolve_plan_release, pending)
        return start_software_action(pending, page_id=page_id, page_token=page_token, workbench=workbench, selected_release=selected)

    app.state.request_software_action = request_software_action
    app.state.get_software_package_details = get_software_package_details
    app.state.confirm_software_action = confirm_software_action
    app.state.start_software_action = start_software_action
