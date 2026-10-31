from __future__ import annotations
from fastapi import APIRouter

from astrophotoflow.core.http import ERROR_RESPONSES
from astrophotoflow.core.http import authenticate

from fastapi import Depends, Request
from sqlalchemy.exc import SQLAlchemyError
from pathlib import Path
from uuid import UUID
import psutil
import subprocess
from astrophotoflow.core.workbench import request_restart, restart_result, WorkbenchError
from astrophotoflow.contracts.workbench import ConfigSave, ConfigState, WorkbenchResult, RestartRequest, DirectorySelectionRequest, DirectorySelectionResult
from astrophotoflow.core.config import ConfigurationError, get_configuration, save_configuration, select_directory
from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.localization import workspace_locale
from astrophotoflow.contracts.localization import WorkspaceLocale
from astrophotoflow.core.database.schema import SCHEMA_REVISION, current_revision


router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)


@router.get('/settings/locale', dependencies=[Depends(authenticate)])
def get_workspace_locale(request: Request) -> WorkspaceLocale:
    try:
        return WorkspaceLocale(locale=workspace_locale(request.app.state.settings.workspace))
    except ConfigurationError as exc:
        raise ApiError(503, 'LOCALE_UNAVAILABLE', '无法读取工作台语言设置。', message_key='locale_unavailable') from exc


@router.get("/settings/workbench", response_model=ConfigState, dependencies=[Depends(authenticate)])
def get_workbench_configuration(request: Request):
    try:
        return get_configuration(request.app.state.settings.workspace / "config.toml")
    except (OSError, ConfigurationError) as exc:
        raise ApiError(503, "CONFIGURATION_UNAVAILABLE", "无法读取工作台配置，请检查配置文件。", message_key='cannot_read_the_workbench_configuration_check_the_configuration_file') from exc


@router.patch("/settings/workbench", response_model=ConfigState, dependencies=[Depends(authenticate)])
def save_workbench_configuration(body: ConfigSave, request: Request):
    try:
        return save_configuration(
            request.app.state.settings.workspace / "config.toml", body.values, body.config_token,
            default_workspace=Path(body.default_workspace) if body.default_workspace is not None else None,
        )
    except (OSError, ConfigurationError) as exc:
        raise ApiError(503, "CONFIGURATION_SAVE_FAILED", "无法保存工作台配置，请重新读取并检查文件权限。", message_key='cannot_save_the_workbench_configuration_read_it_again_and_check_file_permis') from exc


@router.post("/settings/workbench/restart", response_model=WorkbenchResult, status_code=202, dependencies=[Depends(authenticate)])
def restart_workbench(body: RestartRequest, request: Request):
    try:
        return request_restart(request.app.state.settings.workspace / "config.toml", body.operation_id)
    except WorkbenchError as exc:
        raise ApiError(409, 'WORKBENCH_CONTROL_BUSY', str(exc), message_key='workbench_control_busy', fields=[{'path': 'diagnostic', 'message': str(exc)}]) from exc
    except (OSError, ConfigurationError, psutil.Error) as exc:
        raise ApiError(503, 'WORKBENCH_RESTART_FAILED', str(exc), message_key='workbench_restart_failed', fields=[{'path': 'diagnostic', 'message': str(exc)}]) from exc


@router.get("/settings/workbench/restart/{operation_id}", response_model=WorkbenchResult | None, dependencies=[Depends(authenticate)])
def get_workbench_restart(operation_id: UUID, request: Request):
    return restart_result(request.app.state.settings.workspace / "config.toml", operation_id)


@router.post("/settings/workbench/select-directory", response_model=DirectorySelectionResult, dependencies=[Depends(authenticate)])
def select_workbench_directory(body: DirectorySelectionRequest, request: Request):
    path = Path(body.path).expanduser()
    if not path.is_absolute():
        path = request.app.state.settings.workspace / path
    try:
        selected = select_directory(path.resolve())
    except (OSError, ConfigurationError, subprocess.CalledProcessError) as exc:
        raise ApiError(503, "DIRECTORY_PICKER_UNAVAILABLE", "无法打开系统文件夹选择窗口。请检查本机桌面会话或直接填写路径。", message_key='cannot_open_the_system_folder_picker_check_the_local_desktop_session_or_ent') from exc
    return DirectorySelectionResult(path=str(selected) if selected is not None else None)


@router.get("/health", dependencies=[Depends(authenticate)])
def health(request: Request):
    path = request.app.state.settings.database_path
    if current_revision(path) != SCHEMA_REVISION:
        raise ApiError(503, "SERVICE_UNAVAILABLE", "领域服务数据库未就绪。", message_key='the_domain_service_database_is_not_ready')
    try:
        with request.app.state.database.engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
    except SQLAlchemyError as exc:
        raise ApiError(503, "SERVICE_UNAVAILABLE", "领域服务数据库未就绪。", message_key='the_domain_service_database_is_not_ready') from exc
    return {"status": "ok", "api_version": "v1", "database": "ready", "schema_revision": SCHEMA_REVISION,
            "workspace": str(request.app.state.settings.workspace)}


@router.get("/capabilities", dependencies=[Depends(authenticate)])
def capabilities():
    return {
        "stage": "ingestion", "shared_library_read": True, "project_assets_read": True,
        "project_management": True, "equipment_management": True,
        "asset_import": True, "asset_reference_write": True, "asset_preview": True,
        "asset_metadata_edit": True, "dataset_management": True, "asset_task_management": True,
        "calibration_matching": False, "asset_publish": False,
    }
