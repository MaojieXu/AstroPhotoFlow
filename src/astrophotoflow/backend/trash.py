from __future__ import annotations
from fastapi import APIRouter

from .dependencies import ERROR_RESPONSES
from . import dependencies as deps
from . import common as shared

import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID
from fastapi import Depends, Request
from sqlalchemy import delete, func, select
from .errors import ApiError, not_found
from .previews import assert_no_preview_jobs, owned_preview_locations
from .models import Asset, AssetTask, AssetTaskItem, AssetVersion, Dataset, DatasetMember, DatasetVersion, FitsHduMetadata, Preview, Project, ProjectAssetReference, ProjectDatasetReference, LibraryEntryRemoval
from pathlib import Path
from .import_schemas import LibraryEntriesRemove, LibraryTrashDelete, LibraryTrashSelection
from .schemas import LibraryEntriesRemoveOut, LibraryTrashPage, LibraryTrashItemOut, LibraryTrashPreviewOut, LibraryTrashDeleteOut
from .calibration import calibration_references, protect_calibration_targets


router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)


@router.delete("/library/items", response_model=LibraryEntriesRemoveOut, dependencies=[Depends(deps.authenticate)])
def remove_library_entries(body: LibraryEntriesRemove, session: deps.WriteSession):
    removals = set(session.execute(select(LibraryEntryRemoval.entry_type, LibraryEntryRemoval.entry_id)).all())
    checked = []
    for item in body.items:
        record_id = shared._id(item.id)
        if item.entry_type == "asset":
            record = session.get(Asset, record_id)
            if record is None or record.scope != "shared" or record.status != "active":
                raise not_found()
            if record.revision != item.revision:
                shared._conflict_or_missing(session, Asset, record_id)
        else:
            record = session.get(Dataset, record_id)
            if record is None or record.status != "active":
                raise not_found()
            if record.revision != item.revision:
                shared._conflict_or_missing(session, Dataset, record_id)
            if record.current_version_id != (shared._id(item.current_version_id) if item.current_version_id else None):
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


def _trash_cleanup_status(session, removal: LibraryEntryRemoval) -> str:
    if removal.cleaned_paths or removal.cleaned_asset_ids:
        return "partial"
    if removal.entry_type == "dataset":
        for asset_id in removal.member_asset_ids or []:
            child = session.get(LibraryEntryRemoval, ("asset", asset_id))
            if child is not None and _trash_cleanup_status(session, child) == "partial":
                return "partial"
    elif any(not Path(path).is_file() for path in (removal.pending_paths or [])):
        return "partial"
    return "trash"


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
        entry_type=removal.entry_type, id=UUID(removal.entry_id), name=name, removed_at=shared._utc(removal.removed_at),
        revision=revision, current_version_id=UUID(current_version_id) if current_version_id else None, cleanup_status=_trash_cleanup_status(session, removal),
        cleanup_error=removal.cleanup_error, photo_count=photo_count,
        member_asset_ids=[UUID(asset_id) for asset_id in member_asset_ids], groups=groups, source_dataset_id=UUID(source_dataset_id) if source_dataset_id else None,
    ).model_dump()


@router.get("/library/trash", response_model=LibraryTrashPage, dependencies=[Depends(deps.authenticate)])
def library_trash(session: deps.ReadSession, limit: deps.Limit = 50, offset: deps.Offset = 0,
                  group_id: UUID | None = None):
    if group_id is not None:
        group_id_text = shared._id(group_id)
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
        return shared._page(items, len(asset_ids), limit, offset)
    total = session.scalar(select(func.count()).select_from(LibraryEntryRemoval)) or 0
    removals = session.scalars(select(LibraryEntryRemoval).order_by(
        LibraryEntryRemoval.removed_at.desc(), LibraryEntryRemoval.entry_type, LibraryEntryRemoval.entry_id
    ).limit(limit).offset(offset)).all()
    return shared._page([_trash_item(session, removal) for removal in removals], total, limit, offset)


@router.post("/library/trash/restore", dependencies=[Depends(deps.authenticate)])
def restore_library_trash(body: LibraryTrashSelection, session: deps.WriteSession):
    restored = 0
    restored_asset_ids = set()
    # Keep parent removal records available while restoring their selected photos.
    for item in sorted(body.items, key=lambda item: item.entry_type == "dataset"):
        removal = session.get(LibraryEntryRemoval, (item.entry_type, shared._id(item.id)))
        source_dataset_id = shared._id(item.source_dataset_id) if item.source_dataset_id else None
        source_group = session.get(LibraryEntryRemoval, ("dataset", source_dataset_id)) if source_dataset_id else None
        if removal is None and item.entry_type == "asset" and source_group is not None and shared._id(item.id) in (source_group.member_asset_ids or []):
            removal = LibraryEntryRemoval(entry_type="asset", entry_id=shared._id(item.id), removed_at=source_group.removed_at,
                cleanup_status="trash", member_asset_ids=[], pending_paths=[], cleaned_paths=[], cleaned_asset_ids=[])
            removal.source_dataset_id = source_dataset_id
        if removal is None or _trash_cleanup_status(session, removal) != "trash":
            raise ApiError(409, "TRASH_STATE_CONFLICT", "该记录已清理或状态已变化，不能恢复。")
        row = session.get(Asset if item.entry_type == "asset" else Dataset, removal.entry_id)
        if row is None or row.revision != item.revision or shared._utc(removal.removed_at) != shared._utc(item.removed_at):
            raise ApiError(409, "REVISION_CONFLICT", "垃圾桶记录已变化，请重新读取。")
        if isinstance(row, Asset) and row.current_version_id != (shared._id(item.current_version_id) if item.current_version_id else None):
            raise ApiError(409, "REVISION_CONFLICT", "照片版本已变化，请重新读取。")
        if isinstance(row, Dataset) and row.current_version_id != (shared._id(item.current_version_id) if item.current_version_id else None):
            raise ApiError(409, "REVISION_CONFLICT", "数据集版本已变化，请重新读取。")
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
        removal = session.get(LibraryEntryRemoval, (item.entry_type, shared._id(item.id)))
        row = session.get(Asset if item.entry_type == "asset" else Dataset, shared._id(item.id))
        source_dataset_id = shared._id(item.source_dataset_id) if item.source_dataset_id else None
        if removal is None and item.entry_type == "asset" and source_dataset_id:
            parent = session.get(LibraryEntryRemoval, ("dataset", source_dataset_id))
            if parent is not None and shared._id(item.id) in (parent.member_asset_ids or []):
                removal = LibraryEntryRemoval(entry_type="asset", entry_id=shared._id(item.id),
                    dataset_version_id=parent.dataset_version_id, member_asset_ids=[], pending_paths=[], cleaned_paths=[],
                    cleaned_asset_ids=[], cleanup_status="trash", cleanup_error=None, removed_at=parent.removed_at)
                removal.source_dataset_id = source_dataset_id
        elif removal is not None and source_dataset_id:
            parent = session.get(LibraryEntryRemoval, ("dataset", source_dataset_id))
            if parent is None or shared._id(item.id) not in (parent.member_asset_ids or []):
                raise ApiError(409, "TRASH_STATE_CONFLICT", "照片已不属于该组的待清理范围。")
            removal.source_dataset_id = source_dataset_id
        if removal is None or row is None or removal.cleanup_status not in {"trash", "partial", "failed"}:
            raise ApiError(409, "TRASH_STATE_CONFLICT", "只能永久删除仍在垃圾桶中的内容。")
        if shared._utc(removal.removed_at) != shared._utc(item.removed_at) or row.revision != item.revision:
            raise ApiError(409, "REVISION_CONFLICT", "垃圾桶记录已变化，请重新预览。")
        if isinstance(row, Asset) and row.current_version_id != (shared._id(item.current_version_id) if item.current_version_id else None):
            raise ApiError(409, "REVISION_CONFLICT", "照片版本已变化，请重新预览。")
        if isinstance(row, Dataset) and row.current_version_id != (shared._id(item.current_version_id) if item.current_version_id else None):
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
    assert_no_preview_jobs(session, version_ids)
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
    refs.extend(calibration_references(session, version_ids, selected_dataset_version_ids,
                                      deleting_dataset_ids, version_ids))
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
        for location in owned_preview_locations(preview, settings):
            path = (settings.data_dir / location).resolve()
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
            paths.pop(str((settings.data_dir / (location + ".tmp")).resolve()), None)
    managed_bytes = sum(path.stat().st_size for path in paths.values() if path.is_file())
    return asset_ids, versions, previews, refs, task_ids, paths, managed_bytes


@router.post("/library/trash/delete-preview", response_model=LibraryTrashPreviewOut, dependencies=[Depends(deps.authenticate)])
def library_trash_delete_preview(body: LibraryTrashSelection, request: Request, session: deps.ReadSession):
    records = _selected_trash(session, body)
    asset_ids, versions, previews, refs, tasks, paths, managed_bytes = _trash_scope(session, request.app.state.settings, records)
    snapshot = {
        "items": [(r.entry_type, r.entry_id, r.removed_at.isoformat(), row.revision, getattr(row, "current_version_id", None),
                   _trash_cleanup_status(session, r), tuple(sorted(r.pending_paths or [])), tuple(sorted(r.cleaned_paths or [])), tuple(sorted(r.member_asset_ids or [])), tuple(sorted(r.cleaned_asset_ids or [])))
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


@router.post("/library/trash/delete", response_model=LibraryTrashDeleteOut, dependencies=[Depends(deps.authenticate)])
def library_trash_delete(body: LibraryTrashDelete, request: Request, session: deps.ReadSession):
    records = _selected_trash(session, body)
    settings = request.app.state.settings
    asset_ids, versions, previews, refs, tasks, paths, managed_bytes = _trash_scope(session, settings, records)
    if any(ref["kind"] == "calibration" for ref in refs):
        raise ApiError(409, "CALIBRATION_IN_USE", "仍有其他图像组版本使用所选校准目标，请先移除引用组。")
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
            candidate_paths.extend((settings.data_dir / location).resolve()
                                   for preview in previews if preview.asset_version_id == version.id
                                   for location in owned_preview_locations(preview, settings))
        paths_by_asset[asset_id] = [path for path in candidate_paths if str(path) in original_paths]
    success_assets, success_datasets, failed = set(), set(), []
    deferred_assets = set()
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
        current_preview = library_trash_delete_preview(body, request, write)
        if current_preview["preview_fingerprint"] != body.preview_fingerprint:
            raise ApiError(409, "TRASH_PREVIEW_STALE", "清理范围已变化，请重新预览。")
        if any(ref["kind"] == "calibration" for ref in current_preview["references"]):
            raise ApiError(409, "CALIBRATION_IN_USE", "校准引用已变化，请先移除引用组。")
        asset_records = {}
        for asset_id in asset_ids:
            removal = write.get(LibraryEntryRemoval, ("asset", asset_id))
            if removal is None:
                source = next(removal for removal, _ in current_records if
                    removal.entry_type == "asset" and removal.entry_id == asset_id or
                    removal.entry_type == "dataset" and asset_id in (removal.member_asset_ids or []))
                removal = LibraryEntryRemoval(entry_type="asset", entry_id=asset_id,
                    dataset_version_id=source.dataset_version_id, member_asset_ids=[], pending_paths=[],
                    cleaned_paths=[], cleaned_asset_ids=[], cleanup_status="trash", removed_at=source.removed_at)
                write.add(removal)
            asset_records[asset_id] = removal
        current_records = [(asset_records[removal.entry_id] if removal.entry_type == "asset" else removal, row)
                           for removal, row in current_records]
        group_records = [removal for removal, _ in current_records if removal.entry_type == "dataset"]
        for removal in [*asset_records.values(), *group_records]:
            if removal.entry_type == "asset":
                pending = [str(path) for path in paths_by_asset.get(removal.entry_id, [])]
            else:
                pending = [str(path) for asset_id in (removal.member_asset_ids or [])
                           for path in paths_by_asset.get(asset_id, [])]
            removal.pending_paths = list(dict.fromkeys([*(removal.pending_paths or []), *pending]))
            removal.cleanup_status = "partial"
            removal.cleanup_error = None

    removal_times = {asset_id: removal.removed_at for asset_id, removal in asset_records.items()}
    for asset_id in sorted(asset_ids):
        expected_versions = {version.id for version in versions if version.asset_id == asset_id}
        removed_paths = []
        asset_changed_projects, asset_changed_datasets = set(), set()
        try:
            with request.app.state.database.write_session() as write:
                current_removal = write.get(LibraryEntryRemoval, ("asset", asset_id))
                if current_removal is None or shared._utc(current_removal.removed_at) != shared._utc(removal_times[asset_id]):
                    raise ApiError(409, "TRASH_PREVIEW_STALE", "照片已恢复或垃圾桶范围已变化，请重新预览。")
                asset = write.get(Asset, asset_id)
                if asset is not None and (asset.revision, asset.current_version_id) != asset_states[asset_id]:
                    raise ApiError(409, "TRASH_PREVIEW_STALE", "照片资料或版本已变化，请重新预览。")
                original = next(row for row in body.items if row.entry_type == "asset" and shared._id(row.id) == asset_id) if any(
                    row.entry_type == "asset" and shared._id(row.id) == asset_id for row in body.items) else None
                if asset is not None and original is not None and (asset.revision != original.revision or asset.current_version_id != (shared._id(original.current_version_id) if original.current_version_id else None)):
                    raise ApiError(409, "TRASH_PREVIEW_STALE", "照片版本已变化，请重新预览。")
                current_versions = write.scalars(select(AssetVersion).where(AssetVersion.asset_id == asset_id)).all()
                if {version.id for version in current_versions} != expected_versions:
                    raise ApiError(409, "TRASH_PREVIEW_STALE", "照片版本已变化，请重新预览。")
                version_ids = expected_versions
                assert_no_preview_jobs(write, version_ids)
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
                owned_paths = {str(path) for path in paths_by_asset.get(asset_id, [])}
                calibration_version_ids = version_ids | {version.id for version in versions if version.storage_mode == "managed"
                    and str((settings.data_dir / version.storage_location).resolve()) in owned_paths}
                calibration_dataset_ids = set(write.scalars(select(DatasetMember.dataset_version_id).where(
                    DatasetMember.asset_version_id.in_(calibration_version_ids))).all())
                if calibration_references(write, calibration_version_ids, calibration_dataset_ids, excluded_member_versions=version_ids):
                    protect_calibration_targets(write, calibration_version_ids, calibration_dataset_ids, deleting_dataset_ids, version_ids)
                    deferred_assets.add(asset_id)
                    failed.append({"id": asset_id, "error": "校准目标保留原件和版本；待所选引用组清理后可重试此照片。"})
                    continue
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
                        removal.cleanup_status = _trash_cleanup_status(write, removal)
                        removal.cleanup_error = str(exc)
                if stale_before_cleanup:
                    for removal, _ in records:
                        current = write.get(LibraryEntryRemoval, (removal.entry_type, removal.entry_id))
                        if current and _trash_cleanup_status(write, current) == "trash":
                            current.cleanup_status = "trash"
                            current.cleanup_error = None
            if stale_before_cleanup:
                raise exc
    for removal, row in records:
        if removal.entry_type == "asset" and row.id in success_assets:
            continue
        if removal.entry_type == "dataset":
            remaining = set(removal.member_asset_ids or []) - success_assets
            if remaining and not remaining.issubset(deferred_assets):
                continue
            try:
                with request.app.state.database.write_session() as write:
                    dataset_removal = write.get(LibraryEntryRemoval, ("dataset", row.id))
                    dataset = write.get(Dataset, row.id)
                    original = next(item for item in body.items if item.entry_type == "dataset" and shared._id(item.id) == row.id)
                    if dataset_removal is None or shared._utc(dataset_removal.removed_at) != shared._utc(original.removed_at) or set(
                        dataset_removal.member_asset_ids or []
                    ) != remaining:
                        raise ApiError(409, "TRASH_PREVIEW_STALE", "组已恢复或垃圾桶范围已变化，请重新预览。")
                    if dataset and (dataset.revision != original.revision + dataset_revision_deltas.get(row.id, 0) or
                                    dataset.current_version_id != (shared._id(original.current_version_id) if original.current_version_id else None)):
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
                        protect_calibration_targets(write, set(), set(version_ids), {row.id})
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
                        # Deferred photos stay as independent trash entries after their container disappears.
                        for retained_removal in write.scalars(select(LibraryEntryRemoval).where(
                            LibraryEntryRemoval.entry_type == "asset", LibraryEntryRemoval.dataset_version_id.in_(version_ids)
                        )).all():
                            retained_removal.dataset_version_id = None
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
                        dataset_removal.cleanup_status = _trash_cleanup_status(write, dataset_removal)
                        dataset_removal.cleanup_error = str(exc)
                    if stale_before_cleanup:
                        for selected_removal, _ in records:
                            current = write.get(LibraryEntryRemoval, (selected_removal.entry_type, selected_removal.entry_id))
                            if current and _trash_cleanup_status(write, current) == "trash":
                                current.cleanup_status = "trash"
                                current.cleanup_error = None
                if stale_before_cleanup:
                    raise exc
    return {"deleted_count": len(success_assets), "deleted_entry_count": len(success_assets) + len(success_datasets),
            "deleted_file_count": deleted_file_count, "deleted_bytes": deleted_bytes,
            "missing_file_count": missing_file_count, "failed": failed}
