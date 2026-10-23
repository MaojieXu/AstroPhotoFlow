from datetime import datetime, timezone
import hmac
import logging
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from .db import Database
from .errors import ApiError, invalid_reference, not_found
from .models import (
    Asset, AssetTask, AssetTaskItem, AssetVersion, CaptureProfile, Dataset, DatasetMember,
    DatasetVersion, Equipment, FitsHduMetadata, Preview, Project, ProjectAssetReference,
    ProjectCaptureProfile, ProjectDatasetReference,
)
from .schema import SCHEMA_REVISION, current_revision
from .schemas import (
    AssetOut, AssetPage, AssetVersionOut, CaptureProfileCreate, CaptureProfileOut,
    CaptureProfilePage, CaptureProfilePatch, EquipmentCreate, EquipmentOut, EquipmentPage,
    EquipmentPatch, ErrorEnvelope, ProjectAssetReferenceOut, ProjectAssetReferencePage,
    ProjectCreate, ProjectOut, ProjectPage, ProjectPatch,
    AssetTaskOut, AssetTaskPage, AssetVersionPage, DatasetOut, DatasetPage, DatasetVersionOut,
    DatasetVersionPage, FitsHeaderOut, FitsHduOut, FitsHduPage, ImportAccepted, ImportRootEntryPage,
    ImportRootOut, ProjectDatasetReferenceOut, ProjectDatasetReferencePage,
)
from .settings import Settings
from .files import entries_page
from .import_schemas import (
    AssetClassification, AssetParameters, AssetPatch, DatasetPatch,
    ProjectDatasetReferenceCreate, ProjectReferenceCreate, ProjectReferenceDelete,
    RetryCreate, ImportCreate,
)
from .fits_preview import create_preview, PREVIEW_ALGORITHM_VERSION


logger = logging.getLogger("astrophotoflow.service")
bearer = HTTPBearer(auto_error=False)
ERROR_RESPONSES = {
    status: {"model": ErrorEnvelope, "description": description}
    for status, description in {
        401: "Authentication required",
        403: "Origin not allowed by the ComfyUI proxy",
        404: "Resource not found or outside the requested scope",
        405: "Method not allowed",
        409: "Revision conflict",
        422: "Validation error or invalid reference",
        503: "Service not configured or unavailable",
        504: "Service timeout",
        500: "Internal error",
    }.items()
}
router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)




async def authenticate(request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> None:
    expected = request.app.state.token
    if credentials is None or credentials.scheme.lower() != "bearer" or not hmac.compare_digest(credentials.credentials, expected):
        raise ApiError(401, "AUTHENTICATION_REQUIRED", "需要有效的本机服务令牌。")


def read_session(request: Request):
    with request.app.state.database.read_session() as session:
        yield session


def write_session(request: Request):
    with request.app.state.database.write_session() as session:
        yield session


ReadSession = Annotated[Session, Depends(read_session)]
WriteSession = Annotated[Session, Depends(write_session, scope="function")]
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]
SortBy = Annotated[Literal["created_at", "name"], Query()]
Order = Annotated[Literal["asc", "desc"], Query()]
StatusFilter = Annotated[Literal["active", "archived", "all"], Query()]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _id(value: UUID | str) -> str:
    return str(value)


def _uuid(value: str | None) -> UUID | None:
    return UUID(value) if value is not None else None


def _page(items, total: int, limit: int, offset: int) -> dict:
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def _order(column, order: str):
    return column.desc() if order == "desc" else column.asc()


def _status_clause(model, status: str):
    return None if status == "all" else model.status == status


def _check_names(values: list[UUID]) -> list[str]:
    ids = [str(value) for value in values]
    if len(ids) != len(set(ids)):
        raise ApiError(422, "VALIDATION_ERROR", "关联 ID 不能重复。", [{"path": "capture_profile_ids", "message": "关联 ID 不能重复。"}])
    return ids


def _check_profile_refs(session: Session, ids: list[str]) -> None:
    if ids and len(session.scalars(select(CaptureProfile.id).where(CaptureProfile.id.in_(ids))).all()) != len(ids):
        raise invalid_reference("一个或多个拍摄配置不存在。")


def _check_equipment_ref(session: Session, value: str | None, kind: str, path: str) -> None:
    if value is None:
        return
    equipment = session.get(Equipment, value)
    if equipment is None or equipment.kind != kind:
        raise invalid_reference(f"{path} 必须引用现存的 {kind} 设备。")


def _check_profile_equipment(session: Session, camera_id: str, optical_id: str | None, filter_id: str | None) -> None:
    _check_equipment_ref(session, camera_id, "camera", "camera_id")
    _check_equipment_ref(session, optical_id, "optical_system", "optical_system_id")
    _check_equipment_ref(session, filter_id, "filter", "filter_id")


def _project_out(session: Session, row: Project) -> dict:
    ids = session.scalars(
        select(ProjectCaptureProfile.capture_profile_id)
        .where(ProjectCaptureProfile.project_id == row.id)
        .order_by(ProjectCaptureProfile.capture_profile_id)
    ).all()
    return ProjectOut(
        id=UUID(row.id), name=row.name, target_name=row.target_name, notes=row.notes,
        capture_profile_ids=[UUID(value) for value in ids], status=row.status, revision=row.revision,
        created_at=_utc(row.created_at), updated_at=_utc(row.updated_at),
    ).model_dump()


def _equipment_out(row: Equipment) -> dict:
    return EquipmentOut(
        id=UUID(row.id), kind=row.kind, name=row.name, model=row.model, serial_number=row.serial_number,
        notes=row.notes, specs=row.specs, status=row.status, revision=row.revision,
        created_at=_utc(row.created_at), updated_at=_utc(row.updated_at),
    ).model_dump()


def _profile_out(row: CaptureProfile) -> dict:
    return CaptureProfileOut(
        id=UUID(row.id), name=row.name, camera_id=UUID(row.camera_id),
        optical_system_id=_uuid(row.optical_system_id), filter_id=_uuid(row.filter_id),
        frame_type=row.frame_type, parameter_mode=row.parameter_mode, iso=row.iso,
        exposure_seconds=row.exposure_seconds, gain=row.gain, offset=row.offset,
        sensor_temperature_c=row.sensor_temperature_c, binning_x=row.binning_x, binning_y=row.binning_y,
        notes=row.notes, status=row.status, revision=row.revision, created_at=_utc(row.created_at), updated_at=_utc(row.updated_at),
    ).model_dump()


def _version_out(row: AssetVersion) -> dict:
    return AssetVersionOut(
        id=UUID(row.id), asset_id=UUID(row.asset_id), version_number=row.version_number,
        storage_mode=row.storage_mode, storage_location=row.storage_location, byte_size=row.byte_size,
        content_hash=row.content_hash, availability=row.availability, camera_id=_uuid(row.camera_id),
        optical_system_id=_uuid(row.optical_system_id), filter_id=_uuid(row.filter_id),
        capture_profile_id=_uuid(row.capture_profile_id), frame_type=row.frame_type,
        calibration_level=row.calibration_level, capture_snapshot=row.capture_snapshot,
        scientific_metadata=row.scientific_metadata, created_at=_utc(row.created_at),
    ).model_dump()


def _current_calibration_level(classification: dict | None, role: str) -> str | None:
    if role != "calibration" or not classification:
        return None
    if classification.get("frame_class") == "masterframe":
        return "master"
    if classification.get("frame_class") == "subframe":
        return "individual"
    return None


def _asset_out(session: Session, row: Asset) -> dict:
    version = None
    if row.current_version_id is not None:
        version_row = session.get(AssetVersion, row.current_version_id)
        if version_row is None or version_row.asset_id != row.id:
            raise RuntimeError("资产当前版本引用不属于该资产。")
        version = _version_out(version_row)
    return AssetOut(
        id=UUID(row.id), name=row.name, scope=row.scope, owner_project_id=_uuid(row.owner_project_id),
        role=row.role, current_version_id=_uuid(row.current_version_id), created_at=_utc(row.created_at),
        classification=row.classification, parameters=row.parameters or {}, value_sources=row.value_sources or {},
        notes=row.notes, status=row.status, revision=row.revision,
        calibration_level=_current_calibration_level(row.classification, row.role),
        current_version=version,
    ).model_dump()


def _reference_out(session: Session, ref: ProjectAssetReference, asset: Asset, version: AssetVersion) -> dict:
    return ProjectAssetReferenceOut(
        id=UUID(ref.id), project_id=UUID(ref.project_id), asset_version_id=UUID(ref.asset_version_id),
        added_at=_utc(ref.added_at), asset=_asset_out(session, asset), version=_version_out(version),
    ).model_dump()


def _conflict_or_missing(session: Session, model, record_id: str) -> None:
    if session.get(model, record_id) is None:
        raise not_found()
    raise ApiError(409, "REVISION_CONFLICT", "配置已被其他窗口修改，请重新读取后保存。")


def _assert_patch_values(changes: dict, non_nullable: set[str], path_prefix: str = "") -> None:
    fields = [{"path": f"{path_prefix}{key}", "message": "此字段不能为 null。"} for key in non_nullable if key in changes and changes[key] is None]
    if fields:
        raise ApiError(422, "VALIDATION_ERROR", "请求字段无效。", fields)


def _update_config(session: Session, model, record_id: str, base_revision: int, changes: dict) -> None:
    now = _now()
    result = session.execute(
        update(model).where(model.id == record_id, model.revision == base_revision)
        .values(**changes, revision=base_revision + 1, updated_at=now)
    )
    if result.rowcount != 1:
        _conflict_or_missing(session, model, record_id)


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
    return {"status": "ok", "api_version": "v1", "database": "ready", "schema_revision": SCHEMA_REVISION}


@router.get("/capabilities", dependencies=[Depends(authenticate)])
def capabilities():
    return {
        "stage": "ingestion", "shared_library_read": True, "project_assets_read": True,
        "project_management": True, "equipment_management": True, "capture_profile_management": True,
        "asset_import": True, "asset_reference_write": True, "asset_preview": True,
        "asset_metadata_edit": True, "dataset_management": True, "asset_task_management": True,
        "calibration_matching": False, "asset_publish": False,
    }


@router.get("/projects", response_model=ProjectPage, dependencies=[Depends(authenticate)])
def list_projects(
    session: ReadSession, limit: Limit = 50, offset: Offset = 0,
    sort_by: SortBy = "created_at", order: Order = "desc", q: str | None = None,
    status: StatusFilter = "active",
):
    filters = []
    status_clause = _status_clause(Project, status)
    if status_clause is not None:
        filters.append(status_clause)
    if q:
        filters.append(Project.name.contains(q, autoescape=True))
    total = session.scalar(select(func.count()).select_from(Project).where(*filters)) or 0
    column = Project.name if sort_by == "name" else Project.created_at
    rows = session.scalars(select(Project).where(*filters).order_by(_order(column, order), Project.id.asc()).limit(limit).offset(offset)).all()
    return _page([_project_out(session, row) for row in rows], total, limit, offset)


@router.post("/projects", response_model=ProjectOut, status_code=201, dependencies=[Depends(authenticate)])
def create_project(body: ProjectCreate, session: WriteSession):
    profile_ids = _check_names(body.capture_profile_ids)
    _check_profile_refs(session, profile_ids)
    now = _now()
    row = Project(id=str(uuid4()), name=body.name, target_name=body.target_name, notes=body.notes,
                  status="active", revision=1, created_at=now, updated_at=now)
    session.add(row)
    for profile_id in profile_ids:
        session.add(ProjectCaptureProfile(project_id=row.id, capture_profile_id=profile_id))
    session.flush()
    return _project_out(session, row)


@router.get("/projects/{project_id}", response_model=ProjectOut, dependencies=[Depends(authenticate)])
def get_project(project_id: UUID, session: ReadSession):
    row = session.get(Project, _id(project_id))
    if row is None:
        raise not_found()
    return _project_out(session, row)


@router.patch("/projects/{project_id}", response_model=ProjectOut, dependencies=[Depends(authenticate)])
def patch_project(project_id: UUID, body: ProjectPatch, session: WriteSession):
    row_id = _id(project_id)
    changes = body.model_dump(exclude_unset=True, exclude={"base_revision", "capture_profile_ids"})
    _assert_patch_values(changes, {"name", "status"})
    profile_ids = None
    if "capture_profile_ids" in body.model_fields_set:
        if body.capture_profile_ids is None:
            raise ApiError(422, "VALIDATION_ERROR", "capture_profile_ids 不能为 null。", [{"path": "capture_profile_ids", "message": "请提供数组。"}])
        profile_ids = _check_names(body.capture_profile_ids)
        _check_profile_refs(session, profile_ids)
    if changes:
        _update_config(session, Project, row_id, body.base_revision, changes)
    elif session.get(Project, row_id) is None:
        raise not_found()
    elif session.get(Project, row_id).revision != body.base_revision:
        raise ApiError(409, "REVISION_CONFLICT", "配置已被其他窗口修改，请重新读取后保存。")
    else:
        _update_config(session, Project, row_id, body.base_revision, {})
    if profile_ids is not None:
        session.query(ProjectCaptureProfile).filter_by(project_id=row_id).delete(synchronize_session=False)
        session.add_all(ProjectCaptureProfile(project_id=row_id, capture_profile_id=value) for value in profile_ids)
    session.flush()
    session.expire_all()
    return _project_out(session, session.get(Project, row_id))


@router.get("/equipment", response_model=EquipmentPage, dependencies=[Depends(authenticate)])
def list_equipment(
    session: ReadSession, limit: Limit = 50, offset: Offset = 0,
    sort_by: SortBy = "created_at", order: Order = "desc", q: str | None = None,
    status: StatusFilter = "active", kind: Literal["camera", "optical_system", "filter"] | None = None,
):
    filters = []
    status_clause = _status_clause(Equipment, status)
    if status_clause is not None:
        filters.append(status_clause)
    if kind:
        filters.append(Equipment.kind == kind)
    if q:
        filters.append(or_(Equipment.name.contains(q, autoescape=True), Equipment.model.contains(q, autoescape=True)))
    total = session.scalar(select(func.count()).select_from(Equipment).where(*filters)) or 0
    column = Equipment.name if sort_by == "name" else Equipment.created_at
    rows = session.scalars(select(Equipment).where(*filters).order_by(_order(column, order), Equipment.id.asc()).limit(limit).offset(offset)).all()
    return _page([_equipment_out(row) for row in rows], total, limit, offset)


@router.post("/equipment", response_model=EquipmentOut, status_code=201, dependencies=[Depends(authenticate)])
def create_equipment(body: EquipmentCreate, session: WriteSession):
    now = _now()
    row = Equipment(
        id=str(uuid4()), kind=body.kind, name=body.name, model=body.model, serial_number=body.serial_number,
        notes=body.notes, specs=body.specs.model_dump(mode="json"), status="active", revision=1,
        created_at=now, updated_at=now,
    )
    session.add(row)
    session.flush()
    return _equipment_out(row)


@router.get("/equipment/{equipment_id}", response_model=EquipmentOut, dependencies=[Depends(authenticate)])
def get_equipment(equipment_id: UUID, session: ReadSession):
    row = session.get(Equipment, _id(equipment_id))
    if row is None:
        raise not_found()
    return _equipment_out(row)


@router.patch("/equipment/{equipment_id}", response_model=EquipmentOut, dependencies=[Depends(authenticate)])
def patch_equipment(equipment_id: UUID, body: EquipmentPatch, session: WriteSession):
    row_id = _id(equipment_id)
    row = session.get(Equipment, row_id)
    if row is None:
        raise not_found()
    if body.kind != row.kind:
        raise ApiError(422, "VALIDATION_ERROR", "設備 kind 创建后不能修改。", [{"path": "kind", "message": "必须与现有设备类型一致。"}])
    changes = body.model_dump(exclude_unset=True, exclude={"base_revision", "kind", "specs"})
    _assert_patch_values(changes, {"name", "status"})
    if "specs" in body.model_fields_set:
        if body.specs is None:
            raise ApiError(422, "VALIDATION_ERROR", "specs 不能为 null。", [{"path": "specs", "message": "请提供类型化参数对象。"}])
        changes["specs"] = {**row.specs, **body.specs.model_dump(exclude_unset=True)}
    _update_config(session, Equipment, row_id, body.base_revision, changes)
    session.flush()
    session.expire_all()
    return _equipment_out(session.get(Equipment, row_id))


@router.get("/capture-profiles", response_model=CaptureProfilePage, dependencies=[Depends(authenticate)])
def list_capture_profiles(
    session: ReadSession, limit: Limit = 50, offset: Offset = 0,
    sort_by: SortBy = "created_at", order: Order = "desc", q: str | None = None,
    status: StatusFilter = "active", camera_id: UUID | None = None, optical_system_id: UUID | None = None,
    filter_id: UUID | None = None, frame_type: Literal["light", "bias", "dark", "flat", "dark_flat"] | None = None,
):
    filters = []
    status_clause = _status_clause(CaptureProfile, status)
    if status_clause is not None:
        filters.append(status_clause)
    for column, value in ((CaptureProfile.camera_id, camera_id), (CaptureProfile.optical_system_id, optical_system_id), (CaptureProfile.filter_id, filter_id), (CaptureProfile.frame_type, frame_type)):
        if value is not None:
            filters.append(column == _id(value) if isinstance(value, UUID) else column == value)
    if q:
        filters.append(CaptureProfile.name.contains(q, autoescape=True))
    total = session.scalar(select(func.count()).select_from(CaptureProfile).where(*filters)) or 0
    column = CaptureProfile.name if sort_by == "name" else CaptureProfile.created_at
    rows = session.scalars(select(CaptureProfile).where(*filters).order_by(_order(column, order), CaptureProfile.id.asc()).limit(limit).offset(offset)).all()
    return _page([_profile_out(row) for row in rows], total, limit, offset)


@router.post("/capture-profiles", response_model=CaptureProfileOut, status_code=201, dependencies=[Depends(authenticate)])
def create_capture_profile(body: CaptureProfileCreate, session: WriteSession):
    camera_id, optical_id, filter_id = _id(body.camera_id), _id(body.optical_system_id) if body.optical_system_id else None, _id(body.filter_id) if body.filter_id else None
    _check_profile_equipment(session, camera_id, optical_id, filter_id)
    now = _now()
    row = CaptureProfile(
        id=str(uuid4()), name=body.name, camera_id=camera_id, optical_system_id=optical_id, filter_id=filter_id,
        frame_type=body.frame_type, parameter_mode=body.parameter_mode, iso=body.iso,
        exposure_seconds=body.exposure_seconds, gain=body.gain, offset=body.offset,
        sensor_temperature_c=body.sensor_temperature_c, binning_x=body.binning_x, binning_y=body.binning_y,
        notes=body.notes, status="active", revision=1, created_at=now, updated_at=now,
    )
    session.add(row)
    session.flush()
    return _profile_out(row)


@router.get("/capture-profiles/{profile_id}", response_model=CaptureProfileOut, dependencies=[Depends(authenticate)])
def get_capture_profile(profile_id: UUID, session: ReadSession):
    row = session.get(CaptureProfile, _id(profile_id))
    if row is None:
        raise not_found()
    return _profile_out(row)


@router.patch("/capture-profiles/{profile_id}", response_model=CaptureProfileOut, dependencies=[Depends(authenticate)])
def patch_capture_profile(profile_id: UUID, body: CaptureProfilePatch, session: WriteSession):
    row_id = _id(profile_id)
    row = session.get(CaptureProfile, row_id)
    if row is None:
        raise not_found()
    changes = body.model_dump(exclude_unset=True, exclude={"base_revision"})
    _assert_patch_values(changes, {"name", "camera_id", "frame_type", "status"})
    for key in ("camera_id", "optical_system_id", "filter_id"):
        if key in changes and changes[key] is not None:
            changes[key] = _id(changes[key])
    camera_id = changes.get("camera_id", row.camera_id)
    optical_id = changes.get("optical_system_id", row.optical_system_id)
    filter_id = changes.get("filter_id", row.filter_id)
    _check_profile_equipment(session, camera_id, optical_id, filter_id)
    _update_config(session, CaptureProfile, row_id, body.base_revision, changes)
    session.flush()
    session.expire_all()
    return _profile_out(session.get(CaptureProfile, row_id))


def _asset_page(session: Session, params: dict, limit: int, offset: int, sort_by: str, order: str, include_project_private: str | None = None):
    asset_version_join = and_(AssetVersion.id == Asset.current_version_id, AssetVersion.asset_id == Asset.id)
    if include_project_private is None:
        scope = Asset.scope == "shared"
    else:
        scope = or_(Asset.scope == "shared", and_(Asset.scope == "project", Asset.owner_project_id == include_project_private))
    filters = [scope]
    if params.get("q"):
        filters.append(Asset.name.contains(params["q"], autoescape=True))
    if params.get("status") not in (None, "all"):
        filters.append(Asset.status == params["status"])
    if params.get("role"):
        filters.append(Asset.role == params["role"])
    for key in ("frame_type", "camera_id", "optical_system_id", "filter_id"):
        value = params.get(key)
        if value is not None:
            column = Asset.classification["frame_type"].as_string() if key == "frame_type" else Asset.parameters[key].as_string()
            filters.append(column == (_id(value) if isinstance(value, UUID) else value))
    if params.get("calibration_level") is not None:
        frame_class = "masterframe" if params["calibration_level"] == "master" else "subframe"
        filters.extend((Asset.role == "calibration", Asset.classification["frame_class"].as_string() == frame_class))
    stmt = select(Asset).outerjoin(AssetVersion, asset_version_join).where(*filters)
    total = session.scalar(select(func.count()).select_from(Asset).outerjoin(AssetVersion, asset_version_join).where(*filters)) or 0
    column = Asset.name if sort_by == "name" else Asset.created_at
    rows = session.scalars(stmt.order_by(_order(column, order), Asset.id.asc()).limit(limit).offset(offset)).all()
    return _page([_asset_out(session, row) for row in rows], total, limit, offset)


@router.get("/library/assets", response_model=AssetPage, dependencies=[Depends(authenticate)])
def list_library_assets(
    session: ReadSession, limit: Limit = 50, offset: Offset = 0,
    sort_by: SortBy = "created_at", order: Order = "desc", q: str | None = None,
    role: Literal["raw", "calibration", "intermediate", "final"] | None = None,
    status: Literal["active", "archived", "all"] = "active",
    frame_type: Literal["light", "bias", "dark", "flat", "dark_flat"] | None = None,
    calibration_level: Literal["individual", "master"] | None = None,
    camera_id: UUID | None = None, optical_system_id: UUID | None = None, filter_id: UUID | None = None,
):
    params = locals()
    return _asset_page(session, params, limit, offset, sort_by, order)


@router.get("/library/assets/{asset_id}", response_model=AssetOut, dependencies=[Depends(authenticate)])
def get_library_asset(asset_id: UUID, session: ReadSession):
    row = session.get(Asset, _id(asset_id))
    if row is None or row.scope != "shared":
        raise not_found()
    return _asset_out(session, row)


def _project_reference_filters(project_id: str, params: dict):
    scope = or_(Asset.scope == "shared", and_(Asset.scope == "project", Asset.owner_project_id == project_id))
    filters = [ProjectAssetReference.project_id == project_id, scope]
    if params.get("q"):
        filters.append(Asset.name.contains(params["q"], autoescape=True))
    if params.get("role"):
        filters.append(Asset.role == params["role"])
    for key in ("frame_type", "camera_id", "optical_system_id", "filter_id"):
        value = params.get(key)
        if value is not None:
            column = Asset.classification["frame_type"].as_string() if key == "frame_type" else Asset.parameters[key].as_string()
            filters.append(column == (_id(value) if isinstance(value, UUID) else value))
    if params.get("calibration_level") is not None:
        frame_class = "masterframe" if params["calibration_level"] == "master" else "subframe"
        filters.extend((Asset.role == "calibration", Asset.classification["frame_class"].as_string() == frame_class))
    return filters


@router.get("/projects/{project_id}/assets", response_model=ProjectAssetReferencePage, dependencies=[Depends(authenticate)])
def list_project_assets(
    project_id: UUID, session: ReadSession, limit: Limit = 50, offset: Offset = 0,
    sort_by: SortBy = "created_at", order: Order = "desc", q: str | None = None,
    role: Literal["raw", "calibration", "intermediate", "final"] | None = None,
    frame_type: Literal["light", "bias", "dark", "flat", "dark_flat"] | None = None,
    calibration_level: Literal["individual", "master"] | None = None,
    camera_id: UUID | None = None, optical_system_id: UUID | None = None, filter_id: UUID | None = None,
):
    project_key = _id(project_id)
    if session.get(Project, project_key) is None:
        raise not_found()
    params = locals()
    filters = _project_reference_filters(project_key, params)
    stmt = select(ProjectAssetReference, Asset, AssetVersion).join(AssetVersion, AssetVersion.id == ProjectAssetReference.asset_version_id).join(Asset, Asset.id == AssetVersion.asset_id).where(*filters)
    total = session.scalar(select(func.count()).select_from(ProjectAssetReference).join(AssetVersion, AssetVersion.id == ProjectAssetReference.asset_version_id).join(Asset, Asset.id == AssetVersion.asset_id).where(*filters)) or 0
    column = Asset.name if sort_by == "name" else Asset.created_at
    rows = session.execute(stmt.order_by(_order(column, order), ProjectAssetReference.id.asc()).limit(limit).offset(offset)).all()
    return _page([_reference_out(session, ref, asset, version) for ref, asset, version in rows], total, limit, offset)


@router.get("/projects/{project_id}/asset-references/{reference_id}", response_model=ProjectAssetReferenceOut, dependencies=[Depends(authenticate)])
def get_project_asset_reference(project_id: UUID, reference_id: UUID, session: ReadSession):
    project_key = _id(project_id)
    if session.get(Project, project_key) is None:
        raise not_found()
    row = session.execute(
        select(ProjectAssetReference, Asset, AssetVersion)
        .join(AssetVersion, AssetVersion.id == ProjectAssetReference.asset_version_id)
        .join(Asset, Asset.id == AssetVersion.asset_id)
        .where(ProjectAssetReference.id == _id(reference_id), ProjectAssetReference.project_id == project_key,
               or_(Asset.scope == "shared", and_(Asset.scope == "project", Asset.owner_project_id == project_key)))
    ).first()
    if row is None:
        raise not_found()
    return _reference_out(session, *row)


def create_app(settings: Settings, token: str) -> FastAPI:
    app = FastAPI(title="AstroPhotoFlow Asset Service", version="1.0.0", docs_url=None, redoc_url=None)
    app.state.settings = settings
    app.state.token = token
    app.state.database = Database(settings.database_path)

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

    app.include_router(router)
    from .stage2 import router as stage2_router

    app.include_router(stage2_router)
    return app


def _error_response(request: Request, status_code: int, code: str, message: str, fields: list[dict[str, str]]):
    from fastapi.responses import JSONResponse

    rid = getattr(request.state, "request_id", uuid4())
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message, "fields": fields}, "request_id": str(rid)}, headers={"X-Request-ID": str(rid)})
