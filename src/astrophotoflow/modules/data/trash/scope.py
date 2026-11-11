from __future__ import annotations
import hashlib
import json
from datetime import UTC
from pathlib import Path
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from astrophotoflow.contracts.trash import LibraryEntriesRemove, LibraryRemovalScope, LibraryTrashItemOut, LibraryTrashPreviewOut, LibraryTrashSelection
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.datasets.calibration import calibration_references
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember
from astrophotoflow.modules.data.imports.models import AssetTask, AssetTaskItem
from astrophotoflow.modules.data.media.models import Preview
from astrophotoflow.modules.data.media.ownership import assert_no_preview_jobs, owned_preview_locations
from astrophotoflow.modules.data.projects.models import Project, ProjectAssetReference, ProjectDatasetReference
from astrophotoflow.modules.data.trash.models import LibraryEntryRemoval

def preview_library_removal(database: Database, body: LibraryEntriesRemove) -> LibraryRemovalScope:
    asset_ids: list[str] = []
    dataset_ids: list[str] = []
    with database.read_session() as session:
        for item in body.items:
            record_id = str(item.id)
            if item.entry_type == 'asset':
                asset = session.get(Asset, record_id)
                if asset is None or asset.scope != 'shared' or asset.status != 'active':
                    raise not_found()
                if asset.revision != item.revision:
                    raise ApiError(409, 'REVISION_CONFLICT', 'The selected record changed.', message_key='another_window_changed_the_configuration_read_it_again_before_saving')
                if asset.id != (str(item.id) if item.id else None):
                    raise ApiError(409, 'REVISION_CONFLICT', '素材当前版本已变化，请重新读取后预览移除范围。', message_key='the_current_asset_has_changed_read_it_again_before_previewing_remov')
                asset_ids.append(asset.id)
            else:
                dataset = session.get(Dataset, record_id)
                if dataset is None or dataset.status != 'active':
                    raise not_found()
                if dataset.revision != item.revision:
                    raise ApiError(409, 'REVISION_CONFLICT', 'The selected record changed.', message_key='another_window_changed_the_configuration_read_it_again_before_saving')
                if dataset.id != (str(item.id) if item.id else None):
                    raise ApiError(409, 'REVISION_CONFLICT', '素材组成员版本已变化，请重新读取后预览移除范围。', message_key='asset_group_member_versions_have_changed_read_them_again_before_previewing_')
                dataset_ids.append(dataset.id)
                if dataset.id:
                    dataset_ids.append(dataset.id)
                    asset_ids.extend(session.scalars(select(DatasetMember.asset_id).where(DatasetMember.dataset_id == dataset.id).order_by(DatasetMember.position)))
    scope_data = {'selection': body.model_dump(mode='json'), 'asset_ids': list(dict.fromkeys(asset_ids)), 'dataset_ids': list(dict.fromkeys(dataset_ids))}
    token = hashlib.sha256(json.dumps(scope_data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return LibraryRemovalScope.model_validate(LibraryRemovalScope(selection=body, asset_ids=[UUID(value) for value in scope_data['asset_ids']], dataset_ids=[UUID(value) for value in scope_data['dataset_ids']], data_token=token))

def cleanup_status(session: Session, removal: LibraryEntryRemoval) -> str:
    if removal.cleaned_paths or removal.cleaned_asset_ids:
        return 'partial'
    if removal.entry_type == 'dataset':
        for asset_id in removal.member_asset_ids or []:
            child = session.get(LibraryEntryRemoval, ('asset', asset_id))
            if child is not None and cleanup_status(session, child) == 'partial':
                return 'partial'
    elif any((not Path(path).is_file() for path in removal.pending_paths or [])):
        return 'partial'
    return 'trash'

def trash_item(session: Session, removal: LibraryEntryRemoval, source_dataset_id: str | None=None) -> LibraryTrashItemOut:
    row = session.get(Asset if removal.entry_type == 'asset' else Dataset, removal.entry_id)
    name = row.name if row is not None else removal.entry_id
    revision = row.revision if row is not None else 1
    photo_count = 1 if removal.entry_type == 'asset' else len(set(removal.member_asset_ids or []))
    groups = []
    member_asset_ids = removal.member_asset_ids or [] if removal.entry_type == 'dataset' else []
    if removal.entry_type == 'asset':
        asset_groups = session.scalars(select(Dataset).join(DatasetMember, DatasetMember.dataset_id == Dataset.id).join(Asset, Asset.id == DatasetMember.asset_id).where(Asset.id == removal.entry_id).distinct()).all()
        groups = [{'id': UUID(group.id), 'name': group.name, 'in_trash': session.get(LibraryEntryRemoval, ('dataset', group.id)) is not None} for group in asset_groups]
    return LibraryTrashItemOut(entry_type=removal.entry_type, id=UUID(removal.entry_id), name=name, removed_at=removal.removed_at.replace(tzinfo=UTC) if removal.removed_at.tzinfo is None else removal.removed_at.astimezone(UTC), revision=revision, cleanup_status=cleanup_status(session, removal), cleanup_error=removal.cleanup_error, photo_count=photo_count, member_asset_ids=[UUID(asset_id) for asset_id in member_asset_ids], groups=groups, source_dataset_id=UUID(source_dataset_id) if source_dataset_id else None)

def selected_trash(session: Session, body):
    records = []
    for item in body.items:
        removal = session.get(LibraryEntryRemoval, (item.entry_type, str(item.id)))
        row = session.get(Asset if item.entry_type == 'asset' else Dataset, str(item.id))
        source_dataset_id = str(item.source_dataset_id) if item.source_dataset_id else None
        if removal is None and item.entry_type == 'asset' and source_dataset_id:
            parent = session.get(LibraryEntryRemoval, ('dataset', source_dataset_id))
            if parent is not None and str(item.id) in (parent.member_asset_ids or []):
                removal = LibraryEntryRemoval(entry_type='asset', entry_id=str(item.id), dataset_id=parent.dataset_id, member_asset_ids=[], pending_paths=[], cleaned_paths=[], cleaned_asset_ids=[], cleanup_status='trash', cleanup_error=None, removed_at=parent.removed_at)
                removal.source_dataset_id = source_dataset_id
        elif removal is not None and source_dataset_id:
            parent = session.get(LibraryEntryRemoval, ('dataset', source_dataset_id))
            if parent is None or str(item.id) not in (parent.member_asset_ids or []):
                raise ApiError(409, 'TRASH_STATE_CONFLICT', '照片已不属于该组的待清理范围。', message_key='the_photo_no_longer_belongs_to_this_group_s_cleanup_selection')
            removal.source_dataset_id = source_dataset_id
        if removal is None or row is None or removal.cleanup_status not in {'trash', 'partial', 'failed'}:
            raise ApiError(409, 'TRASH_STATE_CONFLICT', '只能永久删除仍在垃圾桶中的内容。', message_key='only_content_still_in_trash_can_be_permanently_deleted')
        if (removal.removed_at.replace(tzinfo=UTC) if removal.removed_at.tzinfo is None else removal.removed_at.astimezone(UTC)) != (item.removed_at.replace(tzinfo=UTC) if item.removed_at.tzinfo is None else item.removed_at.astimezone(UTC)) or row.revision != item.revision:
            raise ApiError(409, 'REVISION_CONFLICT', '垃圾桶记录已变化，请重新预览。', message_key='trash_records_have_changed_preview_them_again')
        if isinstance(row, Asset) and row.id != (str(item.id) if item.id else None):
            raise ApiError(409, 'REVISION_CONFLICT', '照片版本已变化，请重新预览。', message_key='photo_versions_have_changed_preview_them_again')
        if isinstance(row, Dataset) and row.id != (str(item.id) if item.id else None):
            raise ApiError(409, 'REVISION_CONFLICT', '数据集版本已变化，请重新预览。', message_key='datasets_have_changed_preview_them_again')
        records.append((removal, row))
    return records

def trash_scope(session: Session, settings: Settings, records):
    asset_ids = set()
    for removal, row in records:
        if removal.entry_type == 'asset':
            asset_ids.add(row.id)
        else:
            asset_ids.update(removal.member_asset_ids or [])
    versions = session.scalars(select(Asset).where(Asset.id.in_(asset_ids))).all() if asset_ids else []
    registered_asset_ids = {version.id for version in versions}
    assert_no_preview_jobs(session, registered_asset_ids)
    deleting_dataset_ids = {row.id for removal, row in records if removal.entry_type == 'dataset'}
    refs = []
    for ref, project in session.execute(select(ProjectAssetReference, Project).join(Project, Project.id == ProjectAssetReference.project_id).where(ProjectAssetReference.asset_id.in_(registered_asset_ids))).all() if registered_asset_ids else []:
        version = session.get(Asset, ref.asset_id)
        refs.append({'id': UUID(ref.id), 'kind': 'project_asset', 'name': project.name})
    for member, dataset in session.execute(select(DatasetMember, Dataset).join(Dataset, Dataset.id == DatasetMember.dataset_id).where(DatasetMember.asset_id.in_(registered_asset_ids))).all() if registered_asset_ids else []:
        refs.append({'id': UUID(member.id), 'kind': 'dataset_member', 'name': dataset.name})
    internal_member_ids = set(session.scalars(select(DatasetMember.id).where(DatasetMember.dataset_id.in_(deleting_dataset_ids))))
    refs = [ref for ref in refs if ref['kind'] != 'dataset_member' or str(ref['id']) not in internal_member_ids]
    selected_dataset_ids = {removal.dataset_id for removal, _ in records if removal.entry_type == 'dataset' and removal.dataset_id}
    if registered_asset_ids:
        selected_dataset_ids.update(session.scalars(select(DatasetMember.dataset_id).where(DatasetMember.asset_id.in_(registered_asset_ids))).all())
    if deleting_dataset_ids:
        selected_dataset_ids.update(session.scalars(select(Dataset.id).where(Dataset.id.in_(deleting_dataset_ids))).all())
    for ref, project in session.execute(select(ProjectDatasetReference, Project).join(Project, Project.id == ProjectDatasetReference.project_id).where(ProjectDatasetReference.dataset_id.in_(selected_dataset_ids))).all() if selected_dataset_ids else []:
        version = session.get(Dataset, ref.dataset_id)
        refs.append({'id': UUID(ref.id), 'kind': 'project_dataset', 'name': project.name})
    refs.extend(calibration_references(session, registered_asset_ids, selected_dataset_ids, deleting_dataset_ids, registered_asset_ids))
    active_task_statuses = {'queued', 'running', 'cancelling', 'interrupted'}
    task_ids = set(session.scalars(select(AssetTask.id).join(AssetTaskItem, AssetTaskItem.task_id == AssetTask.id).where(AssetTask.status.in_(active_task_statuses), AssetTaskItem.asset_id.in_(asset_ids))).all()) if asset_ids else set()
    task_ids.update(session.scalars(select(AssetTask.id).where(AssetTask.status.in_(active_task_statuses), AssetTask.dataset_id.in_(deleting_dataset_ids))).all() if deleting_dataset_ids else [])
    task_ids = sorted(task_ids)
    paths = {}
    for version in versions:
        if version.storage_mode == 'managed':
            path = (settings.data_dir / version.storage_location).resolve()
            if not path.is_relative_to(settings.data_dir.resolve()):
                raise ApiError(409, 'FILE_SCOPE_INVALID', '托管文件路径不在服务数据目录中，已阻止清理。', message_key='the_managed_file_is_outside_the_service_data_directory_cleanup_is_blocked')
            paths[str(path)] = path
    previews = session.scalars(select(Preview).where(Preview.asset_id.in_(registered_asset_ids))).all() if registered_asset_ids else []
    for preview in previews:
        for location in owned_preview_locations(preview, settings):
            path = (settings.data_dir / location).resolve()
            if not path.is_relative_to(settings.data_dir.resolve()):
                raise ApiError(409, 'FILE_SCOPE_INVALID', '预览文件路径不在服务数据目录中，已阻止清理。', message_key='the_preview_file_is_outside_the_service_data_directory_cleanup_is_blocked')
            paths[str(path)] = path
    managed_locations = [version.storage_location for version in versions if version.storage_mode == 'managed']
    if managed_locations:
        other_locations = set(session.scalars(select(Asset.storage_location).where(Asset.storage_location.in_(managed_locations), Asset.id.not_in(asset_ids))).all())
        for location in other_locations:
            paths.pop(str((settings.data_dir / location).resolve()), None)
    preview_locations = [preview.storage_path for preview in previews]
    if preview_locations:
        other_preview_locations = set(session.scalars(select(Preview.storage_path).join(Asset, Asset.id == Preview.asset_id).where(Preview.storage_path.in_(preview_locations), Asset.id.not_in(asset_ids))).all())
        for location in other_preview_locations:
            paths.pop(str((settings.data_dir / location).resolve()), None)
            paths.pop(str((settings.data_dir / (location + '.tmp')).resolve()), None)
    from astrophotoflow.modules.data.library.layout import library_path
    for removal, dataset in records:
        if removal.entry_type == 'dataset' and dataset.library_directory:
            manifest = library_path(settings.data_dir, Path(dataset.library_directory) / 'dataset.json')
            paths[str(manifest)] = manifest
    managed_bytes = sum((path.stat().st_size for path in paths.values() if path.is_file()))
    return (asset_ids, versions, previews, refs, task_ids, paths, managed_bytes)

def plan_cleanup(session: Session, settings: Settings, body: LibraryTrashSelection) -> LibraryTrashPreviewOut:
    records = selected_trash(session, body)
    asset_ids, versions, _previews, refs, tasks, paths, managed_bytes = trash_scope(session, settings, records)
    snapshot = {'items': [(r.entry_type, r.entry_id, r.removed_at.isoformat(), row.revision, cleanup_status(session, r), tuple(sorted(r.pending_paths or [])), tuple(sorted(r.cleaned_paths or [])), tuple(sorted(r.member_asset_ids or [])), tuple(sorted(r.cleaned_asset_ids or []))) for r, row in records], 'assets': sorted(((asset.id, asset.revision) for asset in session.scalars(select(Asset).where(Asset.id.in_(asset_ids))).all())) if asset_ids else [], 'refs': sorted((ref['id'] for ref in refs)), 'tasks': sorted(tasks), 'paths': sorted(((key, path.stat().st_size if path.is_file() else None) for key, path in paths.items()))}
    fingerprint = hashlib.sha256(json.dumps(snapshot, sort_keys=True, default=str).encode()).hexdigest()
    return LibraryTrashPreviewOut.model_validate({'items': [trash_item(session, r) for r, _ in records], 'references': refs, 'tasks': tasks, 'photo_count': len(asset_ids), 'managed_file_count': len(paths), 'managed_bytes': managed_bytes, 'preview_fingerprint': fingerprint})


def cleanup_originals(session, settings, body):
    records = selected_trash(session, body)
    identities, _, _, _, _, paths, _ = trash_scope(session, settings, records)
    return set(identities), {str(path) for path in paths.values()}
