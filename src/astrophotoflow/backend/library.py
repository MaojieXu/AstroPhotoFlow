from __future__ import annotations
from fastapi import APIRouter

from .dependencies import ERROR_RESPONSES
from .dependencies import Limit, Offset, Order, ReadSession, SortBy, authenticate
from .common import _asset_out, _asset_version_scope, _dataset_out, _dataset_version_out, _fits_hdu_out, _header_out, _id, _order, _page, _read_preview
from . import dependencies as deps
from . import common as shared

from typing import Literal
from uuid import UUID
from fastapi import Depends, Query, Request
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session
from .errors import ApiError, not_found
from .models import Asset, AssetTask, AssetTaskItem, AssetVersion, Dataset, DatasetVersion, Equipment, FitsHduMetadata, LibraryEntryRemoval
from .schemas import AssetOut, AssetPage, AssetVersionOut, AssetVersionPage, FitsHeaderOut, FitsHduPage, LibraryFilterOptions, LibraryItemPage
from .import_schemas import AssetClassification, AssetParameters, AssetPatch
from decimal import Decimal, ROUND_HALF_UP
from functools import cmp_to_key


router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)


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


def _rounded_temperature(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _cmp(left, right) -> int:
    return (left > right) - (left < right)


def _entry_members(entry: dict) -> list[dict]:
    if entry["entry_type"] == "dataset":
        return [{"asset": member["asset"], "version": member["version"]} for member in (entry["version"] or {}).get("members", [])]
    return [{"asset": entry["asset"], "version": entry["asset"].get("current_version")}]


def _asset_sort_value(member: dict, sort_by: str, equipment_names: dict[str, str]):
    asset, version = member["asset"], member["version"] or {}
    parameters, classification = asset.get("parameters") or {}, asset.get("classification") or {}
    if sort_by == "classification":
        return classification.get("frame_class"), classification.get("frame_type")
    if sort_by in {"camera", "optical_system", "filter"}:
        key = {"camera": "camera_id", "optical_system": "optical_system_id", "filter": "filter_id"}[sort_by]
        record_id = parameters.get(key)
        return equipment_names.get(record_id) if record_id else None
    if sort_by == "parameter_mode":
        mode = parameters.get("parameter_mode")
        if mode == "iso":
            return (0, parameters.get("iso"), None)
        if mode == "gain":
            return (1, parameters.get("gain"), parameters.get("offset"))
        return (2, None, None)
    if sort_by == "binning":
        return parameters.get("binning_x"), parameters.get("binning_y")
    if sort_by == "cfa_pattern":
        return parameters.get("cfa_pattern")
    if sort_by == "exposure_seconds":
        return parameters.get("exposure_seconds")
    if sort_by == "integration_seconds":
        return parameters.get("integration_seconds")
    if sort_by == "sensor_temperature_c":
        return parameters.get("sensor_temperature_c")
    if sort_by == "storage_mode":
        return version.get("storage_mode")
    if sort_by == "status":
        return asset.get("status")
    if sort_by == "notes":
        return asset.get("notes")
    return asset.get("name")


def _value_state(value, sort_by: str) -> int:
    if value is None:
        return 2
    if sort_by in {"classification", "binning"}:
        if all(part is None for part in value):
            return 2
        if any(part is None for part in value):
            return 1
    if sort_by == "parameter_mode":
        mode, first, second = value
        if mode == 2:
            return 2
        if first is None:
            return 1
    return 0


def _entry_sort_value(entry: dict, sort_by: str, equipment_names: dict[str, str]):
    if entry["entry_type"] == "dataset" and sort_by in {"name", "status", "notes"}:
        value = entry["dataset"].get(sort_by)
        return (2, None) if value is None else (0, value)
    members = _entry_members(entry)
    values = [_asset_sort_value(member, sort_by, equipment_names) for member in members]
    if sort_by == "parameter_mode":
        modes = {value[0] for value in values}
        if not values or modes == {2}:
            return 3, 1, None, 1, None
        if len(modes) != 1:
            return 2, 1, None, 1, None
        mode = next(iter(modes))
        state = 0 if all(value == values[0] for value in values) and _value_state(values[0], sort_by) == 0 else 1
        if state:
            return mode, state, None, 1, None
        return mode, state, values[0][1], 0 if values[0][2] is not None else 1, values[0][2]
    if entry["entry_type"] == "dataset":
        if not values:
            return 2, None
        if all(value == values[0] for value in values):
            state = _value_state(values[0], sort_by)
            return (2 if state == 2 else state), values[0] if state == 0 else None
        return 1, None
    value = values[0]
    state = _value_state(value, sort_by)
    return state, value if state == 0 else None


def _compare_values(left, right, sort_by: str) -> int:
    if sort_by in {"classification", "binning"}:
        for first, second in zip(left, right):
            if first is None or second is None:
                result = _cmp(first is not None, second is not None)
            else:
                result = _cmp(first.casefold(), second.casefold()) if isinstance(first, str) else _cmp(first, second)
            if result:
                return result
        return _cmp(len(left), len(right))
    if isinstance(left, str):
        return _cmp(left.casefold(), right.casefold())
    return _cmp(left, right)


def _compare_library_entries(left: dict, right: dict, sort_by: str, order: str, equipment_names: dict[str, str]) -> int:
    direction = -1 if order == "desc" else 1
    if sort_by == "created_at":
        result = _cmp(left["sort_created_at"], right["sort_created_at"]) * direction
    else:
        left_value = _entry_sort_value(left, sort_by, equipment_names)
        right_value = _entry_sort_value(right, sort_by, equipment_names)
        if sort_by == "parameter_mode":
            result = _cmp(left_value[0], right_value[0])
            if not result:
                result = _cmp(left_value[1], right_value[1])
            if not result and left_value[1] == 0:
                result = _cmp(left_value[2], right_value[2]) * direction
            if not result and left_value[0] == 1 and left_value[1] == 0:
                result = _cmp(left_value[3], right_value[3])
            if not result and left_value[0] == 1 and left_value[1] == 0 and left_value[3] == 0:
                result = _cmp(left_value[4], right_value[4]) * direction
        else:
            result = _cmp(left_value[0], right_value[0])
            if not result and left_value[0] == 0:
                result = _compare_values(left_value[1], right_value[1], sort_by) * direction
    if result:
        return result
    return _cmp((left["entry_type"], left["id"]), (right["entry_type"], right["id"]))


@router.get("/library/items", response_model=LibraryItemPage, dependencies=[Depends(deps.authenticate)])
def library_items(
    session: deps.ReadSession, limit: deps.Limit = 50, offset: deps.Offset = 0,
    q: str | None = None, role: list[str] = Query(default=[]), frame_type: list[str] = Query(default=[]),
    sort_by: Literal[
        "created_at", "name", "classification", "camera", "parameter_mode", "exposure_seconds",
        "sensor_temperature_c", "binning", "cfa_pattern", "optical_system", "filter", "integration_seconds",
        "storage_mode", "status", "notes",
    ] = "created_at", order: Literal["asc", "desc"] = "desc",
    frame_class: list[str] = Query(default=[]), camera_id: list[UUID] = Query(default=[]),
    optical_system_id: list[UUID] = Query(default=[]), filter_id: list[UUID] = Query(default=[]),
    parameter_mode: list[str] = Query(default=[]), binning: list[str] = Query(default=[]),
    exposure_min: float | None = None, exposure_max: float | None = None,
    integration_min: float | None = None, integration_max: float | None = None,
    temperature_min: float | None = None, temperature_max: float | None = None,
    iso_min: float | None = None, iso_max: float | None = None,
    gain_min: float | None = None, gain_max: float | None = None,
    offset_min: float | None = None, offset_max: float | None = None,
):
    assets = session.scalars(select(Asset).where(Asset.scope == "shared", Asset.status == "active")).all()
    datasets = session.scalars(select(Dataset).where(Dataset.status == "active")).all()
    removals = set(session.execute(select(
        LibraryEntryRemoval.entry_type, LibraryEntryRemoval.entry_id, LibraryEntryRemoval.dataset_version_id
    )).all())
    removed_asset_ids = {entry_id for entry_type, entry_id, _ in removals if entry_type == "asset"}
    removed_dataset_ids = {entry_id for entry_type, entry_id, _ in removals if entry_type == "dataset"}
    removed_dataset_asset_ids = set()
    for removal in session.scalars(select(LibraryEntryRemoval).where(LibraryEntryRemoval.entry_type == "dataset")).all():
        removed_dataset_asset_ids.update(removal.member_asset_ids or [])
    failed_tasks = session.scalars(select(AssetTask).where(AssetTask.status == "completed_with_errors")).all()
    failed_task_ids = [task.id for task in failed_tasks]
    pending_asset_ids = set(session.scalars(select(AssetTaskItem.asset_id).join(
        AssetTask, AssetTask.id == AssetTaskItem.task_id
    ).where(AssetTaskItem.asset_id.is_not(None), AssetTask.status.in_({"queued", "running", "interrupted", "cancelling"}))).all())
    issue_by_dataset = {
        task.dataset_id: "导入完成，但部分素材或预览存在错误。"
        for task in failed_tasks if task.dataset_id
    }
    issue_by_asset = {}
    if failed_task_ids:
        for item in session.scalars(select(AssetTaskItem).where(
            AssetTaskItem.task_id.in_(failed_task_ids), AssetTaskItem.asset_id.is_not(None)
        )).all():
            if item.status == "completed_with_errors" or item.status == "failed":
                issue_by_asset[item.asset_id] = (item.error or {}).get("message") or "导入完成，但素材存在错误。"
    dataset_asset_ids: set[str] = set()
    entries = []
    member_filter = {
        "camera_id": {shared._id(value) for value in camera_id},
        "optical_system_id": {shared._id(value) for value in optical_system_id},
        "filter_id": {shared._id(value) for value in filter_id},
        "parameter_mode": set(parameter_mode),
    }
    bin_pairs=set()
    for value in binning:
        parts=value.lower().replace("×","x").split("x")
        if len(parts)==1:parts*=2
        bin_pairs.add(tuple(int(part) for part in parts))
    numeric_ranges = {
        "exposure_seconds": (exposure_min, exposure_max), "integration_seconds": (integration_min, integration_max),
        "sensor_temperature_c": (temperature_min, temperature_max), "iso": (iso_min, iso_max),
        "gain": (gain_min, gain_max), "offset": (offset_min, offset_max),
    }
    has_member_filters = bool(frame_class or role or frame_type or camera_id or optical_system_id or filter_id or parameter_mode or binning or
                              any(value is not None for pair in numeric_ranges.values() for value in pair))

    def matches_member(asset: dict) -> bool:
        classification, parameters = asset.get("classification") or {}, asset.get("parameters") or {}
        if role and asset["role"] not in role:
            return False
        if frame_type and classification.get("frame_type") not in frame_type:
            return False
        if frame_class and classification.get("frame_class") not in frame_class:
            return False
        if any(values and parameters.get(key) not in values for key, values in member_filter.items()):
            return False
        if bin_pairs and (parameters.get("binning_x"),parameters.get("binning_y")) not in bin_pairs:
            return False
        for key, (low, high) in numeric_ranges.items():
            value = parameters.get(key)
            if value is None:
                if low is not None or high is not None:
                    return False
                continue
            if key == "sensor_temperature_c":
                value = _rounded_temperature(value)
            if (low is not None and value < low) or (high is not None and value > high):
                return False
        return True

    for dataset in datasets:
        if dataset.id in removed_dataset_ids:
            continue
        version = session.get(DatasetVersion, dataset.current_version_id) if dataset.current_version_id else None
        version_out = _dataset_version_out(session, version) if version else None
        members = version_out["members"] if version_out else []
        if version_out:
            members = [member for member in members if str(member["asset"]["id"]) not in removed_asset_ids]
            version_out["members"] = members
        dataset_asset_ids.update(str(member["asset"]["id"]) for member in members)
        if q and q.casefold() not in dataset.name.casefold() and not any(
            q.casefold() in member["asset"]["name"].casefold() for member in members
        ):
            continue
        member_assets = [member["asset"] for member in members]
        if has_member_filters and not any(matches_member(asset) for asset in member_assets):
            continue
        entries.append({"entry_type": "dataset", "id": dataset.id, "dataset": _dataset_out(session, dataset), "version": version_out,
                        "import_issue": issue_by_dataset.get(dataset.id),
                        "sort_created_at": dataset.created_at, "sort_name": dataset.name})
    for asset in assets:
        if asset.id in dataset_asset_ids or asset.id in removed_dataset_asset_ids or asset.id in pending_asset_ids or asset.id in removed_asset_ids:
            continue
        if q and q.casefold() not in asset.name.casefold():
            continue
        if has_member_filters and not matches_member(shared._asset_out(session, asset)):
            continue
        entries.append({"entry_type": "asset", "id": asset.id, "asset": shared._asset_out(session, asset),
                        "import_issue": issue_by_asset.get(asset.id),
                        "sort_created_at": asset.created_at, "sort_name": asset.name})
    equipment_names = {row.id: row.name for row in session.scalars(select(Equipment)).all()}
    entries.sort(key=cmp_to_key(lambda left, right: _compare_library_entries(left, right, sort_by, order, equipment_names)))
    page = [{key: value for key, value in entry.items() if not key.startswith("sort_") and key != "id"} for entry in entries[offset:offset + limit]]
    return shared._page(page, len(entries), limit, offset)


@router.get("/library/filter-options", response_model=LibraryFilterOptions, dependencies=[Depends(deps.authenticate)])
def library_filter_options(session: deps.ReadSession):
    assets = session.scalars(select(Asset).where(Asset.scope == "shared", Asset.status == "active")).all()
    datasets = session.scalars(select(Dataset).where(Dataset.status == "active")).all()
    removals = set(session.execute(select(
        LibraryEntryRemoval.entry_type, LibraryEntryRemoval.entry_id, LibraryEntryRemoval.dataset_version_id
    )).all())
    removed_asset_ids = {entry_id for entry_type, entry_id, _ in removals if entry_type == "asset"}
    removed_dataset_ids = {entry_id for entry_type, entry_id, _ in removals if entry_type == "dataset"}
    removed_dataset_asset_ids = set()
    for removal in session.scalars(select(LibraryEntryRemoval).where(LibraryEntryRemoval.entry_type == "dataset")).all():
        removed_dataset_asset_ids.update(removal.member_asset_ids or [])
    pending_asset_ids = set(session.scalars(select(AssetTaskItem.asset_id).join(
        AssetTask, AssetTask.id == AssetTaskItem.task_id
    ).where(AssetTaskItem.asset_id.is_not(None), AssetTask.status.in_({"queued", "running", "interrupted", "cancelling"}))).all())
    grouped_ids = set()
    member_assets = []
    for dataset in datasets:
        if dataset.id in removed_dataset_ids:
            continue
        if dataset.current_version_id is None:
            continue
        version = session.get(DatasetVersion, dataset.current_version_id)
        if version is None:
            continue
        for member in _dataset_version_out(session, version)["members"]:
            if str(member["asset"]["id"]) in removed_asset_ids:
                continue
            grouped_ids.add(str(member["asset"]["id"]))
            member_assets.append(member["asset"])
    records = [shared._asset_out(session, row) for row in assets
               if row.id not in grouped_ids and row.id not in removed_dataset_asset_ids
               and row.id not in pending_asset_ids and row.id not in removed_asset_ids]
    records.extend(member_assets)
    parameters = [(row.get("parameters") or {}) for row in records]
    classifications = [(row.get("classification") or {}) for row in records]

    def values(key, source=parameters):
        return sorted({row[key] for row in source if row.get(key) is not None}, key=lambda value: str(value).casefold())

    equipment_ids = {key: {parameter[key] for parameter in parameters if parameter.get(key) is not None}
                      for key in ("camera_id", "optical_system_id", "filter_id")}
    equipment_options = {}
    for key, ids in equipment_ids.items():
        equipment_options[key] = [{"id": UUID(row.id), "name": row.name} for row in session.scalars(
            select(Equipment).where(Equipment.id.in_(ids)).order_by(Equipment.name, Equipment.id)
        ).all()] if ids else []
    numeric_ranges = {}
    for key in ("exposure_seconds", "integration_seconds", "sensor_temperature_c", "iso", "gain", "offset"):
        known = [row[key] for row in parameters if row.get(key) is not None]
        if known:
            if key == "sensor_temperature_c":
                known = [_rounded_temperature(value) for value in known]
            numeric_ranges[key] = {"min": min(known), "max": max(known)}
    bin_values=sorted({f"{row.get('binning_x')}x{row.get('binning_y')}" for row in parameters
                       if row.get("binning_x") is not None and row.get("binning_y") is not None})
    return {
        "frame_classes": values("frame_class", classifications), "frame_types": values("frame_type", classifications),
        "roles": sorted({row["role"] for row in records}), "parameter_modes": values("parameter_mode"),
        "bin_values": bin_values,
        "equipment": equipment_options, "numeric_ranges": numeric_ranges,
    }


@router.get("/library/assets/{asset_id}", response_model=AssetOut, dependencies=[Depends(deps.authenticate)])
def get_asset(asset_id: UUID, session: deps.ReadSession):
    row = session.get(Asset, shared._id(asset_id))
    if row is None or row.scope != "shared":
        raise not_found()
    return shared._asset_out(session, row)


@router.patch("/library/assets/{asset_id}", response_model=AssetOut, dependencies=[Depends(deps.authenticate)])
def patch_asset(asset_id: UUID, body: AssetPatch, session: deps.WriteSession):
    asset_id_text = shared._id(asset_id)
    asset = session.get(Asset, asset_id_text)
    if asset is None or asset.scope != "shared":
        raise not_found()
    changes = body.model_dump(exclude_unset=True, exclude={"base_revision", "classification", "parameters"})
    shared._assert_patch_values(changes, {"name", "status"})
    classification = dict(asset.classification or {})
    parameters = dict(asset.parameters or {})
    value_sources = dict(asset.value_sources or {})
    if body.classification is not None:
        patch = body.classification.model_dump(exclude_unset=True)
        classification.update(patch)
        if classification.get("frame_class") == "video":
            classification["frame_type"] = None
        try:
            classification = AssetClassification.model_validate(classification).model_dump(mode="json")
        except Exception as exc:
            raise ApiError(422, "VALIDATION_ERROR", "分类资料无效。", [{"path": "classification", "message": "请同时提供有效的素材形态和帧用途。"}]) from exc
        for key in patch:
            value_sources[f"classification.{key}"] = "manual"
        changes["classification"] = classification
        changes["role"] = "calibration" if classification.get("frame_type") in {"bias", "dark", "flat", "dark_flat"} else "raw"
    if body.parameters is not None:
        patch = body.parameters.model_dump(exclude_unset=True, mode="json")
        parameters.update(patch)
        try:
            parameters = AssetParameters.model_validate(parameters).model_dump(mode="json")
        except Exception as exc:
            raise ApiError(422, "VALIDATION_ERROR", "拍摄参数无效。", [{"path": "parameters", "message": "请检查参数值及设备 ID。"}]) from exc
        for key in patch:
            value_sources[key] = "manual"
        for key, kind in (("camera_id", "camera"), ("optical_system_id", "optical_system"), ("filter_id", "filter")):
            if parameters.get(key) is not None:
                shared._check_equipment_ref(session, parameters[key], kind, f"parameters.{key}")
        changes["parameters"] = parameters
    if body.classification is not None or body.parameters is not None:
        changes["value_sources"] = value_sources
    result = session.execute(update(Asset).where(
        Asset.id == asset_id_text, Asset.revision == body.base_revision
    ).values(**changes, revision=body.base_revision + 1))
    if result.rowcount != 1:
        shared._conflict_or_missing(session, Asset, asset_id_text)
    session.flush()
    session.expire_all()
    return shared._asset_out(session, session.get(Asset, asset_id_text))


@router.get("/library/assets/{asset_id}/versions", response_model=AssetVersionPage, dependencies=[Depends(deps.authenticate)])
def list_asset_versions(asset_id: UUID, session: deps.ReadSession, limit: deps.Limit = 50, offset: deps.Offset = 0):
    asset = session.get(Asset, shared._id(asset_id))
    if asset is None or asset.scope != "shared":
        raise not_found()
    total = session.scalar(select(func.count()).select_from(AssetVersion).where(AssetVersion.asset_id == asset.id)) or 0
    rows = session.scalars(select(AssetVersion).where(AssetVersion.asset_id == asset.id)
        .order_by(AssetVersion.version_number.desc()).limit(limit).offset(offset)).all()
    return shared._page([shared._version_out(row) for row in rows], total, limit, offset)


@router.get("/library/assets/{asset_id}/versions/{version_id}", response_model=AssetVersionOut, dependencies=[Depends(deps.authenticate)])
def get_asset_version(asset_id: UUID, version_id: UUID, session: deps.ReadSession):
    asset, version = _asset_version_scope(session, None, version_id)
    if asset.id != shared._id(asset_id):
        raise not_found()
    return shared._version_out(version)


@router.get("/library/assets/{asset_id}/versions/{version_id}/hdus", response_model=FitsHduPage, dependencies=[Depends(deps.authenticate)])
def list_version_hdus(asset_id: UUID, version_id: UUID, session: deps.ReadSession, limit: deps.Limit = 200, offset: deps.Offset = 0):
    asset, version = _asset_version_scope(session, None, version_id)
    if asset.id != shared._id(asset_id):
        raise not_found()
    total = session.scalar(select(func.count()).select_from(FitsHduMetadata).where(FitsHduMetadata.asset_version_id == version.id)) or 0
    rows = session.scalars(select(FitsHduMetadata).where(FitsHduMetadata.asset_version_id == version.id)
        .order_by(FitsHduMetadata.hdu_index).limit(limit).offset(offset)).all()
    return shared._page([_fits_hdu_out(row) for row in rows], total, limit, offset)


@router.get("/library/assets/{asset_id}/versions/{version_id}/hdus/{hdu_index}/header", response_model=FitsHeaderOut, dependencies=[Depends(deps.authenticate)])
def get_version_header(asset_id: UUID, version_id: UUID, hdu_index: int, session: deps.ReadSession):
    asset, version = _asset_version_scope(session, None, version_id)
    if asset.id != shared._id(asset_id):
        raise not_found()
    hdu = session.scalar(select(FitsHduMetadata).where(
        FitsHduMetadata.asset_version_id == version.id, FitsHduMetadata.hdu_index == hdu_index,
    ))
    if hdu is None:
        raise not_found()
    return _header_out(version, hdu)


@router.get(
    "/library/assets/{asset_id}/versions/{version_id}/previews/{size}",
    responses={200: {"content": {"image/jpeg": {"schema": {"type": "string", "format": "binary"}}}}},
    dependencies=[Depends(deps.authenticate)],
)
def get_version_preview(asset_id: UUID, version_id: UUID, size: str, request: Request, session: deps.ReadSession):
    asset, version = _asset_version_scope(session, None, version_id)
    if asset.id != shared._id(asset_id):
        raise not_found()
    selected = session.scalar(select(FitsHduMetadata.hdu_index).where(
        FitsHduMetadata.asset_version_id == version.id, FitsHduMetadata.is_selected.is_(True)
    ))
    if selected is None and (version.scientific_metadata or {}).get("format") in {"image", "raw", "xisf", "video"}:
        selected = 0
    return _read_preview(request, version.id, selected, size)
