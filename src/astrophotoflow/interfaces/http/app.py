import logging
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Request
import httpx
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from astrophotoflow.core.database.db import Database
from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.http import authenticate
from astrophotoflow.core.config import Settings, ConfigurationError, _update_running_state
from astrophotoflow.core.workbench import status as workbench_status
from astrophotoflow.modules.data.public import DisplayPreviews, MediaViews, import_workers, data_busy
from astrophotoflow.contracts.workbench import BusyState
from astrophotoflow.contracts.common import ErrorDetail, StrictModel, UuidInput
from astrophotoflow.contracts.nodes import NodeDefinition, SavedDefinition, definition_content_token
from astrophotoflow.contracts.software import ConfirmSoftwareEvent, SoftwareInstallRequest, SoftwareUninstallRequest
from astrophotoflow.contracts.workflows import (
    NativePageConfirmSoftwareEvent, NativePageEvent, NativePageOpenEvent, NativePageReply,
    PackageMutationResult, PendingSoftwareAction, SoftwarePackageDetails, SoftwarePlanNodeChange,
    SoftwarePlanSummary,
)
from astrophotoflow.modules.nodes.public import list_definitions, replace_package_definitions
from astrophotoflow.modules.software.public import (
    get_bundled_definitions, get_package, get_package_source, install_package,
    maintain_package, set_package_node_definition_ids, uninstall_package, get_usage, list_packages,
)
from sqlalchemy.exc import SQLAlchemyError
from typing import Literal
from astrophotoflow.modules.data.routes import router as data_router
from astrophotoflow.modules.software.routes import router as software_router
from astrophotoflow.modules.nodes.routes import router as nodes_router
from astrophotoflow.modules.workflows.canvas import router as canvas_router
from astrophotoflow.modules.workflows.siril_preview import SirilPreviews, router as siril_preview_router
from astrophotoflow.interfaces.http import system


logger = logging.getLogger("astrophotoflow.service")


class MaintenanceAction(StrictModel):
    action: Literal["enter", "release"]
    operation_id: UuidInput


def create_app(settings: Settings, token: str) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        from astrophotoflow.modules.workflows.software_calls import recover_siril_calls
        await recover_siril_calls(settings)
        with import_workers(settings) as workers:
            app.state.import_workers = workers
            app.state.display_previews = DisplayPreviews(app.state.database, settings, workers[1])
            app.state.media_views = MediaViews(app.state.database, settings, workers[1])
            app.state.siril_previews = SirilPreviews(app.state.database, settings, workers[1], app.state.media_views.cache)
            try:
                yield
            finally:
                await app.state.siril_previews.close()

    app = FastAPI(lifespan=lifespan, title="AstroPhotoFlow Asset Service", version="1.0.0", docs_url=None, redoc_url=None)
    app.include_router(canvas_router)
    app.include_router(siril_preview_router)
    app.state.siril_previews = None
    app.state.settings = settings
    app.state.token = token
    app.state.database = Database(settings.database_path)
    app.state.maintenance_lock = asyncio.Lock()
    app.state.maintenance = False
    app.state.maintenance_owner = None
    app.state.shutdown_started = False
    app.state.software_page_tokens = {}
    app.state.software_actions = {}
    app.state.software_results = {}
    app.state.software_tasks = {}
    app.state.software_action_lock = Lock()
    from astrophotoflow.modules.workflows.software_calls import register_siril_calls
    register_siril_calls(app, settings)

    def set_maintenance(owner: UUID | None):
        _update_running_state(settings.workspace, {"maintenance_operation_id": str(owner) if owner is not None else None})
        app.state.maintenance_owner = owner
        app.state.maintenance = owner is not None

    def bundle_definition_plan(package_id, version, *, uninstall=False):
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
            return changes, [item.definition for item in package_current.values()], {key: item.content_token for key, item in package_current.items()}
        bundled = [NodeDefinition.model_validate(item) for item in get_bundled_definitions(settings, package_id, version)]
        changes = []
        definitions_by_id = {}
        for definition in bundled:
            saved = current_by_id.get(definition.definition_id)
            if saved is not None and (saved.definition.source != "package" or saved.definition.execution.package_id != package_id):
                raise ApiError(409, "NODE_CONTENT_CONFLICT", "软件包配套节点ID已属于其他定义。")
            token = definition_content_token(definition)
            if saved is not None and saved.content_token != token and saved.definition.model_dump(exclude={'name', 'description'}) != definition.model_dump(exclude={'name', 'description'}):
                raise ApiError(409, "SOFTWARE_CONTENT_CONFLICT", "现有软件包定义与待安装版本不同，需先通过B55确认影响。")
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
        expected_tokens = {definition_id: saved.content_token for definition_id, saved in package_current.items()}
        changes.sort(key=lambda item: str(item.definition_id))
        definitions = [definitions_by_id[definition_id] for definition_id in sorted(definitions_by_id, key=str)]
        return changes, definitions, expected_tokens

    def validate_install_request(package, body: SoftwareInstallRequest | SoftwareUninstallRequest) -> None:
        if get_usage(package.package_id) or any(not task.done() for task in app.state.siril_calls.values()):
            raise ApiError(409, "SOFTWARE_BUSY", "软件仍有实际调用或未知占用。")
        if isinstance(body, SoftwareUninstallRequest):
            if package.package_token != body.package_token:
                raise ApiError(409, "SOFTWARE_CONTENT_CONFLICT", "软件包状态已变化，请重新读取后卸载。")
            if package.install_path is None or package.operation_state in {"running", "unknown"}:
                raise ApiError(409, "SOFTWARE_BUSY", "当前安装或操作状态不能确认，无法卸载。")
            return
        if body.version not in package.available_versions:
            raise ApiError(422, "VALIDATION_ERROR", "请求的版本不在软件维护清单中。")
        if package.package_token != body.package_token:
            raise ApiError(409, "SOFTWARE_CONTENT_CONFLICT", "软件包状态已变化，请重新读取后请求安装。")
        if package.operation_state == "running":
            raise ApiError(409, "SOFTWARE_BUSY", "软件包已有动作正在执行。")
        if package.availability != "not_installed" and not package.migration_required:
            raise ApiError(503, "SOFTWARE_NOT_READY", package.reason or "当前软件状态不允许重新安装。")

    def request_software_action(package_id: str, body: SoftwareInstallRequest | SoftwareUninstallRequest) -> PendingSoftwareAction:
        package = get_package(settings, package_id)
        validate_install_request(package, body)
        try:
            workbench = workbench_status(settings.workspace / "config.toml")
        except (OSError, ConfigurationError, ValueError) as exc:
            raise ApiError(503, "WORKBENCH_NOT_READY", "无法确认工作台网页已就绪。") from exc
        if not workbench.ready or not workbench.web_url:
            raise ApiError(503, "WORKBENCH_NOT_READY", "必须从已就绪的工作台网页确认软件安装。")
        uninstall = isinstance(body, SoftwareUninstallRequest)
        node_changes, _, _ = bundle_definition_plan(package_id, body.version if not uninstall else package.installed_version, uninstall=uninstall)
        operation_id = uuid4()
        plan = SoftwarePlanSummary(
            action="uninstall" if uninstall else "install",
            package_id=package_id,
            current_version=package.installed_version,
            target_version=None if uninstall else body.version,
            source=None if uninstall else get_package_source(package_id, body.version),
            install_path=settings.workspace / "software" / package_id / "bundle" / "app",
            package_token=body.package_token,
            impact_token=None,
            restart_required=True,
            restart_reason="完成后在空闲状态重启工作台以加载节点；繁忙时拒绝重启。",
            node_changes=node_changes,
            workflow_impacts=[],
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
                raise ApiError(409, "SOFTWARE_BUSY", "软件包已有动作正在执行。")
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
                raise ApiError(409, "SOFTWARE_ACTION_EXPIRED", "该软件动作已被替换或服务重启后失效。")
            result = app.state.software_results.get(current_action.operation_id) if current_action is not None else None
        return SoftwarePackageDetails(package=package, current_action=current_action, result=result)

    async def execute_software_action(pending: PendingSoftwareAction, definitions: list[NodeDefinition],
                                      expected_tokens: dict[UUID, str]) -> None:
        definition_results = []
        error = None
        try:
            async with maintain_package(pending.plan.package_id):
                package = get_package(settings, pending.plan.package_id)
                if package.package_token != pending.plan.package_token:
                    raise ApiError(409, "SOFTWARE_CONTENT_CONFLICT", "确认后软件包状态发生变化，未开始安装。")
                if pending.plan.action == "uninstall":
                    installed = await uninstall_package(settings, pending.plan.package_id, pending.plan.package_token)
                else:
                    installed = await install_package(
                        settings, pending.plan.package_id, pending.plan.target_version, pending.plan.package_token,
                    )
                    definition_results = replace_package_definitions(
                        settings.workspace, pending.plan.package_id, definitions, expected_tokens,
                    )
                    actual_definition_ids = [
                        item.definition.definition_id for item in list_definitions(settings.workspace)
                        if item.definition.source == "package" and item.definition.execution.package_id == pending.plan.package_id
                    ]
                    set_package_node_definition_ids(settings, pending.plan.package_id, actual_definition_ids)
                installed = get_package(settings, pending.plan.package_id)
                write_error = next((item.error for item in definition_results if not item.applied), None)
                if write_error is not None:
                    error = write_error
            result = PackageMutationResult(
                package=installed, definition_results=definition_results, loads=[], workflow_results=[], error=error,
            )
            final_state = "failed" if error is not None else "completed"
        except ApiError as exc:
            result = PackageMutationResult(
                package=get_package(settings, pending.plan.package_id), definition_results=definition_results,
                loads=[], workflow_results=[],
                error=ErrorDetail(code=exc.code, message=exc.message, fields=exc.fields),
            )
            final_state = "failed"
        except Exception as exc:
            logger.exception("software install failed package=%s operation=%s", pending.plan.package_id, pending.operation_id)
            result = PackageMutationResult(
                package=get_package(settings, pending.plan.package_id), definition_results=definition_results,
                loads=[], workflow_results=[], error=ErrorDetail(code="INTERNAL_ERROR", message="软件安装或配套定义写入失败。", fields=[]),
            )
            final_state = "failed"
        with app.state.software_action_lock:
            app.state.software_results[pending.operation_id] = result
            app.state.software_actions[pending.plan.package_id] = pending.model_copy(
                update={"state": final_state, "error": result.error}
            )
        if final_state == "completed" and pending.plan.restart_required:
            asyncio.get_running_loop().call_soon(schedule_bundle_restart, pending.plan.package_id)

    def schedule_bundle_restart(package_id):
        from astrophotoflow.core.workbench import request_restart
        async def restart_when_idle():
            try:
                import json
                operation_id = uuid4()
                (settings.workspace / 'software' / package_id / 'bundle-restart.json').write_text(
                    json.dumps({'operation_id': str(operation_id)}), encoding='utf-8')
                await asyncio.to_thread(request_restart, settings.workspace / "config.toml", operation_id)
            except Exception:
                logger.exception("Bundle installed; controlled restart was refused. package=%s", package_id)
        asyncio.create_task(restart_when_idle())


    async def confirm_software_action(body: ConfirmSoftwareEvent, *, page_id: UUID, page_token: str) -> PendingSoftwareAction:
        async with app.state.maintenance_lock:
            return await _confirm_software_action_locked(body, page_id=page_id, page_token=page_token)

    def start_software_action(pending: PendingSoftwareAction, *, page_id: UUID, page_token: str,
                              workbench) -> PendingSoftwareAction:
        expected_base = pending.confirmation_url.split("/#/", 1)[0]
        if not workbench.ready or workbench.web_url != expected_base:
            raise ApiError(409, "SOFTWARE_ACTION_EXPIRED", "工作台网页地址已变化，请重新查看安装计划。")
        package = get_package(settings, pending.plan.package_id)
        node_changes, definitions, expected_tokens = bundle_definition_plan(pending.plan.package_id, pending.plan.target_version, uninstall=pending.plan.action == "uninstall")
        if get_usage(pending.plan.package_id):
            raise ApiError(409, "SOFTWARE_BUSY", "软件仍有实际调用或未知占用。")
        with app.state.software_action_lock:
            if app.state.software_page_tokens.get(page_id) != page_token:
                raise ApiError(409, "SOFTWARE_ACTION_EXPIRED", "软件确认页面连接已改变。")
            current = app.state.software_actions.get(pending.plan.package_id)
            if current is None or current.operation_id != pending.operation_id or current.state != "awaiting_confirmation":
                raise ApiError(409, "SOFTWARE_ACTION_EXPIRED", "该软件动作已被替换或失效。")
            if app.state.maintenance or app.state.shutdown_started:
                raise ApiError(409, "WORKBENCH_MAINTENANCE", "工作台正在维护，无法确认软件安装。")
            if package.package_token != pending.plan.package_token:
                expired = current.model_copy(update={
                    "state": "expired",
                    "error": ErrorDetail(code="SOFTWARE_ACTION_EXPIRED", message="软件包状态已变化，请重新查看安装计划。", fields=[]),
                })
                app.state.software_actions[pending.plan.package_id] = expired
                raise ApiError(409, "SOFTWARE_ACTION_EXPIRED", "软件包状态已变化，请重新查看安装计划。")
            if node_changes != pending.plan.node_changes:
                expired = current.model_copy(update={
                    "state": "expired",
                    "error": ErrorDetail(code="SOFTWARE_ACTION_EXPIRED", message="配套节点定义已变化，请重新查看安装计划。", fields=[]),
                })
                app.state.software_actions[pending.plan.package_id] = expired
                raise ApiError(409, "SOFTWARE_ACTION_EXPIRED", "配套节点定义已变化，请重新查看安装计划。")
            running = current.model_copy(update={"state": "running"})
            app.state.software_actions[pending.plan.package_id] = running
            task = asyncio.create_task(execute_software_action(running, definitions, expected_tokens))
            app.state.software_tasks[pending.plan.package_id] = task
            return running

    async def _confirm_software_action_locked(body: ConfirmSoftwareEvent, *, page_id: UUID,
                                              page_token: str) -> PendingSoftwareAction:
        with app.state.software_action_lock:
            if app.state.software_page_tokens.get(page_id) != page_token:
                raise ApiError(409, "SOFTWARE_ACTION_EXPIRED", "软件确认页面连接已改变。")
            pending = next((item for item in app.state.software_actions.values() if item.operation_id == body.operation_id), None)
            if pending is None or pending.operation_id != body.operation_id:
                raise ApiError(409, "SOFTWARE_ACTION_EXPIRED", "该软件动作已被替换或失效。")
            if pending.state != "awaiting_confirmation":
                return pending
            if app.state.maintenance or app.state.shutdown_started:
                raise ApiError(409, "WORKBENCH_MAINTENANCE", "工作台正在维护，无法确认软件安装。")
        workbench = await asyncio.to_thread(workbench_status, settings.workspace / "config.toml")
        return start_software_action(pending, page_id=page_id, page_token=page_token, workbench=workbench)

    app.state.request_software_action = request_software_action
    app.state.get_software_package_details = get_software_package_details
    app.state.confirm_software_action = confirm_software_action
    app.state.start_software_action = start_software_action

    @app.post("/internal/maintenance", dependencies=[Depends(authenticate)], include_in_schema=False)
    async def maintenance(body: MaintenanceAction):
        async with app.state.maintenance_lock:
            if app.state.shutdown_started:
                return BusyState(busy=True, unknown=False, blockers=["领域服务正在排空停止"])
            if body.action == "release":
                if app.state.maintenance_owner is None:
                    return BusyState(busy=False, unknown=False, blockers=[])
                if app.state.maintenance_owner != body.operation_id:
                    return BusyState(busy=True, unknown=False, blockers=["维护已归另一控制操作，本次释放未应用"])
                try:
                    set_maintenance(None)
                except (OSError, KeyError, ValueError, ConfigurationError) as exc:
                    return BusyState(busy=True, unknown=True, blockers=[f"维护标记释放失败：{exc}"])
                return BusyState(busy=False, unknown=False, blockers=[])
            if app.state.maintenance_owner not in {None, body.operation_id}:
                return BusyState(busy=True, unknown=False, blockers=["已有其他控制操作正在维护"])
            state = BusyState(busy=False, unknown=False, blockers=[])
            try:
                set_maintenance(body.operation_id)
                state = data_busy(app.state.database)
                active_software = [package_id for package_id, task in app.state.software_tasks.items() if not task.done()]
                active_software.extend(f"{package.package_id}调用 {use.call_id}" for package in list_packages(settings) for use in get_usage(package.package_id))
                active_software.extend(f"Siril准备 {call_id}" for call_id, task in app.state.siril_calls.items() if not task.done())
                if app.state.siril_previews is not None:
                    active_software.extend(f"Siril实时预览 {consumer}" for consumer in app.state.siril_previews.active)
                    if app.state.siril_previews.requests:
                        active_software.append("Siril 实时预览请求尚未结束")
                if active_software:
                    state.busy = True
                    state.blockers.extend(f"软件包动作 {package_id}" for package_id in active_software)
                elif any(package.operation_state == "unknown" for package in list_packages(settings)):
                    state.unknown = True
                    state.blockers.append("无法确认Siril软件动作是否已停止")
                async with httpx.AsyncClient(timeout=3) as client:
                    response = await client.get(settings.allowed_origins[0] + "/queue")
                    response.raise_for_status()
                    queue = response.json()
                    running, pending = queue["queue_running"], queue["queue_pending"]
                    if not isinstance(running, list) or not isinstance(pending, list):
                        raise ValueError("原生队列格式无效。")
                    if running or pending:
                        state.busy = True
                        state.blockers.append("原生队列仍有执行或排队任务")
            except (OSError, httpx.HTTPError, KeyError, TypeError, ValueError, ConfigurationError, SQLAlchemyError) as exc:
                state.unknown = True
                state.blockers.append(f"无法确认工作台空闲：{exc}")
            if state.busy or state.unknown:
                try:
                    set_maintenance(None)
                except (OSError, KeyError, ValueError, ConfigurationError) as exc:
                    state.unknown = True
                    state.blockers.append(f"维护标记释放失败：{exc}")
            return state

    @app.post("/internal/shutdown", dependencies=[Depends(authenticate)], include_in_schema=False)
    async def shutdown(request: Request):
        async with app.state.maintenance_lock:
            app.state.maintenance = True
            app.state.shutdown_started = True
            request.app.state.shutdown()
        return {"status": "stopping"}

    @app.post("/internal/native/page", response_model=NativePageReply, dependencies=[Depends(authenticate)], include_in_schema=False)
    async def receive_native_page(body: NativePageEvent):
        if body.action == "open":
            with app.state.software_action_lock:
                app.state.software_page_tokens[body.page_id] = body.page_token
            return NativePageReply(
                event_id=body.event_id, page_id=body.page_id, page_token=body.page_token, result=None, error=None,
            )
        if body.action == "close":
            with app.state.software_action_lock:
                if app.state.software_page_tokens.get(body.page_id) == body.page_token:
                    app.state.software_page_tokens.pop(body.page_id, None)
            return NativePageReply(
                event_id=body.event_id, page_id=body.page_id, page_token=body.page_token, result=None, error=None,
            )
        with app.state.software_action_lock:
            page_is_current = app.state.software_page_tokens.get(body.page_id) == body.page_token
        if not page_is_current:
            return NativePageReply(
                event_id=body.event_id, page_id=body.page_id, page_token=body.page_token, result=None,
                error=ErrorDetail(code="NATIVE_PAGE_EXPIRED", message="软件确认页面连接已过期。", fields=[]),
            )
        handler = getattr(app.state, "confirm_software_action", None)
        if handler is None:
            return NativePageReply(
                event_id=body.event_id, page_id=body.page_id, page_token=body.page_token, result=None,
                error=ErrorDetail(code="SOFTWARE_ACTION_EXPIRED", message="当前没有待确认的软件动作。", fields=[]),
            )
        try:
            result = await handler(body.payload, page_id=body.page_id, page_token=body.page_token)
        except ApiError as exc:
            return NativePageReply(
                event_id=body.event_id, page_id=body.page_id, page_token=body.page_token, result=None,
                error=ErrorDetail(code=exc.code, message=exc.message, fields=exc.fields),
            )
        return NativePageReply(
            event_id=body.event_id, page_id=body.page_id, page_token=body.page_token, result=result, error=None,
        )

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        try:
            request.state.request_id = UUID(request.headers.get("X-Request-ID", ""))
        except ValueError:
            request.state.request_id = uuid4()
        response = await call_next(request)
        response.headers["X-Request-ID"] = str(request.state.request_id)
        return response

    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError):
        return _error_response(request, exc.status_code, exc.code, exc.message, exc.fields)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        fields = []
        for error in exc.errors():
            path = ".".join(str(part) for part in error.get("loc", ()) if part not in ("body", "query", "path"))
            if error.get("loc", (None,))[0] == "query":
                path = "query." + path
            fields.append({"path": path, "message": "请求字段无效。"})
        return _error_response(request, 422, "VALIDATION_ERROR", "请求数据不符合接口契约。", fields)

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        code = "RESOURCE_NOT_FOUND" if exc.status_code == 404 else "METHOD_NOT_ALLOWED" if exc.status_code == 405 else "INTERNAL_ERROR"
        message = "未找到请求的资源。" if exc.status_code == 404 else "该资源不支持此 HTTP 方法。" if exc.status_code == 405 else "请求失败。"
        return _error_response(request, exc.status_code, code, message, [])

    @app.exception_handler(Exception)
    async def internal_error_handler(request: Request, exc: Exception):
        logger.exception("request failed request_id=%s", getattr(request.state, "request_id", "unknown"))
        return _error_response(request, 500, "INTERNAL_ERROR", "服务发生未预期错误。", [])

    app.include_router(system.router)
    app.include_router(data_router)
    app.include_router(software_router)
    app.include_router(nodes_router)
    return app


def _error_response(request: Request, status_code: int, code: str, message: str, fields: list[dict[str, str]]):
    from fastapi.responses import JSONResponse

    rid = getattr(request.state, "request_id", uuid4())
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message, "fields": fields}, "request_id": str(rid)}, headers={"X-Request-ID": str(rid)})
