from __future__ import annotations
from fastapi import APIRouter

from astrophotoflow.core.http import ERROR_RESPONSES
from astrophotoflow.core.http import authenticate

from fastapi import Depends, Request
from sqlalchemy.exc import SQLAlchemyError
from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.database.schema import SCHEMA_REVISION, current_revision


router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)


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
