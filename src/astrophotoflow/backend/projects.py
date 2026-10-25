from __future__ import annotations
from fastapi import APIRouter

from .dependencies import ERROR_RESPONSES
from .dependencies import Limit, Offset, Order, ReadSession, SortBy, StatusFilter, WriteSession, authenticate
from .common import _assert_patch_values, _asset_version_scope, _dataset_reference_out, _fits_hdu_out, _header_out, _id, _now, _order, _page, _project_out, _read_preview, _reference_out, _status_clause, _update_config
from . import dependencies as deps
from . import common as shared

from typing import Literal
from uuid import UUID, uuid4
from fastapi import Depends, Request
from sqlalchemy import and_, func, or_, select, update
from .errors import ApiError, invalid_reference, not_found
from .models import Asset, AssetVersion, Dataset, DatasetVersion, FitsHduMetadata, Project, ProjectAssetReference, ProjectDatasetReference
from .schemas import ProjectAssetReferenceOut, ProjectAssetReferencePage, ProjectCreate, ProjectOut, ProjectPage, ProjectPatch, FitsHeaderOut, FitsHduPage, ProjectDatasetReferenceOut, ProjectDatasetReferencePage
from .import_schemas import ProjectDatasetReferenceCreate, ProjectReferenceCreate, ProjectReferenceDelete


router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)


@router.get("/projects", response_model=ProjectPage, dependencies=[Depends(authenticate)])
def list_projects(
    session: ReadSession, limit: Limit = 50, offset: Offset = 0,
    sort_by: SortBy = "created_at", order: Order = "desc", q: str | None = None,
    status: StatusFilter = "active", target_name: str | None = None,
):
    filters = []
    status_clause = _status_clause(Project, status)
    if status_clause is not None:
        filters.append(status_clause)
    if q:
        filters.append(Project.name.contains(q, autoescape=True))
    if target_name:
        filters.append(Project.target_name.contains(target_name, autoescape=True))
    total = session.scalar(select(func.count()).select_from(Project).where(*filters)) or 0
    column = Project.name if sort_by == "name" else Project.created_at
    rows = session.scalars(select(Project).where(*filters).order_by(_order(column, order), Project.id.asc()).limit(limit).offset(offset)).all()
    return _page([_project_out(session, row) for row in rows], total, limit, offset)


@router.post("/projects", response_model=ProjectOut, status_code=201, dependencies=[Depends(authenticate)])
def create_project(body: ProjectCreate, session: WriteSession):
    now = _now()
    row = Project(id=str(uuid4()), name=body.name, target_name=body.target_name, notes=body.notes,
                  status="active", revision=1, created_at=now, updated_at=now)
    session.add(row)
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
    changes = body.model_dump(exclude_unset=True, exclude={"base_revision"})
    _assert_patch_values(changes, {"name", "status"})
    if changes:
        _update_config(session, Project, row_id, body.base_revision, changes)
    elif session.get(Project, row_id) is None:
        raise not_found()
    elif session.get(Project, row_id).revision != body.base_revision:
        raise ApiError(409, "REVISION_CONFLICT", "配置已被其他窗口修改，请重新读取后保存。")
    else:
        _update_config(session, Project, row_id, body.base_revision, {})
    session.flush()
    session.expire_all()
    return _project_out(session, session.get(Project, row_id))


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


def _update_project_revision(session, project: Project, revision: int) -> None:
    result = session.execute(
        update(Project).where(Project.id == project.id, Project.revision == revision)
        .values(revision=revision + 1, updated_at=shared._now())
    )
    if result.rowcount != 1:
        shared._conflict_or_missing(session, Project, project.id)


@router.get("/projects/{project_id}/dataset-references", response_model=ProjectDatasetReferencePage, dependencies=[Depends(deps.authenticate)])
def list_project_dataset_references(
    project_id: UUID, session: deps.ReadSession, limit: deps.Limit = 50, offset: deps.Offset = 0,
    sort_by: deps.SortBy = "created_at", order: deps.Order = "desc",
):
    project = session.get(Project, shared._id(project_id))
    if project is None:
        raise not_found()
    total = session.scalar(select(func.count()).select_from(ProjectDatasetReference)
        .where(ProjectDatasetReference.project_id == project.id)) or 0
    column = ProjectDatasetReference.added_at
    rows = session.scalars(select(ProjectDatasetReference)
        .where(ProjectDatasetReference.project_id == project.id)
        .order_by(column.desc() if order == "desc" else column.asc(), ProjectDatasetReference.id.asc())
        .limit(limit).offset(offset)).all()
    return shared._page([_dataset_reference_out(session, row) for row in rows], total, limit, offset)


@router.get("/projects/{project_id}/datasets", response_model=ProjectDatasetReferencePage, dependencies=[Depends(deps.authenticate)])
def list_project_datasets(
    project_id: UUID, session: deps.ReadSession, limit: deps.Limit = 50, offset: deps.Offset = 0,
):
    return list_project_dataset_references(project_id, session, limit, offset)


@router.post("/projects/{project_id}/dataset-references", response_model=ProjectDatasetReferenceOut, status_code=201, dependencies=[Depends(deps.authenticate)])
def add_project_dataset_reference(project_id: UUID, body: ProjectDatasetReferenceCreate, session: deps.WriteSession):
    project_id_text = shared._id(project_id)
    project = session.get(Project, project_id_text)
    if project is None:
        raise not_found()
    dataset = session.get(Dataset, shared._id(body.dataset_id))
    version = session.get(DatasetVersion, shared._id(body.dataset_version_id))
    if dataset is None or version is None or version.dataset_id != dataset.id:
        raise invalid_reference("数据集版本不属于指定的数据集。")
    if dataset.status != "active":
        raise invalid_reference("已归档数据集不能新建项目引用。")
    _update_project_revision(session, project, body.base_revision)
    existing = session.scalar(select(ProjectDatasetReference).where(
        ProjectDatasetReference.project_id == project_id_text,
        ProjectDatasetReference.dataset_version_id == version.id,
    ))
    if existing:
        raise ApiError(409, "REVISION_CONFLICT", "项目已引用该数据集版本。")
    reference = ProjectDatasetReference(
        id=str(uuid4()), project_id=project_id_text, dataset_id=dataset.id,
        dataset_version_id=version.id, base_revision=body.base_revision + 1, added_at=shared._now(),
    )
    session.add(reference)
    session.flush()
    session.expire_all()
    return _dataset_reference_out(session, session.get(ProjectDatasetReference, reference.id))


@router.get("/projects/{project_id}/dataset-references/{reference_id}", response_model=ProjectDatasetReferenceOut, dependencies=[Depends(deps.authenticate)])
def get_project_dataset_reference(project_id: UUID, reference_id: UUID, session: deps.ReadSession):
    project = session.get(Project, shared._id(project_id))
    row = session.get(ProjectDatasetReference, shared._id(reference_id))
    if project is None or row is None or row.project_id != project.id:
        raise not_found()
    return _dataset_reference_out(session, row)


@router.delete("/projects/{project_id}/dataset-references/{reference_id}", response_model=dict, dependencies=[Depends(deps.authenticate)])
def remove_project_dataset_reference(
    project_id: UUID, reference_id: UUID, body: ProjectReferenceDelete, session: deps.WriteSession,
):
    project_id_text, reference_id_text = shared._id(project_id), shared._id(reference_id)
    project = session.get(Project, project_id_text)
    reference = session.get(ProjectDatasetReference, reference_id_text)
    if project is None or reference is None or reference.project_id != project_id_text:
        raise not_found()
    _update_project_revision(session, project, body.base_revision)
    session.delete(reference)
    session.flush()
    return {"deleted_id": reference_id_text, "revision": body.base_revision + 1}


@router.post("/projects/{project_id}/asset-references", response_model=ProjectAssetReferenceOut, status_code=201, dependencies=[Depends(deps.authenticate)])
def add_project_asset_reference(project_id: UUID, body: ProjectReferenceCreate, session: deps.WriteSession):
    project_id_text = shared._id(project_id)
    project = session.get(Project, project_id_text)
    if project is None:
        raise not_found()
    asset, version = _asset_version_scope(session, project_id, body.asset_version_id)
    if asset.status != "active":
        raise invalid_reference("已归档资产不能新建项目引用。")
    if session.scalar(select(ProjectAssetReference.id).where(
        ProjectAssetReference.project_id == project_id_text,
        ProjectAssetReference.asset_version_id == version.id,
    )):
        raise ApiError(409, "REVISION_CONFLICT", "项目已引用该资产版本。")
    _update_project_revision(session, project, body.base_revision)
    reference = ProjectAssetReference(
        id=str(uuid4()), project_id=project_id_text, asset_version_id=version.id, added_at=shared._now()
    )
    session.add(reference)
    session.flush()
    session.expire_all()
    return shared._reference_out(session, session.get(ProjectAssetReference, reference.id), asset, version)


@router.delete("/projects/{project_id}/asset-references/{reference_id}", response_model=dict, dependencies=[Depends(deps.authenticate)])
def remove_project_asset_reference(
    project_id: UUID, reference_id: UUID, body: ProjectReferenceDelete, session: deps.WriteSession,
):
    project_id_text, reference_id_text = shared._id(project_id), shared._id(reference_id)
    project = session.get(Project, project_id_text)
    reference = session.get(ProjectAssetReference, reference_id_text)
    if project is None or reference is None or reference.project_id != project_id_text:
        raise not_found()
    _update_project_revision(session, project, body.base_revision)
    session.delete(reference)
    session.flush()
    return {"deleted_id": reference_id_text, "revision": body.base_revision + 1}


def _require_project_reference(session, project_id: UUID, reference_id: UUID, version_id: UUID | None = None):
    reference = session.get(ProjectAssetReference, shared._id(reference_id))
    if reference is None or reference.project_id != shared._id(project_id):
        raise not_found()
    if version_id is not None and reference.asset_version_id != shared._id(version_id):
        raise not_found()
    asset, version = _asset_version_scope(session, project_id, UUID(reference.asset_version_id))
    return asset, version


@router.get(
    "/projects/{project_id}/asset-references/{reference_id}/versions/{version_id}/hdus",
    response_model=FitsHduPage, dependencies=[Depends(deps.authenticate)],
)
def list_project_reference_hdus(
    project_id: UUID, reference_id: UUID, version_id: UUID, session: deps.ReadSession,
    limit: deps.Limit = 200, offset: deps.Offset = 0,
):
    _, version = _require_project_reference(session, project_id, reference_id, version_id)
    total = session.scalar(select(func.count()).select_from(FitsHduMetadata).where(FitsHduMetadata.asset_version_id == version.id)) or 0
    rows = session.scalars(select(FitsHduMetadata).where(FitsHduMetadata.asset_version_id == version.id)
        .order_by(FitsHduMetadata.hdu_index).limit(limit).offset(offset)).all()
    return shared._page([_fits_hdu_out(row) for row in rows], total, limit, offset)


@router.get(
    "/projects/{project_id}/asset-references/{reference_id}/versions/{version_id}/hdus/{hdu_index}/header",
    response_model=FitsHeaderOut, dependencies=[Depends(deps.authenticate)],
)
def get_project_reference_header(
    project_id: UUID, reference_id: UUID, version_id: UUID, hdu_index: int, session: deps.ReadSession,
):
    _, version = _require_project_reference(session, project_id, reference_id, version_id)
    hdu = session.scalar(select(FitsHduMetadata).where(
        FitsHduMetadata.asset_version_id == version.id, FitsHduMetadata.hdu_index == hdu_index,
    ))
    if hdu is None:
        raise not_found()
    return _header_out(version, hdu)


@router.get(
    "/projects/{project_id}/asset-references/{reference_id}/previews/{size}",
    responses={200: {"content": {"image/jpeg": {"schema": {"type": "string", "format": "binary"}}}}},
    dependencies=[Depends(deps.authenticate)],
)
def get_project_reference_preview(project_id: UUID, reference_id: UUID, size: str, request: Request, session: deps.ReadSession):
    reference = session.get(ProjectAssetReference, shared._id(reference_id))
    if reference is None or reference.project_id != shared._id(project_id):
        raise not_found()
    asset, version = _asset_version_scope(session, project_id, UUID(reference.asset_version_id))
    if asset.id != version.asset_id:
        raise not_found()
    selected = session.scalar(select(FitsHduMetadata.hdu_index).where(
        FitsHduMetadata.asset_version_id == version.id, FitsHduMetadata.is_selected.is_(True)
    ))
    if selected is None and (version.scientific_metadata or {}).get("format") in {"image", "raw", "xisf", "video"}:
        selected = 0
    return _read_preview(request, version.id, selected, size)
