from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from functools import cmp_to_key
import hashlib
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy import delete, func, select, update

from . import api as base
from .db import Database
from .errors import ApiError, invalid_reference, not_found
from .files import entries_page, find_root, format_for_path, resolve_relative
from .fits_preview import PREVIEW_ALGORITHM_VERSION, create_preview
from .import_schemas import (
    AssetClassification, AssetParameters, AssetPatch, DatasetMemberParametersUpdate, DatasetMembersCreate, DatasetPatch, ImportCreate,
    LibraryEntriesRemove, LibraryTrashDelete, LibraryTrashSelection,
    ProjectDatasetReferenceCreate, ProjectReferenceCreate, ProjectReferenceDelete, RetryCreate, UploadImportCreate,
)
from .ingestion import mark_interrupted_tasks, process_task, validate_import_equipment
from .models import (
    Asset, AssetTask, AssetTaskItem, AssetVersion, Dataset, DatasetMember, DatasetVersion, Equipment, LibraryEntryRemoval,
    FitsHduMetadata, Preview, Project, ProjectAssetReference, ProjectDatasetReference,
)
from .schemas import (
    AssetOut, AssetPage, AssetTaskOut, AssetTaskPage, AssetVersionOut, AssetVersionPage, DatasetOut,
    DatasetPage, DatasetVersionOut, DatasetVersionPage, FitsHeaderOut, FitsHduOut, FitsHduPage,
    DatasetMemberParametersUpdateOut, ImportAccepted, ImportRootEntryPage, ImportRootOut, LibraryEntriesRemoveOut, LibraryFilterOptions, LibraryItemPage, ProjectAssetReferenceOut,
    LibraryTrashPage, LibraryTrashItemOut, LibraryTrashPreviewOut, LibraryTrashDeleteOut,
    LibraryTrashReferenceOut,
    ProjectDatasetReferenceOut, ProjectDatasetReferencePage,
)


logger = logging.getLogger("astrophotoflow.service.stage2")
router = APIRouter(prefix="/api/v1", responses=base.ERROR_RESPONSES)


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


@router.get("/library/items", response_model=LibraryItemPage, dependencies=[Depends(base.authenticate)])
def library_items(
    session: base.ReadSession, limit: base.Limit = 50, offset: base.Offset = 0,
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
        "camera_id": {base._id(value) for value in camera_id},
        "optical_system_id": {base._id(value) for value in optical_system_id},
        "filter_id": {base._id(value) for value in filter_id},
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
        if has_member_filters and not matches_member(base._asset_out(session, asset)):
            continue
        entries.append({"entry_type": "asset", "id": asset.id, "asset": base._asset_out(session, asset),
                        "import_issue": issue_by_asset.get(asset.id),
                        "sort_created_at": asset.created_at, "sort_name": asset.name})
    equipment_names = {row.id: row.name for row in session.scalars(select(Equipment)).all()}
    entries.sort(key=cmp_to_key(lambda left, right: _compare_library_entries(left, right, sort_by, order, equipment_names)))
    page = [{key: value for key, value in entry.items() if not key.startswith("sort_") and key != "id"} for entry in entries[offset:offset + limit]]
    return base._page(page, len(entries), limit, offset)


@router.delete("/library/items", response_model=LibraryEntriesRemoveOut, dependencies=[Depends(base.authenticate)])
def remove_library_entries(body: LibraryEntriesRemove, session: base.WriteSession):
    removals = set(session.execute(select(LibraryEntryRemoval.entry_type, LibraryEntryRemoval.entry_id)).all())
    checked = []
    for item in body.items:
        record_id = base._id(item.id)
        if item.entry_type == "asset":
            record = session.get(Asset, record_id)
            if record is None or record.scope != "shared" or record.status != "active":
                raise not_found()
            if record.revision != item.revision:
                base._conflict_or_missing(session, Asset, record_id)
        else:
            record = session.get(Dataset, record_id)
            if record is None or record.status != "active":
                raise not_found()
            if record.revision != item.revision:
                base._conflict_or_missing(session, Dataset, record_id)
            if record.current_version_id != (base._id(item.current_version_id) if item.current_version_id else None):
                raise ApiError(409, "REVISION_CONFLICT", "数据集成员版本已变化，请重新读取后删除。")
        checked.append((item.entry_type, record_id, record.current_version_id if item.entry_type == "dataset" else None))

    added = 0
    for entry_type, entry_id, dataset_version_id in checked:
        if (entry_type, entry_id) not in removals:
            member_asset_ids = []
            if entry_type == "dataset" and dataset_version_id:
                member_asset_ids = list(session.scalars(
                    select(AssetVersion.asset_id).join(DatasetMember, DatasetMember.asset_version_id == AssetVersion.id)
                    .where(DatasetMember.dataset_version_id == dataset_version_id).distinct()
                ).all())
            session.add(LibraryEntryRemoval(
                entry_type=entry_type, entry_id=entry_id, dataset_version_id=dataset_version_id,
                member_asset_ids=member_asset_ids, cleanup_status="trash",
            ))
            added += 1
    session.flush()
    return {"removed_count": added}


def _trash_item(session, removal: LibraryEntryRemoval, source_dataset_id: str | None = None) -> dict:
    row = session.get(Asset if removal.entry_type == "asset" else Dataset, removal.entry_id)
    name = row.name if row is not None else removal.entry_id
    revision = row.revision if row is not None else 1
    current_version_id = row.current_version_id if row is not None else None
    photo_count = 1 if removal.entry_type == "asset" else len(set(removal.member_asset_ids or []))
    groups = []
    member_asset_ids = removal.member_asset_ids or [] if removal.entry_type == "dataset" else []
    if removal.entry_type == "asset":
        asset_groups = session.scalars(select(Dataset).join(
            DatasetVersion, DatasetVersion.dataset_id == Dataset.id
        ).join(DatasetMember, DatasetMember.dataset_version_id == DatasetVersion.id).join(
            AssetVersion, AssetVersion.id == DatasetMember.asset_version_id
        ).where(AssetVersion.asset_id == removal.entry_id).distinct()).all()
        groups = [{"id": UUID(group.id), "name": group.name,
                   "in_trash": session.get(LibraryEntryRemoval, ("dataset", group.id)) is not None}
                  for group in asset_groups]
    return LibraryTrashItemOut(
        entry_type=removal.entry_type, id=UUID(removal.entry_id), name=name, removed_at=base._utc(removal.removed_at),
        revision=revision, current_version_id=UUID(current_version_id) if current_version_id else None, cleanup_status=removal.cleanup_status,
        cleanup_error=removal.cleanup_error, photo_count=photo_count,
        member_asset_ids=[UUID(asset_id) for asset_id in member_asset_ids], groups=groups, source_dataset_id=UUID(source_dataset_id) if source_dataset_id else None,
    ).model_dump()


@router.get("/library/trash", response_model=LibraryTrashPage, dependencies=[Depends(base.authenticate)])
def library_trash(session: base.ReadSession, limit: base.Limit = 50, offset: base.Offset = 0,
                  group_id: UUID | None = None):
    if group_id is not None:
        group_id_text = base._id(group_id)
        group_removal = session.get(LibraryEntryRemoval, ("dataset", group_id_text))
        if group_removal is None:
            raise not_found()
        asset_ids = list(dict.fromkeys(group_removal.member_asset_ids or []))
        assets = session.scalars(select(Asset).where(Asset.id.in_(asset_ids)).order_by(Asset.name, Asset.id).limit(limit).offset(offset)).all() if asset_ids else []
        items = []
        for asset in assets:
            asset_removal = session.get(LibraryEntryRemoval, ("asset", asset.id))
            if asset_removal is not None:
                items.append(_trash_item(session, asset_removal, group_id_text))
            else:
                virtual = LibraryEntryRemoval(entry_type="asset", entry_id=asset.id,
                    dataset_version_id=group_removal.dataset_version_id, member_asset_ids=[], pending_paths=[],
                    cleaned_paths=[], cleaned_asset_ids=[], cleanup_status="trash", cleanup_error=None,
                    removed_at=group_removal.removed_at)
                items.append(_trash_item(session, virtual, group_id_text))
        return base._page(items, len(asset_ids), limit, offset)
    total = session.scalar(select(func.count()).select_from(LibraryEntryRemoval)) or 0
    removals = session.scalars(select(LibraryEntryRemoval).order_by(
        LibraryEntryRemoval.removed_at.desc(), LibraryEntryRemoval.entry_type, LibraryEntryRemoval.entry_id
    ).limit(limit).offset(offset)).all()
    return base._page([_trash_item(session, removal) for removal in removals], total, limit, offset)


@router.post("/library/trash/restore", dependencies=[Depends(base.authenticate)])
def restore_library_trash(body: LibraryTrashSelection, session: base.WriteSession):
    restored = 0
    restored_asset_ids = set()
    for item in body.items:
        removal = session.get(LibraryEntryRemoval, (item.entry_type, base._id(item.id)))
        source_dataset_id = base._id(item.source_dataset_id) if item.source_dataset_id else None
        source_group = session.get(LibraryEntryRemoval, ("dataset", source_dataset_id)) if source_dataset_id else None
        if removal is None and item.entry_type == "asset" and source_group is not None and base._id(item.id) in (source_group.member_asset_ids or []):
            removal = LibraryEntryRemoval(entry_type="asset", entry_id=base._id(item.id), removed_at=source_group.removed_at,
                cleanup_status="trash", member_asset_ids=[], pending_paths=[], cleaned_paths=[], cleaned_asset_ids=[])
            removal.source_dataset_id = source_dataset_id
        if removal is None or removal.cleanup_status != "trash":
            raise ApiError(409, "TRASH_STATE_CONFLICT", "该记录已清理或状态已变化，不能恢复。")
        row = session.get(Asset if item.entry_type == "asset" else Dataset, removal.entry_id)
        if row is None or row.revision != item.revision or base._utc(removal.removed_at) != base._utc(item.removed_at):
            raise ApiError(409, "REVISION_CONFLICT", "垃圾桶记录已变化，请重新读取。")
        if isinstance(row, Asset) and row.current_version_id != (base._id(item.current_version_id) if item.current_version_id else None):
            raise ApiError(409, "REVISION_CONFLICT", "照片版本已变化，请重新读取。")
        if isinstance(row, Dataset) and row.current_version_id != (base._id(item.current_version_id) if item.current_version_id else None):
            raise ApiError(409, "REVISION_CONFLICT", "数据集版本已变化，请重新读取。")
        if item.entry_type == "dataset":
            member_removals = [session.get(LibraryEntryRemoval, ("asset", asset_id)) for asset_id in (removal.member_asset_ids or [])]
            if removal.cleaned_asset_ids or any(member is not None and member.cleanup_status != "trash" for member in member_removals):
                raise ApiError(409, "TRASH_STATE_CONFLICT", "组内照片已有部分清理，不能恢复该组。")
        if source_dataset_id and item.entry_type == "asset":
            source_group = session.get(LibraryEntryRemoval, ("dataset", source_dataset_id))
            if source_group is None or removal.entry_id not in (source_group.member_asset_ids or []):
                raise ApiError(409, "TRASH_STATE_CONFLICT", "照片已不属于该组的待清理范围。")
            source_group.member_asset_ids = [asset_id for asset_id in source_group.member_asset_ids if asset_id != removal.entry_id]
            if session.get(LibraryEntryRemoval, ("asset", removal.entry_id)) is not None:
                session.delete(session.get(LibraryEntryRemoval, ("asset", removal.entry_id)))
        else:
            session.delete(removal)
        if item.entry_type == "asset":
            restored_asset_ids.add(removal.entry_id)
        else:
            restored_asset_ids.update(removal.member_asset_ids or [])
        restored += 1
    for asset_id in restored_asset_ids:
        removal = session.get(LibraryEntryRemoval, ("asset", asset_id))
        if removal is not None:
            session.delete(removal)
        for group_removal in session.scalars(select(LibraryEntryRemoval).where(
            LibraryEntryRemoval.entry_type == "dataset")).all():
            if asset_id in (group_removal.member_asset_ids or []):
                group_removal.member_asset_ids = [member_id for member_id in group_removal.member_asset_ids if member_id != asset_id]
    return {"restored_count": restored}


def _selected_trash(session, body):
    records = []
    for item in body.items:
        removal = session.get(LibraryEntryRemoval, (item.entry_type, base._id(item.id)))
        row = session.get(Asset if item.entry_type == "asset" else Dataset, base._id(item.id))
        source_dataset_id = base._id(item.source_dataset_id) if item.source_dataset_id else None
        if removal is None and item.entry_type == "asset" and source_dataset_id:
            parent = session.get(LibraryEntryRemoval, ("dataset", source_dataset_id))
            if parent is not None and base._id(item.id) in (parent.member_asset_ids or []):
                removal = LibraryEntryRemoval(entry_type="asset", entry_id=base._id(item.id),
                    dataset_version_id=parent.dataset_version_id, member_asset_ids=[], pending_paths=[], cleaned_paths=[],
                    cleaned_asset_ids=[], cleanup_status="trash", cleanup_error=None, removed_at=parent.removed_at)
                removal.source_dataset_id = source_dataset_id
        elif removal is not None and source_dataset_id:
            parent = session.get(LibraryEntryRemoval, ("dataset", source_dataset_id))
            if parent is None or base._id(item.id) not in (parent.member_asset_ids or []):
                raise ApiError(409, "TRASH_STATE_CONFLICT", "照片已不属于该组的待清理范围。")
            removal.source_dataset_id = source_dataset_id
        if removal is None or row is None or removal.cleanup_status not in {"trash", "partial", "failed"}:
            raise ApiError(409, "TRASH_STATE_CONFLICT", "只能永久删除仍在垃圾桶中的内容。")
        if base._utc(removal.removed_at) != base._utc(item.removed_at) or row.revision != item.revision:
            raise ApiError(409, "REVISION_CONFLICT", "垃圾桶记录已变化，请重新预览。")
        if isinstance(row, Asset) and row.current_version_id != (base._id(item.current_version_id) if item.current_version_id else None):
            raise ApiError(409, "REVISION_CONFLICT", "照片版本已变化，请重新预览。")
        if isinstance(row, Dataset) and row.current_version_id != (base._id(item.current_version_id) if item.current_version_id else None):
            raise ApiError(409, "REVISION_CONFLICT", "数据集版本已变化，请重新预览。")
        records.append((removal, row))
    return records


def _trash_scope(session, settings, records):
    asset_ids = set()
    for removal, row in records:
        if removal.entry_type == "asset":
            asset_ids.add(row.id)
        else:
            asset_ids.update(removal.member_asset_ids or [])
    versions = session.scalars(select(AssetVersion).where(AssetVersion.asset_id.in_(asset_ids))).all() if asset_ids else []
    version_ids = {version.id for version in versions}
    deleting_dataset_ids = {row.id for removal, row in records if removal.entry_type == "dataset"}
    refs = []
    for ref, project in session.execute(select(ProjectAssetReference, Project).join(Project, Project.id == ProjectAssetReference.project_id).where(ProjectAssetReference.asset_version_id.in_(version_ids))).all() if version_ids else []:
        version = session.get(AssetVersion, ref.asset_version_id)
        refs.append({"id": UUID(ref.id), "kind": "project_asset", "name": project.name, "version": version.version_number})
    for member, dataset_version, dataset in session.execute(
        select(DatasetMember, DatasetVersion, Dataset).join(DatasetVersion, DatasetVersion.id == DatasetMember.dataset_version_id)
        .join(Dataset, Dataset.id == DatasetVersion.dataset_id).where(DatasetMember.asset_version_id.in_(version_ids))
    ).all() if version_ids else []:
        refs.append({"id": UUID(member.id), "kind": "dataset_member", "name": dataset.name, "version": dataset_version.version_number})
    selected_dataset_member_ids = {str(ref["id"]) for ref in refs if ref["kind"] == "dataset_member"}
    if deleting_dataset_ids:
        for member, dataset_version, dataset in session.execute(
            select(DatasetMember, DatasetVersion, Dataset).join(
                DatasetVersion, DatasetVersion.id == DatasetMember.dataset_version_id
            ).join(Dataset, Dataset.id == DatasetVersion.dataset_id).where(
                DatasetVersion.dataset_id.in_(deleting_dataset_ids)
            )
        ).all():
            if member.id not in selected_dataset_member_ids:
                refs.append({"id": UUID(member.id), "kind": "dataset_member", "name": dataset.name,
                             "version": dataset_version.version_number})
    selected_dataset_version_ids = {removal.dataset_version_id for removal, _ in records if removal.entry_type == "dataset" and removal.dataset_version_id}
    if version_ids:
        selected_dataset_version_ids.update(session.scalars(select(DatasetMember.dataset_version_id).where(
            DatasetMember.asset_version_id.in_(version_ids)
        )).all())
    if deleting_dataset_ids:
        selected_dataset_version_ids.update(session.scalars(select(DatasetVersion.id).where(
            DatasetVersion.dataset_id.in_(deleting_dataset_ids)
        )).all())
    for ref, project in session.execute(select(ProjectDatasetReference, Project).join(
        Project, Project.id == ProjectDatasetReference.project_id
    ).where(ProjectDatasetReference.dataset_version_id.in_(selected_dataset_version_ids))).all() if selected_dataset_version_ids else []:
        version = session.get(DatasetVersion, ref.dataset_version_id)
        refs.append({"id": UUID(ref.id), "kind": "project_dataset", "name": project.name, "version": version.version_number})
    active_task_statuses = {"queued", "running", "cancelling", "interrupted"}
    task_ids = set(session.scalars(select(AssetTask.id).join(
        AssetTaskItem, AssetTaskItem.task_id == AssetTask.id
    ).where(AssetTask.status.in_(active_task_statuses), AssetTaskItem.asset_id.in_(asset_ids))).all()) if asset_ids else set()
    task_ids.update(session.scalars(select(AssetTask.id).where(
        AssetTask.status.in_(active_task_statuses), AssetTask.dataset_id.in_(deleting_dataset_ids)
    )).all() if deleting_dataset_ids else [])
    task_ids = sorted(task_ids)
    paths = {}
    for version in versions:
        if version.storage_mode == "managed":
            path = (settings.data_dir / version.storage_location).resolve()
            if not path.is_relative_to(settings.data_dir.resolve()):
                raise ApiError(409, "FILE_SCOPE_INVALID", "托管文件路径不在服务数据目录中，已阻止清理。")
            paths[str(path)] = path
    previews = session.scalars(select(Preview).where(Preview.asset_version_id.in_(version_ids))).all() if version_ids else []
    for preview in previews:
        if not preview.storage_path:
            continue
        path = (settings.data_dir / preview.storage_path).resolve()
        if not path.is_relative_to(settings.data_dir.resolve()):
            raise ApiError(409, "FILE_SCOPE_INVALID", "预览文件路径不在服务数据目录中，已阻止清理。")
        paths[str(path)] = path
    managed_locations = [version.storage_location for version in versions if version.storage_mode == "managed"]
    if managed_locations:
        other_locations = set(session.scalars(select(AssetVersion.storage_location).where(
            AssetVersion.storage_location.in_(managed_locations), AssetVersion.asset_id.not_in(asset_ids)
        )).all())
        for location in other_locations:
            paths.pop(str((settings.data_dir / location).resolve()), None)
    preview_locations = [preview.storage_path for preview in previews]
    if preview_locations:
        other_preview_locations = set(session.scalars(select(Preview.storage_path).join(
            AssetVersion, AssetVersion.id == Preview.asset_version_id
        ).where(Preview.storage_path.in_(preview_locations), AssetVersion.asset_id.not_in(asset_ids))).all())
        for location in other_preview_locations:
            paths.pop(str((settings.data_dir / location).resolve()), None)
    managed_bytes = sum(path.stat().st_size for path in paths.values() if path.is_file())
    return asset_ids, versions, previews, refs, task_ids, paths, managed_bytes


@router.post("/library/trash/delete-preview", response_model=LibraryTrashPreviewOut, dependencies=[Depends(base.authenticate)])
def library_trash_delete_preview(body: LibraryTrashSelection, request: Request, session: base.ReadSession):
    records = _selected_trash(session, body)
    asset_ids, versions, previews, refs, tasks, paths, managed_bytes = _trash_scope(session, request.app.state.settings, records)
    snapshot = {
        "items": [(r.entry_type, r.entry_id, r.removed_at.isoformat(), row.revision, getattr(row, "current_version_id", None),
                   r.cleanup_status, tuple(sorted(r.pending_paths or [])), tuple(sorted(r.cleaned_paths or [])), tuple(sorted(r.member_asset_ids or [])), tuple(sorted(r.cleaned_asset_ids or [])))
                  for r, row in records],
        "assets": sorted((asset.id, asset.revision, asset.current_version_id) for asset in
                         session.scalars(select(Asset).where(Asset.id.in_(asset_ids))).all()) if asset_ids else [],
        "versions": sorted(v.id for v in versions), "refs": sorted(ref["id"] for ref in refs), "tasks": sorted(tasks),
        "paths": sorted((key, path.stat().st_size if path.is_file() else None) for key, path in paths.items()),
    }
    fingerprint = hashlib.sha256(json.dumps(snapshot, sort_keys=True, default=str).encode()).hexdigest()
    return {
        "items": [_trash_item(session, r) for r, _ in records], "references": refs, "tasks": tasks,
        "photo_count": len(asset_ids), "managed_file_count": len(paths), "managed_bytes": managed_bytes,
        "preview_fingerprint": fingerprint,
    }


@router.post("/library/trash/delete", response_model=LibraryTrashDeleteOut, dependencies=[Depends(base.authenticate)])
def library_trash_delete(body: LibraryTrashDelete, request: Request, session: base.ReadSession):
    records = _selected_trash(session, body)
    settings = request.app.state.settings
    asset_ids, versions, previews, refs, tasks, paths, managed_bytes = _trash_scope(session, settings, records)
    if tasks:
        raise ApiError(409, "IMPORT_ACTIVE", "正在执行或可恢复的导入任务仍占用所选内容，请先取消任务。")
    expected_references = {str(ref["id"]) for ref in refs}
    deleting_dataset_ids = {row.id for removal, row in records if removal.entry_type == "dataset"}
    expected_group_references = {group_id: set(session.scalars(select(ProjectDatasetReference.id).where(
        ProjectDatasetReference.dataset_id == group_id)).all()) for group_id in deleting_dataset_ids}
    if deleting_dataset_ids:
        expected_references.update(session.scalars(select(DatasetMember.id).join(
            DatasetVersion, DatasetVersion.id == DatasetMember.dataset_version_id
        ).where(DatasetVersion.dataset_id.in_(deleting_dataset_ids))).all())
    expected_tasks = set(tasks)
    asset_states = {asset.id: (asset.revision, asset.current_version_id) for asset in
                    session.scalars(select(Asset).where(Asset.id.in_(asset_ids))).all()} if asset_ids else {}
    original_paths = {str(path): path for path in paths.values()}
    paths_by_asset = {}
    for asset_id in asset_ids:
        asset_versions = [version for version in versions if version.asset_id == asset_id]
        candidate_paths = []
        for version in asset_versions:
            if version.storage_mode == "managed":
                candidate_paths.append((settings.data_dir / version.storage_location).resolve())
            candidate_paths.extend((settings.data_dir / preview.storage_path).resolve()
                                   for preview in previews if preview.asset_version_id == version.id and preview.storage_path)
        paths_by_asset[asset_id] = [path for path in candidate_paths if str(path) in original_paths]
    success_assets, success_datasets, failed = set(), set(), []
    deleted_file_count = deleted_bytes = missing_file_count = 0
    dataset_revision_deltas = {}
    selected_group_states = {}
    for removal, row in records:
        if removal.entry_type == "dataset":
            live_members = set(session.scalars(select(AssetVersion.asset_id).join(
                DatasetMember, DatasetMember.asset_version_id == AssetVersion.id
            ).where(DatasetMember.dataset_version_id == row.current_version_id)).all()) if row.current_version_id else set()
            selected_group_states[row.id] = (row.revision, row.current_version_id,
                set(removal.member_asset_ids or []), live_members)
    selected_group_ids = set(selected_group_states)

    # Save the confirmed finite path list before touching files. This also makes an interrupted
    # cleanup non-restorable until the operation either succeeds or proves that no path was removed.
    with request.app.state.database.write_session() as write:
        current_records = _selected_trash(write, body)
        for removal, _ in current_records:
            source_dataset_id = getattr(removal, "source_dataset_id", None)
            if source_dataset_id and write.get(LibraryEntryRemoval, ("asset", removal.entry_id)) is None:
                write.add(LibraryEntryRemoval(entry_type="asset", entry_id=removal.entry_id,
                    dataset_version_id=removal.dataset_version_id, member_asset_ids=[], pending_paths=[], cleaned_paths=[],
                    cleaned_asset_ids=[], cleanup_status="trash", cleanup_error=None, removed_at=removal.removed_at))
                removal.source_dataset_id = source_dataset_id
        current_preview = library_trash_delete_preview(body, request, write)
        if current_preview["preview_fingerprint"] != body.preview_fingerprint:
            raise ApiError(409, "TRASH_PREVIEW_STALE", "清理范围已变化，请重新预览。")
        for removal, _ in current_records:
            if removal.entry_type == "asset":
                pending = [str(path) for path in paths_by_asset.get(removal.entry_id, [])]
            else:
                pending = [str(path) for asset_id in (removal.member_asset_ids or [])
                           for path in paths_by_asset.get(asset_id, [])]
            removal.pending_paths = list(dict.fromkeys([*(removal.pending_paths or []), *pending]))
            removal.cleanup_status = "partial"
            removal.cleanup_error = None

    for asset_id in sorted(asset_ids):
        expected_versions = {version.id for version in versions if version.asset_id == asset_id}
        removed_paths = []
        asset_changed_projects, asset_changed_datasets = set(), set()
        try:
            with request.app.state.database.write_session() as write:
                asset = write.get(Asset, asset_id)
                if asset is not None and (asset.revision, asset.current_version_id) != asset_states[asset_id]:
                    raise ApiError(409, "TRASH_PREVIEW_STALE", "照片资料或版本已变化，请重新预览。")
                original = next(row for row in body.items if row.entry_type == "asset" and base._id(row.id) == asset_id) if any(
                    row.entry_type == "asset" and base._id(row.id) == asset_id for row in body.items) else None
                if asset is not None and original is not None and (asset.revision != original.revision or asset.current_version_id != (base._id(original.current_version_id) if original.current_version_id else None)):
                    raise ApiError(409, "TRASH_PREVIEW_STALE", "照片版本已变化，请重新预览。")
                current_versions = write.scalars(select(AssetVersion).where(AssetVersion.asset_id == asset_id)).all()
                if {version.id for version in current_versions} != expected_versions:
                    raise ApiError(409, "TRASH_PREVIEW_STALE", "照片版本已变化，请重新预览。")
                version_ids = expected_versions
                current_refs = set(write.scalars(select(ProjectAssetReference.id).where(
                    ProjectAssetReference.asset_version_id.in_(version_ids)
                )).all()) if version_ids else set()
                current_refs.update(write.scalars(select(DatasetMember.id).where(
                    DatasetMember.asset_version_id.in_(version_ids)
                )).all() if version_ids else [])
                member_dataset_version_ids = set(write.scalars(select(DatasetMember.dataset_version_id).where(
                    DatasetMember.asset_version_id.in_(version_ids)
                )).all()) if version_ids else set()
                current_group_project_refs = set(write.scalars(select(ProjectDatasetReference.id).where(
                    ProjectDatasetReference.dataset_version_id.in_(member_dataset_version_ids)
                )).all()) if member_dataset_version_ids else set()
                if not current_group_project_refs.issubset(expected_references):
                    raise ApiError(409, "TRASH_PREVIEW_STALE", "项目组关联已变化，请重新预览。")
                # Recheck selected containers before touching this member; new group-level
                # references, tasks, or membership changes must invalidate the confirmed range.
                for group_id, (initial_revision, initial_version_id, initial_members, initial_live_members) in selected_group_states.items():
                    group = write.get(Dataset, group_id)
                    expected_revision = initial_revision + dataset_revision_deltas.get(group_id, 0)
                    if group is None or group.revision != expected_revision or group.current_version_id != initial_version_id:
                        raise ApiError(409, "TRASH_PREVIEW_STALE", "组资料或版本已变化，请重新预览。")
                    current_group_removal = write.get(LibraryEntryRemoval, ("dataset", group_id))
                    expected_group_members = initial_members - success_assets
                    if current_group_removal is None or set(current_group_removal.member_asset_ids or []) != expected_group_members:
                        raise ApiError(409, "TRASH_PREVIEW_STALE", "组内待清理范围已变化，请重新预览。")
                    live_group_members = set(write.scalars(select(AssetVersion.asset_id).join(
                        DatasetMember, DatasetMember.asset_version_id == AssetVersion.id
                    ).where(DatasetMember.dataset_version_id == initial_version_id)).all()) if initial_version_id else set()
                    if live_group_members != initial_live_members - success_assets:
                        raise ApiError(409, "TRASH_PREVIEW_STALE", "组内成员已变化，请重新预览。")
                    group_version_ids = set(write.scalars(select(DatasetVersion.id).where(DatasetVersion.dataset_id == group_id)).all())
                    group_refs = set(write.scalars(select(ProjectDatasetReference.id).where(
                        ProjectDatasetReference.dataset_version_id.in_(group_version_ids))).all()) if group_version_ids else set()
                    if group_refs != expected_group_references[group_id]:
                        raise ApiError(409, "TRASH_PREVIEW_STALE", "项目组关联已变化，请重新预览。")
                    group_tasks = set(write.scalars(select(AssetTask.id).where(
                        AssetTask.dataset_id == group_id,
                        AssetTask.status.in_({"queued", "running", "cancelling", "interrupted"}),
                    )).all())
                    if not group_tasks.issubset(expected_tasks):
                        raise ApiError(409, "TRASH_PREVIEW_STALE", "组导入任务占用已变化，请重新预览。")
                if not current_refs.issubset(expected_references):
                    raise ApiError(409, "TRASH_PREVIEW_STALE", "项目或组关联已变化，请重新预览。")
                active_task_ids = set(write.scalars(select(AssetTask.id).join(
                    AssetTaskItem, AssetTaskItem.task_id == AssetTask.id
                ).where(AssetTask.status.in_({"queued", "running", "cancelling", "interrupted"}),
                        AssetTaskItem.asset_id == asset_id)).all())
                if not active_task_ids.issubset(expected_tasks):
                    raise ApiError(409, "TRASH_PREVIEW_STALE", "导入任务占用已变化，请重新预览。")
                current_removals = write.scalars(select(LibraryEntryRemoval)).all()
                affected_removals = [removal for removal in current_removals if
                    removal.entry_type == "asset" and removal.entry_id == asset_id or
                    removal.entry_type == "dataset" and removal.entry_id in selected_group_ids and asset_id in (removal.member_asset_ids or [])]
                cleaned = {path for removal in affected_removals for path in (removal.cleaned_paths or [])}
                for path in paths_by_asset.get(asset_id, []):
                    path_key = str(path)
                    if path_key in cleaned:
                        continue
                    if not path.is_file():
                        missing_file_count += 1
                        continue
                    file_size = path.stat().st_size
                    path.unlink()
                    deleted_file_count += 1
                    deleted_bytes += file_size
                    removed_paths.append(path_key)
                    for removal in affected_removals:
                        if path_key in (removal.pending_paths or []) and path_key not in (removal.cleaned_paths or []):
                            removal.cleaned_paths = [*(removal.cleaned_paths or []), path_key]
                            removal.cleanup_status = "partial"
                for version in current_versions:
                    asset = write.get(Asset, asset_id)
                    if asset and asset.current_version_id == version.id:
                        asset.current_version_id = None
                    for ref in write.scalars(select(ProjectAssetReference).where(ProjectAssetReference.asset_version_id == version.id)).all():
                        asset_changed_projects.add(ref.project_id)
                        write.delete(ref)
                    for member in write.scalars(select(DatasetMember).where(DatasetMember.asset_version_id == version.id)).all():
                        dataset_version = write.get(DatasetVersion, member.dataset_version_id)
                        if dataset_version:
                            asset_changed_datasets.add(dataset_version.dataset_id)
                        write.delete(member)
                    write.execute(delete(Preview).where(Preview.asset_version_id == version.id))
                    write.execute(delete(FitsHduMetadata).where(FitsHduMetadata.asset_version_id == version.id))
                for item in write.scalars(select(AssetTaskItem).where(AssetTaskItem.asset_id == asset_id)).all():
                    item.asset_id = None
                    item.asset_version_id = None
                write.execute(delete(AssetVersion).where(AssetVersion.asset_id == asset_id))
                asset = write.get(Asset, asset_id)
                if asset:
                    write.delete(asset)
                asset_removal = write.get(LibraryEntryRemoval, ("asset", asset_id))
                if asset_removal:
                    write.delete(asset_removal)
                for removal in write.scalars(select(LibraryEntryRemoval).where(LibraryEntryRemoval.entry_type == "dataset")).all():
                    if asset_id in (removal.member_asset_ids or []):
                        if removal.entry_id in selected_group_ids:
                            removal.cleaned_asset_ids = list(dict.fromkeys([*(removal.cleaned_asset_ids or []), asset_id]))
                        removal.member_asset_ids = [entry for entry in removal.member_asset_ids if entry != asset_id]
                for project_id in asset_changed_projects:
                    project = write.get(Project, project_id)
                    if project:
                        project.revision += 1
                        project.updated_at = datetime.now(timezone.utc)
                for dataset_id in asset_changed_datasets:
                    dataset = write.get(Dataset, dataset_id)
                    if dataset:
                        dataset.revision += 1
                        dataset.updated_at = datetime.now(timezone.utc)
                write.flush()
            for dataset_id in asset_changed_datasets:
                dataset_revision_deltas[dataset_id] = dataset_revision_deltas.get(dataset_id, 0) + 1
            success_assets.add(asset_id)
        except Exception as exc:
            failed.append({"id": asset_id, "error": str(exc)})
            stale_before_cleanup = isinstance(exc, ApiError) and exc.status_code == 409 and not success_assets and not deleted_file_count
            with request.app.state.database.write_session() as write:
                for removal in write.scalars(select(LibraryEntryRemoval)).all():
                    if removal.entry_type == "asset" and removal.entry_id == asset_id or (
                        removal.entry_type == "dataset" and removal.entry_id in selected_group_ids and asset_id in (removal.member_asset_ids or [])
                    ):
                        removal.cleaned_paths = list(dict.fromkeys([*(removal.cleaned_paths or []), *removed_paths]))
                        removal.cleanup_status = "partial" if removal.cleaned_paths or removal.cleaned_asset_ids else "trash"
                        removal.cleanup_error = str(exc)
                if stale_before_cleanup:
                    for removal, _ in records:
                        current = write.get(LibraryEntryRemoval, (removal.entry_type, removal.entry_id))
                        if current and not current.cleaned_paths:
                            current.cleanup_status = "trash"
                            current.cleanup_error = None
            if stale_before_cleanup:
                raise exc
    for removal, row in records:
        if removal.entry_type == "asset" and row.id in success_assets:
            continue
        if removal.entry_type == "dataset":
            remaining = set(removal.member_asset_ids or []) - success_assets
            if remaining:
                continue
            try:
                with request.app.state.database.write_session() as write:
                    dataset_removal = write.get(LibraryEntryRemoval, ("dataset", row.id))
                    dataset = write.get(Dataset, row.id)
                    original = next(item for item in body.items if item.entry_type == "dataset" and base._id(item.id) == row.id)
                    if dataset and (dataset.revision != original.revision + dataset_revision_deltas.get(row.id, 0) or
                                    dataset.current_version_id != (base._id(original.current_version_id) if original.current_version_id else None)):
                        raise ApiError(409, "TRASH_PREVIEW_STALE", "组版本已变化，请重新预览。")
                    version_rows = write.scalars(select(DatasetVersion).where(DatasetVersion.dataset_id == row.id)).all() if dataset else []
                    current_refs = set(write.scalars(select(ProjectDatasetReference.id).where(ProjectDatasetReference.dataset_id == row.id)).all())
                    if not current_refs.issubset(expected_references):
                        raise ApiError(409, "TRASH_PREVIEW_STALE", "项目关联已变化，请重新预览。")
                    active_task_ids = set(write.scalars(select(AssetTask.id).where(
                        AssetTask.dataset_id == row.id,
                        AssetTask.status.in_({"queued", "running", "cancelling", "interrupted"}),
                    )).all())
                    if not active_task_ids.issubset(expected_tasks):
                        raise ApiError(409, "TRASH_PREVIEW_STALE", "导入任务占用已变化，请重新预览。")
                    if dataset:
                        version_ids = [v.id for v in version_rows]
                        write.execute(delete(DatasetMember).where(DatasetMember.dataset_version_id.in_(version_ids))) if version_ids else None
                        affected_project_ids = set()
                        for reference in write.scalars(select(ProjectDatasetReference).where(ProjectDatasetReference.dataset_id == row.id)).all():
                            affected_project_ids.add(reference.project_id)
                            write.delete(reference)
                        for project_id in affected_project_ids:
                            project = write.get(Project, project_id)
                            if project:
                                project.revision += 1
                                project.updated_at = datetime.now(timezone.utc)
                        dataset.current_version_id = None
                        if dataset_removal:
                            write.delete(dataset_removal)
                        write.flush()
                        for task in write.scalars(select(AssetTask).where(AssetTask.dataset_id == row.id)).all():
                            task.dataset_id = None
                        write.execute(delete(DatasetVersion).where(DatasetVersion.dataset_id == row.id))
                        write.flush()
                        write.delete(dataset)
                    elif dataset_removal:
                        write.delete(dataset_removal)
                success_datasets.add(row.id)
            except Exception as exc:
                failed.append({"id": row.id, "error": str(exc)})
                stale_before_cleanup = isinstance(exc, ApiError) and exc.status_code == 409 and not success_assets and not deleted_file_count
                with request.app.state.database.write_session() as write:
                    dataset_removal = write.get(LibraryEntryRemoval, ("dataset", row.id))
                    if dataset_removal:
                        original_group = next(original for original, _ in records if original.entry_type == "dataset" and original.entry_id == row.id)
                        changed_members = set(dataset_removal.member_asset_ids or []) != set(original_group.member_asset_ids or [])
                        dataset_removal.cleanup_status = "partial" if dataset_removal.cleaned_paths or dataset_removal.cleaned_asset_ids or changed_members else "trash"
                        dataset_removal.cleanup_error = str(exc)
                    if stale_before_cleanup:
                        for selected_removal, _ in records:
                            current = write.get(LibraryEntryRemoval, (selected_removal.entry_type, selected_removal.entry_id))
                            if current and not current.cleaned_paths:
                                current.cleanup_status = "trash"
                                current.cleanup_error = None
                if stale_before_cleanup:
                    raise exc
    return {"deleted_count": len(success_assets), "deleted_entry_count": len(success_assets) + len(success_datasets),
            "deleted_file_count": deleted_file_count, "deleted_bytes": deleted_bytes,
            "missing_file_count": missing_file_count, "failed": failed}


@router.get("/library/filter-options", response_model=LibraryFilterOptions, dependencies=[Depends(base.authenticate)])
def library_filter_options(session: base.ReadSession):
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
    records = [base._asset_out(session, row) for row in assets
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


@router.post("/uploads", status_code=202, dependencies=[Depends(base.authenticate)])
def create_upload(body: UploadImportCreate, request: Request, session: base.WriteSession):
    validate_import_equipment(session, body.parameters.model_dump(mode="json"))
    task_id = str(uuid4())
    staging = request.app.state.settings.data_dir / "upload-staging" / task_id
    staging.mkdir(parents=True, exist_ok=True)
    files = []
    sources = []
    now = base._now()
    for position, file in enumerate(body.files):
        suffix = "".join(Path(file.name).suffixes[-2:]) if file.name.lower().endswith((".fits.fz", ".fit.fz")) else Path(file.name).suffix
        stored_name = f"{position}{suffix.lower()}"
        files.append({"name": file.name, "size": file.size, "received": 0, "stored_name": stored_name})
        sources.append({"root_id": "__upload__", "path": stored_name, "kind": "file", "enumeration_completed": True, "error": None})
        session.add(AssetTaskItem(
            id=str(uuid4()), task_id=task_id, root_item_id=str(uuid4()), retry_of_item_id=None,
            root_id="__upload__", source_path=stored_name, source_identity=f"upload:{task_id}:{position}",
            position=position, status="queued", content_status="pending", metadata_status="pending",
            preview_status="pending", error=None, created_at=now, updated_at=now,
        ))
    create_dataset = body.create_dataset or len(body.files) > 1
    task = AssetTask(
        id=task_id, status="queued", sources=sources, storage_mode="managed",
        classification=body.classification.model_dump(mode="json"), parameters=body.parameters.model_dump(mode="json"),
        notes=body.notes,
        dataset_name=(body.dataset_name or body.files[0].name) if create_dataset else None,
        target_dataset_id=str(uuid4()) if create_dataset else None, dataset_base_revision=None,
        dataset_id=None, enumeration_completed=True, retry_of_task_id=None,
        report={"upload_manifest": True, "upload_files": files}, error=None,
        created_at=now, updated_at=now,
    )
    session.add(task)
    session.flush()
    return {"task_id": UUID(task_id), "status": "queued"}


@router.put("/uploads/{task_id}/{index}", dependencies=[Depends(base.authenticate)])
async def upload_file(task_id: UUID, index: int, request: Request):
    database = request.app.state.database
    with database.read_session() as session:
        task = session.get(AssetTask, base._id(task_id))
        files = (task.report or {}).get("upload_files", []) if task else []
        if task is None or not (task.report or {}).get("upload_manifest") or index < 0 or index >= len(files):
            raise not_found()
        entry = dict(files[index])
        if entry["received"] != 0:
            raise ApiError(409, "UPLOAD_ALREADY_RECEIVED", "该文件已上传；请重新选择文件创建导入批次。")
    target = request.app.state.settings.data_dir / "upload-staging" / base._id(task_id) / entry["stored_name"]
    received = 0
    try:
        with target.open("xb") as stream:
            async for chunk in request.stream():
                stream.write(chunk)
                received += len(chunk)
    except Exception as exc:
        with database.write_session() as session:
            task = session.get(AssetTask, base._id(task_id))
            if task and task.status == "queued":
                task.status = "failed"
                task.error = {"code": "UPLOAD_FAILED", "message": "文件上传中断，请重新选择文件创建导入批次。"}
                task.updated_at = base._now()
                for item in session.scalars(select(AssetTaskItem).where(AssetTaskItem.task_id == task.id)).all():
                    item.status, item.content_status, item.error = "failed", "failed", task.error
                    item.updated_at = base._now()
        shutil.rmtree(request.app.state.settings.data_dir / "upload-staging" / base._id(task_id), ignore_errors=True)
        raise ApiError(400, "UPLOAD_FAILED", "文件上传中断，请重新选择文件创建导入批次。") from exc
    if received != entry["size"]:
        target.unlink(missing_ok=True)
        raise ApiError(400, "UPLOAD_SIZE_MISMATCH", "上传文件大小与选择时记录不一致，请重新选择文件。")
    with database.write_session() as session:
        task = session.get(AssetTask, base._id(task_id))
        files = list((task.report or {}).get("upload_files", []))
        files[index] = {**files[index], "received": received}
        task.report = {**(task.report or {}), "upload_files": files}
        task.updated_at = base._now()
    return {"received": received}


@router.post("/uploads/{task_id}/start", status_code=202, dependencies=[Depends(base.authenticate)])
def start_upload_import(task_id: UUID, request: Request, background: BackgroundTasks, session: base.WriteSession):
    task = session.get(AssetTask, base._id(task_id))
    if task is None or not (task.report or {}).get("upload_manifest"):
        raise not_found()
    if any(file["received"] != file["size"] for file in task.report["upload_files"]):
        raise ApiError(409, "UPLOAD_INCOMPLETE", "所有文件上传完成后才能开始导入。")
    if task.status != "queued":
        raise ApiError(409, "TASK_STATE_CONFLICT", "该上传批次已开始处理。")
    task.report = {**task.report, "upload_complete": True}
    task.updated_at = base._now()
    background.add_task(process_task, request.app.state.database, request.app.state.settings, task.id)
    return {"task_id": UUID(task.id), "status": "queued"}


@router.post("/uploads/{task_id}/fail", dependencies=[Depends(base.authenticate)])
def fail_upload(task_id: UUID, request: Request, session: base.WriteSession):
    task = session.get(AssetTask, base._id(task_id))
    if task is None or not (task.report or {}).get("upload_manifest"):
        raise not_found()
    if task.status != "queued":
        raise ApiError(409, "TASK_STATE_CONFLICT", "后台处理已开始，不能按上传失败取消。")
    task.status = "failed"
    task.error = {"code": "UPLOAD_FAILED", "message": "文件上传未完成，请重新选择文件创建导入批次。"}
    task.updated_at = base._now()
    for item in session.scalars(select(AssetTaskItem).where(AssetTaskItem.task_id == task.id)).all():
        item.status = "failed"
        item.content_status = "failed"
        item.error = task.error
        item.updated_at = base._now()
    shutil.rmtree(request.app.state.settings.data_dir / "upload-staging" / task.id, ignore_errors=True)
    return {"task_id": UUID(task.id), "status": task.status}


def _asset_version_scope(session, project_id: UUID | None, version_id: UUID):
    version = session.get(AssetVersion, base._id(version_id))
    if version is None:
        raise not_found()
    asset = session.get(Asset, version.asset_id)
    if asset is None:
        raise not_found()
    if project_id is None and asset.scope != "shared":
        raise not_found()
    if project_id is not None and asset.scope != "shared" and not (
        asset.scope == "project" and asset.owner_project_id == base._id(project_id)
    ):
        raise not_found()
    return asset, version


def _task_out(session, task: AssetTask, items_limit: int, items_offset: int) -> dict:
    total = session.scalar(
        select(func.count()).select_from(AssetTaskItem).where(AssetTaskItem.task_id == task.id)
    ) or 0
    items = session.scalars(
        select(AssetTaskItem).where(AssetTaskItem.task_id == task.id)
        .order_by(AssetTaskItem.position, AssetTaskItem.id).limit(items_limit).offset(items_offset)
    ).all()
    completed = session.scalar(
        select(func.count()).select_from(AssetTaskItem).where(
            AssetTaskItem.task_id == task.id,
            AssetTaskItem.status.in_({"completed", "completed_with_errors", "failed", "cancelled", "skipped"}),
        )
    ) or 0
    return {
        "id": UUID(task.id), "status": task.status, "sources": task.sources,
        "storage_mode": task.storage_mode, "classification": task.classification,
        "parameters": task.parameters, "notes": task.notes, "dataset_name": task.dataset_name,
        "target_dataset_id": UUID(task.target_dataset_id) if task.target_dataset_id else None,
        "dataset_base_revision": task.dataset_base_revision,
        "dataset_id": UUID(task.dataset_id) if task.dataset_id else None,
        "enumeration_completed": task.enumeration_completed,
        "retry_of_task_id": UUID(task.retry_of_task_id) if task.retry_of_task_id else None,
        "report": task.report or {}, "error": task.error,
        "created_at": base._utc(task.created_at), "updated_at": base._utc(task.updated_at),
        "items": [{
            "id": UUID(row.id), "task_id": UUID(row.task_id), "root_item_id": UUID(row.root_item_id),
            "retry_of_item_id": UUID(row.retry_of_item_id) if row.retry_of_item_id else None,
            "root_id": row.root_id, "source_path": row.source_path, "position": row.position,
            "status": row.status, "content_status": row.content_status,
            "metadata_status": row.metadata_status, "preview_status": row.preview_status,
            "asset_id": UUID(row.asset_id) if row.asset_id else None,
            "asset_version_id": UUID(row.asset_version_id) if row.asset_version_id else None,
            "error": row.error, "created_at": base._utc(row.created_at), "updated_at": base._utc(row.updated_at),
        } for row in items],
        "items_total": total, "items_completed": completed,
        "items_limit": items_limit, "items_offset": items_offset,
    }


def _dataset_out(session, row: Dataset) -> dict:
    member_count = 0
    if row.current_version_id:
        member_count = session.scalar(select(func.count()).select_from(DatasetMember).where(
            DatasetMember.dataset_version_id == row.current_version_id
        )) or 0
    return {
        "id": UUID(row.id), "name": row.name, "notes": row.notes, "status": row.status,
        "revision": row.revision, "current_version_id": UUID(row.current_version_id) if row.current_version_id else None,
        "member_count": member_count,
        "created_at": base._utc(row.created_at), "updated_at": base._utc(row.updated_at),
    }


def _dataset_version_out(session, row: DatasetVersion) -> dict:
    members = session.scalars(
        select(DatasetMember).where(DatasetMember.dataset_version_id == row.id).order_by(DatasetMember.position)
    ).all()
    result = []
    for member in members:
        version = session.get(AssetVersion, member.asset_version_id)
        asset = session.get(Asset, version.asset_id) if version else None
        if asset is not None and version is not None:
            result.append({
                "id": UUID(member.id), "dataset_version_id": UUID(row.id), "asset_version_id": UUID(version.id),
                "position": member.position, "relative_path": member.relative_path,
                "asset": base._asset_out(session, asset), "version": base._version_out(version),
            })
    return {
        "id": UUID(row.id), "dataset_id": UUID(row.dataset_id), "version_number": row.version_number,
        "created_at": base._utc(row.created_at), "members": result,
    }


def _dataset_reference_out(session, row: ProjectDatasetReference) -> dict:
    dataset = session.get(Dataset, row.dataset_id)
    version = session.get(DatasetVersion, row.dataset_version_id)
    if dataset is None or version is None or version.dataset_id != dataset.id:
        raise RuntimeError("项目数据集引用指向无效版本。")
    return {
        "id": UUID(row.id), "project_id": UUID(row.project_id), "dataset_id": UUID(row.dataset_id),
        "dataset_version_id": UUID(row.dataset_version_id), "base_revision": row.base_revision,
        "added_at": base._utc(row.added_at), "dataset": _dataset_out(session, dataset),
        "version": _dataset_version_out(session, version),
    }


def _publish_dataset_version(session, dataset: Dataset, submitted_ids: list[str], relative_paths: dict[str, str | None] | None = None) -> DatasetVersion:
    if len(set(submitted_ids)) != len(submitted_ids):
        raise ApiError(422, "VALIDATION_ERROR", "数据集成员不能重复。", [{"path": "asset_version_ids", "message": "成员版本 ID 不能重复。"}])
    existing = []
    if dataset.current_version_id:
        existing = session.scalars(
            select(DatasetMember).where(DatasetMember.dataset_version_id == dataset.current_version_id)
            .order_by(DatasetMember.position)
        ).all()
    old_ids = [member.asset_version_id for member in existing]
    submitted_old = [value for value in submitted_ids if value in set(old_ids)]
    retained_old = [value for value in old_ids if value in set(submitted_ids)]
    if retained_old != submitted_old:
        raise ApiError(422, "VALIDATION_ERROR", "已有成员必须保留原有相对顺序，新成员只能追加。", [{"path": "asset_version_ids", "message": "不得重排已有成员。"}])
    additions = [value for value in submitted_ids if value not in set(old_ids)]
    if submitted_ids != retained_old + additions:
        raise ApiError(422, "VALIDATION_ERROR", "新成员必须追加到保留成员之后。", [{"path": "asset_version_ids", "message": "新成员只能追加。"}])
    for version_id in additions:
        asset, _ = _asset_version_scope(session, None, UUID(version_id))
        if asset.scope != "shared":
            raise invalid_reference("共享数据集只能包含共享资产。")
    if dataset.current_version_id and submitted_ids == old_ids:
        return session.get(DatasetVersion, dataset.current_version_id)
    latest_number = session.scalar(select(func.max(DatasetVersion.version_number)).where(DatasetVersion.dataset_id == dataset.id)) or 0
    version = DatasetVersion(id=str(uuid4()), dataset_id=dataset.id, version_number=latest_number + 1)
    session.add(version)
    session.flush()
    path_map = relative_paths or {}
    retained = {member.asset_version_id: member.relative_path for member in existing}
    for position, asset_version_id in enumerate(submitted_ids):
        relative = retained.get(asset_version_id) if asset_version_id in retained else path_map.get(asset_version_id)
        session.add(DatasetMember(
            id=str(uuid4()), dataset_version_id=version.id, asset_version_id=asset_version_id,
            position=position, relative_path=relative,
        ))
    dataset.current_version_id = version.id
    dataset.revision += 1
    dataset.updated_at = base._now()
    session.flush()
    return version


def _update_project_revision(session, project: Project, revision: int) -> None:
    result = session.execute(
        update(Project).where(Project.id == project.id, Project.revision == revision)
        .values(revision=revision + 1, updated_at=base._now())
    )
    if result.rowcount != 1:
        base._conflict_or_missing(session, Project, project.id)


@router.get("/import-roots", response_model=list[ImportRootOut], dependencies=[Depends(base.authenticate)])
def import_roots(request: Request):
    result = []
    for root in request.app.state.settings.import_roots:
        try:
            available = root.path.resolve(strict=True).is_dir()
        except OSError:
            available = False
        result.append({"id": root.id, "label": root.path.name or root.id, "available": available})
    return result


@router.get("/import-roots/{root_id}/entries", response_model=ImportRootEntryPage, dependencies=[Depends(base.authenticate)])
def import_root_entries(
    root_id: str, request: Request, path: str = "", limit: base.Limit = 100,
    offset: base.Offset = 0, q: str | None = None,
):
    return entries_page(request.app.state.settings, root_id, path, limit, offset, q)


@router.post("/imports", response_model=ImportAccepted, status_code=202, dependencies=[Depends(base.authenticate)])
def create_import(body: ImportCreate, request: Request, background: BackgroundTasks, session: base.WriteSession):
    validate_import_equipment(session, body.parameters.model_dump(mode="json"))
    sources = []
    is_dataset = len(body.sources) > 1
    for source in body.sources:
        _, root = find_root(request.app.state.settings, source.root_id)
        selected = resolve_relative(root, source.path, allow_empty=True)
        kind = "directory" if selected.is_dir() else "file"
        if kind == "directory":
            is_dataset = True
        data_root = request.app.state.settings.data_dir.resolve()
        try:
            data_root.relative_to(root)
        except ValueError:
            pass
        else:
            raise ApiError(422, "VALIDATION_ERROR", "素材根目录不能包含 AstroPhotoFlow 数据目录。")
        sources.append({
            "root_id": source.root_id, "path": source.path, "kind": kind,
            "enumeration_completed": False, "error": None,
        })
    task_id = str(uuid4())
    target_dataset_id = str(uuid4()) if is_dataset else None
    dataset_name = body.dataset_name
    if is_dataset and not dataset_name:
        primary = sources[0]
        dataset_name = Path(primary["path"].rstrip("/")).name or next(
            (root.path.name for root in request.app.state.settings.import_roots if root.id == primary["root_id"]), "素材集"
        )
    task = AssetTask(
        id=task_id, status="queued", sources=sources, storage_mode=body.storage_mode,
        classification=body.classification.model_dump(mode="json"),
        parameters=body.parameters.model_dump(mode="json"), notes=body.notes, dataset_name=dataset_name,
        target_dataset_id=target_dataset_id, dataset_base_revision=None, dataset_id=None,
        enumeration_completed=False, retry_of_task_id=None, report={}, error=None,
        created_at=base._now(), updated_at=base._now(),
    )
    session.add(task)
    session.flush()
    background.add_task(process_task, request.app.state.database, request.app.state.settings, task_id)
    return {"task_id": UUID(task_id), "status": "queued"}


@router.get("/asset-tasks", response_model=AssetTaskPage, dependencies=[Depends(base.authenticate)])
def list_asset_tasks(
    session: base.ReadSession, limit: base.Limit = 50, offset: base.Offset = 0,
    status: Literal["queued", "running", "cancelling", "completed", "completed_with_errors", "failed", "cancelled", "interrupted", "all"] = "all",
):
    filters = [] if status == "all" else [AssetTask.status == status]
    total = session.scalar(select(func.count()).select_from(AssetTask).where(*filters)) or 0
    rows = session.scalars(
        select(AssetTask).where(*filters).order_by(AssetTask.created_at.desc(), AssetTask.id).limit(limit).offset(offset)
    ).all()
    return {"items": [_task_out(session, task, 20, 0) for task in rows], "total": total, "limit": limit, "offset": offset}


@router.get("/asset-tasks/{task_id}", response_model=AssetTaskOut, dependencies=[Depends(base.authenticate)])
def get_asset_task(
    task_id: UUID, session: base.ReadSession,
    items_limit: Annotated[int, Query(ge=1, le=200)] = 50,
    items_offset: Annotated[int, Query(ge=0)] = 0,
):
    task = session.get(AssetTask, base._id(task_id))
    if task is None:
        raise not_found()
    return _task_out(session, task, items_limit, items_offset)


@router.post("/asset-tasks/{task_id}/cancel", status_code=202, dependencies=[Depends(base.authenticate)])
def cancel_asset_task(task_id: UUID, request: Request, session: base.WriteSession):
    task = session.get(AssetTask, base._id(task_id))
    if task is None:
        raise not_found()
    if task.status not in {"queued", "running", "cancelling", "interrupted"}:
        raise ApiError(409, "TASK_STATE_CONFLICT", "当前任务状态不能取消。")
    task.status = "cancelling" if task.status in {"running", "cancelling"} else "cancelled"
    task.updated_at = base._now()
    if task.status == "cancelled":
        for item in session.scalars(select(AssetTaskItem).where(
            AssetTaskItem.task_id == task.id, AssetTaskItem.status.in_({"queued", "interrupted", "running"})
        )).all():
            item.status = "cancelled"
            item.updated_at = base._now()
    return {"task_id": UUID(task.id), "status": task.status}


@router.post("/asset-tasks/{task_id}/resume", status_code=202, response_model=ImportAccepted, dependencies=[Depends(base.authenticate)])
def resume_asset_task(task_id: UUID, request: Request, background: BackgroundTasks, session: base.WriteSession):
    task = session.get(AssetTask, base._id(task_id))
    if task is None:
        raise not_found()
    if task.status != "interrupted":
        raise ApiError(409, "TASK_STATE_CONFLICT", "只有服务中断的任务可恢复。")
    if (task.report or {}).get("upload_manifest") and not (task.report or {}).get("upload_complete"):
        raise ApiError(409, "UPLOAD_REQUIRES_SELECTION", "上传未完成，请重新选择文件并创建导入批次。")
    task.status = "queued"
    task.error = None
    task.updated_at = base._now()
    for item in session.scalars(select(AssetTaskItem).where(
        AssetTaskItem.task_id == task.id, AssetTaskItem.status == "interrupted"
    )).all():
        item.status = "queued"
        item.updated_at = base._now()
    background.add_task(process_task, request.app.state.database, request.app.state.settings, task.id)
    return {"task_id": UUID(task.id), "status": "queued"}


@router.post("/asset-tasks/{task_id}/retry", status_code=202, response_model=ImportAccepted, dependencies=[Depends(base.authenticate)])
def retry_asset_task(task_id: UUID, body: RetryCreate, request: Request, background: BackgroundTasks, session: base.WriteSession):
    original = session.get(AssetTask, base._id(task_id))
    if original is None:
        raise not_found()
    if original.status not in {"failed", "completed_with_errors", "cancelled"}:
        raise ApiError(409, "TASK_STATE_CONFLICT", "当前任务状态不能重试。")
    selected_ids = [base._id(value) for value in body.item_ids]
    if len(set(selected_ids)) != len(selected_ids):
        raise ApiError(422, "VALIDATION_ERROR", "重试项不能重复。")
    items = session.scalars(select(AssetTaskItem).where(
        AssetTaskItem.task_id == original.id, AssetTaskItem.id.in_(selected_ids)
    ).order_by(AssetTaskItem.position)).all()
    if len(items) != len(selected_ids):
        raise not_found()
    if any(item.status == "skipped" or not (
        item.content_status in {"pending", "failed"} or item.metadata_status == "failed" or item.preview_status == "failed"
    ) for item in items):
        raise ApiError(422, "VALIDATION_ERROR", "所选项没有失败或未完成阶段，不能重试。")
    source_task = session.get(AssetTask, original.retry_of_task_id) if original.retry_of_task_id else original
    retry_task_id = str(uuid4())
    target_dataset_id = source_task.target_dataset_id
    dataset = session.get(Dataset, target_dataset_id) if target_dataset_id else None
    retry_task = AssetTask(
        id=retry_task_id, status="queued",
        sources=[{"root_id": item.root_id, "path": item.source_path, "kind": "file", "enumeration_completed": True, "error": None} for item in items],
        storage_mode=source_task.storage_mode, classification=source_task.classification,
        parameters=source_task.parameters, notes=source_task.notes, dataset_name=source_task.dataset_name,
        target_dataset_id=target_dataset_id, dataset_base_revision=dataset.revision if dataset else None,
        dataset_id=source_task.dataset_id, enumeration_completed=True, retry_of_task_id=original.id,
        report={
            "upload_manifest": bool((source_task.report or {}).get("upload_manifest")),
            "upload_complete": bool((source_task.report or {}).get("upload_complete")),
            "upload_source_task_id": (source_task.report or {}).get("upload_source_task_id", source_task.id),
            "upload_files": (source_task.report or {}).get("upload_files", []),
        }, error=None, created_at=base._now(), updated_at=base._now(),
    )
    session.add(retry_task)
    session.flush()
    for position, item in enumerate(items):
        source_item = session.get(AssetTaskItem, item.retry_of_item_id) if item.retry_of_item_id else item
        root_item = source_item.root_item_id if source_item else item.root_item_id
        session.add(AssetTaskItem(
            id=str(uuid4()), task_id=retry_task_id, root_item_id=root_item, retry_of_item_id=item.id,
            root_id=item.root_id, source_path=item.source_path, source_identity=item.source_identity,
            position=position, status="queued", content_status=item.content_status,
            metadata_status=item.metadata_status, preview_status=item.preview_status,
            asset_id=item.asset_id, asset_version_id=item.asset_version_id, error=None,
            created_at=base._now(), updated_at=base._now(),
        ))
    session.flush()
    background.add_task(process_task, request.app.state.database, request.app.state.settings, retry_task_id)
    return {"task_id": UUID(retry_task_id), "status": "queued"}



@router.get("/library/assets/{asset_id}", response_model=AssetOut, dependencies=[Depends(base.authenticate)])
def get_asset(asset_id: UUID, session: base.ReadSession):
    row = session.get(Asset, base._id(asset_id))
    if row is None or row.scope != "shared":
        raise not_found()
    return base._asset_out(session, row)


@router.patch("/library/assets/{asset_id}", response_model=AssetOut, dependencies=[Depends(base.authenticate)])
def patch_asset(asset_id: UUID, body: AssetPatch, session: base.WriteSession):
    asset_id_text = base._id(asset_id)
    asset = session.get(Asset, asset_id_text)
    if asset is None or asset.scope != "shared":
        raise not_found()
    changes = body.model_dump(exclude_unset=True, exclude={"base_revision", "classification", "parameters"})
    base._assert_patch_values(changes, {"name", "status"})
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
                base._check_equipment_ref(session, parameters[key], kind, f"parameters.{key}")
        changes["parameters"] = parameters
    if body.classification is not None or body.parameters is not None:
        changes["value_sources"] = value_sources
    result = session.execute(update(Asset).where(
        Asset.id == asset_id_text, Asset.revision == body.base_revision
    ).values(**changes, revision=body.base_revision + 1))
    if result.rowcount != 1:
        base._conflict_or_missing(session, Asset, asset_id_text)
    session.flush()
    session.expire_all()
    return base._asset_out(session, session.get(Asset, asset_id_text))


@router.get("/library/assets/{asset_id}/versions", response_model=AssetVersionPage, dependencies=[Depends(base.authenticate)])
def list_asset_versions(asset_id: UUID, session: base.ReadSession, limit: base.Limit = 50, offset: base.Offset = 0):
    asset = session.get(Asset, base._id(asset_id))
    if asset is None or asset.scope != "shared":
        raise not_found()
    total = session.scalar(select(func.count()).select_from(AssetVersion).where(AssetVersion.asset_id == asset.id)) or 0
    rows = session.scalars(select(AssetVersion).where(AssetVersion.asset_id == asset.id)
        .order_by(AssetVersion.version_number.desc()).limit(limit).offset(offset)).all()
    return base._page([base._version_out(row) for row in rows], total, limit, offset)


@router.get("/library/assets/{asset_id}/versions/{version_id}", response_model=AssetVersionOut, dependencies=[Depends(base.authenticate)])
def get_asset_version(asset_id: UUID, version_id: UUID, session: base.ReadSession):
    asset, version = _asset_version_scope(session, None, version_id)
    if asset.id != base._id(asset_id):
        raise not_found()
    return base._version_out(version)


@router.get("/library/assets/{asset_id}/versions/{version_id}/hdus", response_model=FitsHduPage, dependencies=[Depends(base.authenticate)])
def list_version_hdus(asset_id: UUID, version_id: UUID, session: base.ReadSession, limit: base.Limit = 200, offset: base.Offset = 0):
    asset, version = _asset_version_scope(session, None, version_id)
    if asset.id != base._id(asset_id):
        raise not_found()
    total = session.scalar(select(func.count()).select_from(FitsHduMetadata).where(FitsHduMetadata.asset_version_id == version.id)) or 0
    rows = session.scalars(select(FitsHduMetadata).where(FitsHduMetadata.asset_version_id == version.id)
        .order_by(FitsHduMetadata.hdu_index).limit(limit).offset(offset)).all()
    return base._page([_fits_hdu_out(row) for row in rows], total, limit, offset)


def _header_out(version: AssetVersion, hdu: FitsHduMetadata) -> dict:
    cards = [{"keyword": card["keyword"], "value": card.get("value"), "comment": card.get("comment")} for card in hdu.header_cards]
    return {"asset_version_id": UUID(version.id), "hdu_index": hdu.hdu_index, "cards": cards}


def _fits_hdu_out(row: FitsHduMetadata) -> dict:
    return FitsHduOut(
        id=UUID(row.id), asset_version_id=UUID(row.asset_version_id), hdu_index=row.hdu_index,
        name=row.name, hdu_type=row.hdu_type, shape=row.shape, bitpix=row.bitpix,
        pixel_type=row.pixel_type, bscale=row.bscale, bzero=row.bzero, bunit=row.bunit,
        parser_version=row.parser_version, supported_kind=row.supported_kind,
        is_selected=row.is_selected, parse_error=row.parse_error,
    ).model_dump()


def _read_preview(request: Request, version_id: str, hdu_index: int | None, size: str) -> Response:
    if size not in {"thumbnail", "detail"} or hdu_index is None:
        raise not_found()
    with request.app.state.database.read_session() as session:
        preview = session.scalar(select(Preview).where(
            Preview.asset_version_id == version_id, Preview.hdu_index == hdu_index,
            Preview.size == size, Preview.status == "available",
        ).order_by(Preview.created_at.desc()).limit(1))
        if preview is None:
            raise not_found()
        relative = Path(preview.storage_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise not_found()
        root = request.app.state.settings.data_dir.resolve()
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
            content = path.read_bytes()
        except (OSError, ValueError) as exc:
            raise not_found() from exc
        return Response(content, media_type=preview.mime_type, headers={"Cache-Control": "private, max-age=0"})


@router.get("/library/assets/{asset_id}/versions/{version_id}/hdus/{hdu_index}/header", response_model=FitsHeaderOut, dependencies=[Depends(base.authenticate)])
def get_version_header(asset_id: UUID, version_id: UUID, hdu_index: int, session: base.ReadSession):
    asset, version = _asset_version_scope(session, None, version_id)
    if asset.id != base._id(asset_id):
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
    dependencies=[Depends(base.authenticate)],
)
def get_version_preview(asset_id: UUID, version_id: UUID, size: str, request: Request, session: base.ReadSession):
    asset, version = _asset_version_scope(session, None, version_id)
    if asset.id != base._id(asset_id):
        raise not_found()
    selected = session.scalar(select(FitsHduMetadata.hdu_index).where(
        FitsHduMetadata.asset_version_id == version.id, FitsHduMetadata.is_selected.is_(True)
    ))
    if selected is None and (version.scientific_metadata or {}).get("format") in {"image", "video"}:
        selected = 0
    return _read_preview(request, version.id, selected, size)


@router.get(
    "/projects/{project_id}/asset-references/{reference_id}/previews/{size}",
    responses={200: {"content": {"image/jpeg": {"schema": {"type": "string", "format": "binary"}}}}},
    dependencies=[Depends(base.authenticate)],
)
def get_project_reference_preview(project_id: UUID, reference_id: UUID, size: str, request: Request, session: base.ReadSession):
    reference = session.get(ProjectAssetReference, base._id(reference_id))
    if reference is None or reference.project_id != base._id(project_id):
        raise not_found()
    asset, version = _asset_version_scope(session, project_id, UUID(reference.asset_version_id))
    if asset.id != version.asset_id:
        raise not_found()
    selected = session.scalar(select(FitsHduMetadata.hdu_index).where(
        FitsHduMetadata.asset_version_id == version.id, FitsHduMetadata.is_selected.is_(True)
    ))
    if selected is None and (version.scientific_metadata or {}).get("format") in {"image", "video"}:
        selected = 0
    return _read_preview(request, version.id, selected, size)



@router.get("/datasets", response_model=DatasetPage, dependencies=[Depends(base.authenticate)])
def list_datasets(
    session: base.ReadSession, limit: base.Limit = 50, offset: base.Offset = 0,
    sort_by: base.SortBy = "created_at", order: base.Order = "desc", q: str | None = None,
    status: Literal["active", "archived", "all"] = "active",
):
    filters = [] if status == "all" else [Dataset.status == status]
    if q:
        filters.append(Dataset.name.contains(q, autoescape=True))
    total = session.scalar(select(func.count()).select_from(Dataset).where(*filters)) or 0
    column = Dataset.name if sort_by == "name" else Dataset.created_at
    rows = session.scalars(select(Dataset).where(*filters)
        .order_by(column.desc() if order == "desc" else column.asc(), Dataset.id.asc())
        .limit(limit).offset(offset)).all()
    return base._page([_dataset_out(session, row) for row in rows], total, limit, offset)


@router.get("/datasets/{dataset_id}", response_model=DatasetOut, dependencies=[Depends(base.authenticate)])
def get_dataset(dataset_id: UUID, session: base.ReadSession):
    dataset = session.get(Dataset, base._id(dataset_id))
    if dataset is None:
        raise not_found()
    return _dataset_out(session, dataset)


@router.patch("/datasets/{dataset_id}", response_model=DatasetOut, dependencies=[Depends(base.authenticate)])
def patch_dataset(dataset_id: UUID, body: DatasetPatch, session: base.WriteSession):
    dataset_id_text = base._id(dataset_id)
    changes = body.model_dump(exclude_unset=True, exclude={"base_revision"})
    base._assert_patch_values(changes, {"name", "status"})
    result = session.execute(update(Dataset).where(
        Dataset.id == dataset_id_text, Dataset.revision == body.base_revision
    ).values(**changes, revision=body.base_revision + 1, updated_at=base._now()))
    if result.rowcount != 1:
        base._conflict_or_missing(session, Dataset, dataset_id_text)
    session.flush()
    session.expire_all()
    return _dataset_out(session, session.get(Dataset, dataset_id_text))


@router.get("/datasets/{dataset_id}/versions", response_model=DatasetVersionPage, dependencies=[Depends(base.authenticate)])
def list_dataset_versions(dataset_id: UUID, session: base.ReadSession, limit: base.Limit = 50, offset: base.Offset = 0):
    dataset = session.get(Dataset, base._id(dataset_id))
    if dataset is None:
        raise not_found()
    total = session.scalar(select(func.count()).select_from(DatasetVersion).where(DatasetVersion.dataset_id == dataset.id)) or 0
    rows = session.scalars(select(DatasetVersion).where(DatasetVersion.dataset_id == dataset.id)
        .order_by(DatasetVersion.version_number.desc()).limit(limit).offset(offset)).all()
    return base._page([_dataset_version_out(session, row) for row in rows], total, limit, offset)


@router.get("/datasets/{dataset_id}/versions/{version_id}", response_model=DatasetVersionOut, dependencies=[Depends(base.authenticate)])
def get_dataset_version(dataset_id: UUID, version_id: UUID, session: base.ReadSession):
    dataset = session.get(Dataset, base._id(dataset_id))
    version = session.get(DatasetVersion, base._id(version_id))
    if dataset is None or version is None or version.dataset_id != dataset.id:
        raise not_found()
    return _dataset_version_out(session, version)


@router.patch("/datasets/{dataset_id}/member-parameters", response_model=DatasetMemberParametersUpdateOut, dependencies=[Depends(base.authenticate)])
def update_dataset_member_parameters(
    dataset_id: UUID, body: DatasetMemberParametersUpdate, session: base.WriteSession,
):
    dataset = session.get(Dataset, base._id(dataset_id))
    if dataset is None:
        raise not_found()
    if dataset.revision != body.base_revision or dataset.current_version_id != base._id(body.base_version_id):
        raise ApiError(409, "REVISION_CONFLICT", "数据集成员已变化，请重新读取后保存。")
    members = session.scalars(
        select(DatasetMember).where(DatasetMember.dataset_version_id == dataset.current_version_id)
        .order_by(DatasetMember.position)
    ).all()
    asset_by_id = {}
    for member in members:
        version = session.get(AssetVersion, member.asset_version_id)
        if version is None:
            raise ApiError(409, "REVISION_CONFLICT", "数据集成员版本已变化，请重新读取后保存。")
        asset_by_id[version.asset_id] = session.get(Asset, version.asset_id)
    submitted = {base._id(item.asset_id): item.revision for item in body.members}
    if set(submitted) != set(asset_by_id):
        raise ApiError(409, "REVISION_CONFLICT", "数据集成员已变化，请重新读取后保存。")
    for asset_id, asset in asset_by_id.items():
        if asset is None or asset.revision != submitted[asset_id]:
            raise ApiError(409, "REVISION_CONFLICT", "素材资料已变化，请重新读取后保存。")

    parameter_patch = body.parameters.model_dump(exclude_unset=True, mode="json") if body.parameters is not None else {}
    classification_patch = body.classification.model_dump(exclude_unset=True, mode="json") if body.classification is not None else {}
    updated = []
    for asset_id, asset in asset_by_id.items():
        if parameter_patch:
            values = dict(asset.parameters or {})
            values.update(parameter_patch)
            try:
                asset.parameters = AssetParameters.model_validate(values).model_dump(mode="json")
            except Exception as exc:
                raise ApiError(422, "VALIDATION_ERROR", "拍摄参数无效。", [{"path": "parameters", "message": "请检查参数值及设备 ID。"}]) from exc
            for key, kind in (("camera_id", "camera"), ("optical_system_id", "optical_system"), ("filter_id", "filter")):
                if asset.parameters.get(key) is not None:
                    base._check_equipment_ref(session, asset.parameters[key], kind, f"parameters.{key}")
        if classification_patch:
            classification = {**(asset.classification or {}), **classification_patch}
            if classification.get("frame_class") == "video":
                classification["frame_type"] = None
            try:
                asset.classification = AssetClassification.model_validate(classification).model_dump(mode="json")
            except Exception as exc:
                raise ApiError(422, "VALIDATION_ERROR", "素材分类无效。", [{"path": "classification", "message": "请检查素材形态与帧用途。"}]) from exc
            asset.role = "calibration" if asset.classification.get("frame_type") in {"bias", "dark", "flat", "dark_flat"} else "raw"
        asset.value_sources = {
            **(asset.value_sources or {}),
            **{key: "manual" for key in parameter_patch},
            **{f"classification.{key}": "manual" for key in classification_patch},
        }
        asset.revision += 1
        asset.updated_at = base._now()
        updated.append(base._asset_out(session, asset))
    return {
        "dataset_id": UUID(dataset.id), "revision": dataset.revision,
        "version_id": UUID(dataset.current_version_id), "assets": updated,
    }


@router.post("/datasets/{dataset_id}/versions", response_model=DatasetVersionOut, status_code=201, dependencies=[Depends(base.authenticate)])
def create_dataset_version(
    dataset_id: UUID, body: DatasetMembersCreate, session: base.WriteSession,
):
    dataset_id_text = base._id(dataset_id)
    dataset = session.get(Dataset, dataset_id_text)
    if dataset is None:
        raise not_found()
    if dataset.revision != body.base_revision:
        raise ApiError(409, "REVISION_CONFLICT", "数据集已在其他窗口修改，请重新读取后保存。")
    ids = [base._id(value) for value in body.asset_version_ids]
    relative_paths = {}
    if ids:
        source_rows = session.execute(
            select(AssetTaskItem.asset_version_id, AssetTaskItem.source_path)
            .where(AssetTaskItem.asset_version_id.in_(ids))
            .order_by(AssetTaskItem.created_at, AssetTaskItem.id)
        ).all()
        for version_id, source_path in source_rows:
            relative_paths.setdefault(version_id, source_path)
    version = _publish_dataset_version(session, dataset, ids, relative_paths)
    return _dataset_version_out(session, version)


@router.get("/projects/{project_id}/dataset-references", response_model=ProjectDatasetReferencePage, dependencies=[Depends(base.authenticate)])
def list_project_dataset_references(
    project_id: UUID, session: base.ReadSession, limit: base.Limit = 50, offset: base.Offset = 0,
    sort_by: base.SortBy = "created_at", order: base.Order = "desc",
):
    project = session.get(Project, base._id(project_id))
    if project is None:
        raise not_found()
    total = session.scalar(select(func.count()).select_from(ProjectDatasetReference)
        .where(ProjectDatasetReference.project_id == project.id)) or 0
    column = ProjectDatasetReference.added_at
    rows = session.scalars(select(ProjectDatasetReference)
        .where(ProjectDatasetReference.project_id == project.id)
        .order_by(column.desc() if order == "desc" else column.asc(), ProjectDatasetReference.id.asc())
        .limit(limit).offset(offset)).all()
    return base._page([_dataset_reference_out(session, row) for row in rows], total, limit, offset)


@router.get("/projects/{project_id}/datasets", response_model=ProjectDatasetReferencePage, dependencies=[Depends(base.authenticate)])
def list_project_datasets(
    project_id: UUID, session: base.ReadSession, limit: base.Limit = 50, offset: base.Offset = 0,
):
    return list_project_dataset_references(project_id, session, limit, offset)


@router.post("/projects/{project_id}/dataset-references", response_model=ProjectDatasetReferenceOut, status_code=201, dependencies=[Depends(base.authenticate)])
def add_project_dataset_reference(project_id: UUID, body: ProjectDatasetReferenceCreate, session: base.WriteSession):
    project_id_text = base._id(project_id)
    project = session.get(Project, project_id_text)
    if project is None:
        raise not_found()
    dataset = session.get(Dataset, base._id(body.dataset_id))
    version = session.get(DatasetVersion, base._id(body.dataset_version_id))
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
        dataset_version_id=version.id, base_revision=body.base_revision + 1, added_at=base._now(),
    )
    session.add(reference)
    session.flush()
    session.expire_all()
    return _dataset_reference_out(session, session.get(ProjectDatasetReference, reference.id))


@router.get("/projects/{project_id}/dataset-references/{reference_id}", response_model=ProjectDatasetReferenceOut, dependencies=[Depends(base.authenticate)])
def get_project_dataset_reference(project_id: UUID, reference_id: UUID, session: base.ReadSession):
    project = session.get(Project, base._id(project_id))
    row = session.get(ProjectDatasetReference, base._id(reference_id))
    if project is None or row is None or row.project_id != project.id:
        raise not_found()
    return _dataset_reference_out(session, row)


@router.delete("/projects/{project_id}/dataset-references/{reference_id}", response_model=dict, dependencies=[Depends(base.authenticate)])
def remove_project_dataset_reference(
    project_id: UUID, reference_id: UUID, body: ProjectReferenceDelete, session: base.WriteSession,
):
    project_id_text, reference_id_text = base._id(project_id), base._id(reference_id)
    project = session.get(Project, project_id_text)
    reference = session.get(ProjectDatasetReference, reference_id_text)
    if project is None or reference is None or reference.project_id != project_id_text:
        raise not_found()
    _update_project_revision(session, project, body.base_revision)
    session.delete(reference)
    session.flush()
    return {"deleted_id": reference_id_text, "revision": body.base_revision + 1}


@router.post("/projects/{project_id}/asset-references", response_model=ProjectAssetReferenceOut, status_code=201, dependencies=[Depends(base.authenticate)])
def add_project_asset_reference(project_id: UUID, body: ProjectReferenceCreate, session: base.WriteSession):
    project_id_text = base._id(project_id)
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
        id=str(uuid4()), project_id=project_id_text, asset_version_id=version.id, added_at=base._now()
    )
    session.add(reference)
    session.flush()
    session.expire_all()
    return base._reference_out(session, session.get(ProjectAssetReference, reference.id), asset, version)


@router.delete("/projects/{project_id}/asset-references/{reference_id}", response_model=dict, dependencies=[Depends(base.authenticate)])
def remove_project_asset_reference(
    project_id: UUID, reference_id: UUID, body: ProjectReferenceDelete, session: base.WriteSession,
):
    project_id_text, reference_id_text = base._id(project_id), base._id(reference_id)
    project = session.get(Project, project_id_text)
    reference = session.get(ProjectAssetReference, reference_id_text)
    if project is None or reference is None or reference.project_id != project_id_text:
        raise not_found()
    _update_project_revision(session, project, body.base_revision)
    session.delete(reference)
    session.flush()
    return {"deleted_id": reference_id_text, "revision": body.base_revision + 1}


def register_stage2(app) -> None:
    app.include_router(router)



def _require_project_reference(session, project_id: UUID, reference_id: UUID, version_id: UUID | None = None):
    reference = session.get(ProjectAssetReference, base._id(reference_id))
    if reference is None or reference.project_id != base._id(project_id):
        raise not_found()
    if version_id is not None and reference.asset_version_id != base._id(version_id):
        raise not_found()
    asset, version = _asset_version_scope(session, project_id, UUID(reference.asset_version_id))
    return asset, version


@router.get(
    "/projects/{project_id}/asset-references/{reference_id}/versions/{version_id}/hdus",
    response_model=FitsHduPage, dependencies=[Depends(base.authenticate)],
)
def list_project_reference_hdus(
    project_id: UUID, reference_id: UUID, version_id: UUID, session: base.ReadSession,
    limit: base.Limit = 200, offset: base.Offset = 0,
):
    _, version = _require_project_reference(session, project_id, reference_id, version_id)
    total = session.scalar(select(func.count()).select_from(FitsHduMetadata).where(FitsHduMetadata.asset_version_id == version.id)) or 0
    rows = session.scalars(select(FitsHduMetadata).where(FitsHduMetadata.asset_version_id == version.id)
        .order_by(FitsHduMetadata.hdu_index).limit(limit).offset(offset)).all()
    return base._page([_fits_hdu_out(row) for row in rows], total, limit, offset)


@router.get(
    "/projects/{project_id}/asset-references/{reference_id}/versions/{version_id}/hdus/{hdu_index}/header",
    response_model=FitsHeaderOut, dependencies=[Depends(base.authenticate)],
)
def get_project_reference_header(
    project_id: UUID, reference_id: UUID, version_id: UUID, hdu_index: int, session: base.ReadSession,
):
    _, version = _require_project_reference(session, project_id, reference_id, version_id)
    hdu = session.scalar(select(FitsHduMetadata).where(
        FitsHduMetadata.asset_version_id == version.id, FitsHduMetadata.hdu_index == hdu_index,
    ))
    if hdu is None:
        raise not_found()
    return _header_out(version, hdu)
