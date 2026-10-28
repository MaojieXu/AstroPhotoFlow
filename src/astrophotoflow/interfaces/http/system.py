from __future__ import annotations
from fastapi import APIRouter

from astrophotoflow.core.http import ERROR_RESPONSES
from astrophotoflow.core.http import authenticate

from fastapi import Depends, Request
from sqlalchemy.exc import SQLAlchemyError
from pathlib import Path
from astrophotoflow.contracts.workbench import ConfigSave, ConfigState
from astrophotoflow.core.config import ConfigurationError, get_configuration, save_configuration
from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.database.schema import SCHEMA_REVISION, current_revision


router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)


@router.get("/settings/workbench", response_model=ConfigState, dependencies=[Depends(authenticate)])
def get_workbench_configuration(request: Request):
    try:
        return get_configuration(request.app.state.settings.workspace / "config.toml")
    except (OSError, ConfigurationError) as exc:
        raise ApiError(503, "CONFIGURATION_UNAVAILABLE", "无法读取工作台配置，请检查配置文件。") from exc


@router.patch("/settings/workbench", response_model=ConfigState, dependencies=[Depends(authenticate)])
def save_workbench_configuration(body: ConfigSave, request: Request):
    try:
        return save_configuration(
            request.app.state.settings.workspace / "config.toml", body.values, body.config_token,
            default_workspace=Path(body.default_workspace) if body.default_workspace is not None else None,
        )
    except (OSError, ConfigurationError) as exc:
        raise ApiError(503, "CONFIGURATION_SAVE_FAILED", "无法保存工作台配置，请重新读取并检查文件权限。") from exc


@router.get("/health", dependencies=[Depends(authenticate)])
def health(request: Request):
    path = request.app.state.settings.database_path
    if current_revision(path) != SCHEMA_REVISION:
        raise ApiError(503, "SERVICE_UNAVAILABLE", "领域服务数据库未就绪。")
    try:
        with request.app.state.database.engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")
    except SQLAlchemyError as exc:
        raise ApiError(503, "SERVICE_UNAVAILABLE", "领域服务数据库未就绪。") from exc
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
