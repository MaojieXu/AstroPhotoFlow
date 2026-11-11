from __future__ import annotations
from collections.abc import Collection, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from astrophotoflow.contracts.trash import LibraryTrashDelete, LibraryTrashDeleteOut
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.assets.models import Asset, FitsHduMetadata
from astrophotoflow.modules.data.datasets.calibration import calibration_references, protect_calibration_targets
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember
from astrophotoflow.modules.data.imports.models import AssetTask, AssetTaskItem
from astrophotoflow.modules.data.media.models import Preview
from astrophotoflow.modules.data.media.ownership import assert_no_preview_jobs, owned_preview_locations
from astrophotoflow.modules.data.projects.models import Project, ProjectAssetReference, ProjectDatasetReference
from astrophotoflow.modules.data.trash import scope
from astrophotoflow.modules.data.trash.files import delete_owned_files
from astrophotoflow.modules.data.trash.models import LibraryEntryRemoval
from astrophotoflow.modules.data.trash.scope import cleanup_status, selected_trash, trash_scope
from astrophotoflow.modules.data.trash.types import CleanupPlan, FileCleanupResult

def confirm_cleanup(database: Database, settings: Settings, body: LibraryTrashDelete, asset_ids: Collection[str], paths_by_asset: Mapping[str, Sequence[Path]]) -> dict[str, datetime]:
    """Validate scope and commit finite cleanup intent before any file deletion."""
    with database.write_session() as write:
        current_records = selected_trash(write, body)
        current_preview = scope.plan_cleanup(write, settings, body)
        if current_preview.preview_fingerprint != body.preview_fingerprint:
            raise ApiError(409, 'TRASH_PREVIEW_STALE', '清理范围已变化，请重新预览。', message_key='the_cleanup_scope_has_changed_preview_it_again')
        if current_preview.references:
            raise ApiError(409, 'REFERENCES_EXIST', 'Detach external references before permanently deleting originals.', [{'path': ref.kind, 'message': ref.name} for ref in current_preview.references], message_key='library_external_references_block_cleanup')
        asset_records = {}
        for asset_id in asset_ids:
            removal = write.get(LibraryEntryRemoval, ('asset', asset_id))
            if removal is None:
                source = next((removal for removal, _ in current_records if removal.entry_type == 'asset' and removal.entry_id == asset_id or (removal.entry_type == 'dataset' and asset_id in (removal.member_asset_ids or []))))
                removal = LibraryEntryRemoval(entry_type='asset', entry_id=asset_id, dataset_id=source.dataset_id, member_asset_ids=[], pending_paths=[], cleaned_paths=[], cleaned_asset_ids=[], cleanup_status='trash', removed_at=source.removed_at)
                write.add(removal)
            asset_records[asset_id] = removal
        current_records = [(asset_records[removal.entry_id] if removal.entry_type == 'asset' else removal, row) for removal, row in current_records]
        group_records = [removal for removal, _ in current_records if removal.entry_type == 'dataset']
        for removal in [*asset_records.values(), *group_records]:
            if removal.entry_type == 'asset':
                pending = [str(path) for path in paths_by_asset.get(removal.entry_id, [])]
            else:
                pending = [str(path) for asset_id in removal.member_asset_ids or [] for path in paths_by_asset.get(asset_id, [])]
            if removal.entry_type == 'dataset':
                dataset = write.get(Dataset, removal.entry_id)
                if dataset and dataset.library_directory:
                    from astrophotoflow.modules.data.library.layout import library_path
                    pending.append(str(library_path(settings.data_dir, Path(dataset.library_directory) / 'dataset.json')))
            removal.pending_paths = list(dict.fromkeys([*(removal.pending_paths or []), *pending]))
            removal.cleanup_status = 'partial'
            removal.cleanup_error = None
    return {asset_id: removal.removed_at for asset_id, removal in asset_records.items()}

def finalize_cleanup(write: Session, result: FileCleanupResult) -> set[str]:
    if result.error is not None:
        raise result.error
    asset_id = result.plan.asset_id
    projects = set(write.scalars(select(ProjectAssetReference.project_id).where(ProjectAssetReference.asset_id == asset_id)))
    datasets = set(write.scalars(select(DatasetMember.dataset_id).where(DatasetMember.asset_id == asset_id)))
    write.execute(delete(ProjectAssetReference).where(ProjectAssetReference.asset_id == asset_id))
    write.execute(delete(DatasetMember).where(DatasetMember.asset_id == asset_id))
    write.execute(delete(Preview).where(Preview.asset_id == asset_id))
    write.execute(delete(FitsHduMetadata).where(FitsHduMetadata.asset_id == asset_id))
    for item in write.scalars(select(AssetTaskItem).where(AssetTaskItem.asset_id == asset_id)):
        item.asset_id = None
    write.flush()
    asset = write.get(Asset, asset_id)
    if asset is not None:
        write.delete(asset)
    removal = write.get(LibraryEntryRemoval, ('asset', asset_id))
    if removal is not None:
        write.delete(removal)
    for removal in write.scalars(select(LibraryEntryRemoval).where(LibraryEntryRemoval.entry_type == 'dataset')):
        if asset_id in (removal.member_asset_ids or []):
            if removal.entry_id in result.plan.selected_group_ids:
                removal.cleaned_asset_ids = list(dict.fromkeys([*(removal.cleaned_asset_ids or []), asset_id]))
            removal.member_asset_ids = [identity for identity in removal.member_asset_ids if identity != asset_id]
    for project_id in projects:
        project = write.get(Project, project_id)
        if project:
            project.revision += 1
            project.updated_at = datetime.now(UTC)
    for dataset_id in datasets:
        dataset = write.get(Dataset, dataset_id)
        if dataset:
            dataset.revision += 1
            dataset.updated_at = datetime.now(UTC)
    write.flush()
    return datasets

def delete_library_trash(session: Session, database: Database, settings: Settings, body: LibraryTrashDelete) -> LibraryTrashDeleteOut:
    records = selected_trash(session, body)
    asset_ids, versions, previews, refs, tasks, paths, _managed_bytes = trash_scope(session, settings, records)
    if refs:
        raise ApiError(409, 'REFERENCES_EXIST', 'Detach external references before permanently deleting originals.', [{'path': ref['kind'], 'message': ref['name']} for ref in refs], message_key='library_external_references_block_cleanup')
    if tasks:
        raise ApiError(409, 'IMPORT_ACTIVE', '正在执行或可恢复的导入任务仍占用所选内容，请先取消任务。', message_key='an_active_or_resumable_import_task_still_holds_the_selected_content_cancel_')
    expected_references = {str(ref['id']) for ref in refs}
    deleting_dataset_ids = {row.id for removal, row in records if removal.entry_type == 'dataset'}
    expected_group_references = {group_id: set(session.scalars(select(ProjectDatasetReference.id).where(ProjectDatasetReference.dataset_id == group_id)).all()) for group_id in deleting_dataset_ids}
    if deleting_dataset_ids:
        expected_references.update(session.scalars(select(DatasetMember.id).join(Dataset, Dataset.id == DatasetMember.dataset_id).where(Dataset.id.in_(deleting_dataset_ids))).all())
    expected_tasks = set(tasks)
    asset_states = {asset.id: (asset.revision, asset.id) for asset in session.scalars(select(Asset).where(Asset.id.in_(asset_ids))).all()} if asset_ids else {}
    original_paths = {str(path): path for path in paths.values()}
    paths_by_asset = {}
    for asset_id in asset_ids:
        assets = [version for version in versions if version.id == asset_id]
        candidate_paths = []
        for version in assets:
            if version.storage_mode == 'managed':
                candidate_paths.append((settings.data_dir / version.storage_location).resolve())
            candidate_paths.extend(((settings.data_dir / location).resolve() for preview in previews if preview.asset_id == version.id for location in owned_preview_locations(preview, settings)))
        paths_by_asset[asset_id] = [path for path in candidate_paths if str(path) in original_paths]
    success_assets, success_datasets, failed = (set(), set(), [])
    deferred_assets = set()
    deleted_file_count = deleted_bytes = missing_file_count = 0
    dataset_revision_deltas = {}
    selected_group_states = {}
    for removal, row in records:
        if removal.entry_type == 'dataset':
            live_members = set(session.scalars(select(Asset.id).join(DatasetMember, DatasetMember.asset_id == Asset.id).where(DatasetMember.dataset_id == row.id)).all()) if row.id else set()
            selected_group_states[row.id] = (row.revision, row.id, set(removal.member_asset_ids or []), live_members)
    selected_group_ids = set(selected_group_states)
    removal_times = confirm_cleanup(database, settings, body, asset_ids, paths_by_asset)
    for asset_id in sorted(asset_ids):
        expected_asset_ids = {version.id for version in versions if version.id == asset_id}
        removed_paths = []
        try:
            with database.write_session() as write:
                current_removal = write.get(LibraryEntryRemoval, ('asset', asset_id))
                if current_removal is None or (current_removal.removed_at.replace(tzinfo=UTC) if current_removal.removed_at.tzinfo is None else current_removal.removed_at.astimezone(UTC)) != (removal_times[asset_id].replace(tzinfo=UTC) if removal_times[asset_id].tzinfo is None else removal_times[asset_id].astimezone(UTC)):
                    raise ApiError(409, 'TRASH_PREVIEW_STALE', '照片已恢复或垃圾桶范围已变化，请重新预览。', message_key='the_photo_was_restored_or_the_trash_scope_has_changed_preview_it_again')
                asset = write.get(Asset, asset_id)
                if asset is not None and (asset.revision, asset.id) != asset_states[asset_id]:
                    raise ApiError(409, 'TRASH_PREVIEW_STALE', '照片资料或版本已变化，请重新预览。', message_key='photo_metadata_or_versions_have_changed_preview_them_again')
                original = next((row for row in body.items if row.entry_type == 'asset' and str(row.id) == asset_id)) if any((row.entry_type == 'asset' and str(row.id) == asset_id for row in body.items)) else None
                if asset is not None and original is not None and (asset.revision != original.revision or asset.id != (str(original.id) if original.id else None)):
                    raise ApiError(409, 'TRASH_PREVIEW_STALE', '照片版本已变化，请重新预览。', message_key='photo_versions_have_changed_preview_them_again')
                if asset is None or asset.id not in expected_asset_ids:
                    raise ApiError(409, 'TRASH_PREVIEW_STALE', '照片版本已变化，请重新预览。', message_key='photo_versions_have_changed_preview_them_again')
                registered_asset_ids = expected_asset_ids
                assert_no_preview_jobs(write, registered_asset_ids)
                current_refs = set(write.scalars(select(ProjectAssetReference.id).where(ProjectAssetReference.asset_id.in_(registered_asset_ids))).all()) if registered_asset_ids else set()
                current_refs.update(write.scalars(select(DatasetMember.id).where(DatasetMember.asset_id.in_(registered_asset_ids))).all() if registered_asset_ids else [])
                member_dataset_ids = set(write.scalars(select(DatasetMember.dataset_id).where(DatasetMember.asset_id.in_(registered_asset_ids))).all()) if registered_asset_ids else set()
                current_group_project_refs = set(write.scalars(select(ProjectDatasetReference.id).where(ProjectDatasetReference.dataset_id.in_(member_dataset_ids))).all()) if member_dataset_ids else set()
                if not current_group_project_refs.issubset(expected_references):
                    raise ApiError(409, 'TRASH_PREVIEW_STALE', '项目组关联已变化，请重新预览。', message_key='project_group_references_have_changed_preview_them_again')
                for group_id, (initial_revision, initial_dataset_id, initial_members, initial_live_members) in selected_group_states.items():
                    group = write.get(Dataset, group_id)
                    expected_revision = initial_revision + dataset_revision_deltas.get(group_id, 0)
                    if group is None or group.revision != expected_revision or group.id != initial_dataset_id:
                        raise ApiError(409, 'TRASH_PREVIEW_STALE', '组资料或版本已变化，请重新预览。', message_key='group_metadata_or_versions_have_changed_preview_them_again')
                    current_group_removal = write.get(LibraryEntryRemoval, ('dataset', group_id))
                    expected_group_members = initial_members - success_assets
                    if current_group_removal is None or set(current_group_removal.member_asset_ids or []) != expected_group_members:
                        raise ApiError(409, 'TRASH_PREVIEW_STALE', '组内待清理范围已变化，请重新预览。', message_key='the_group_s_cleanup_scope_has_changed_preview_it_again')
                    live_group_members = set(write.scalars(select(Asset.id).join(DatasetMember, DatasetMember.asset_id == Asset.id).where(DatasetMember.dataset_id == initial_dataset_id)).all()) if initial_dataset_id else set()
                    if live_group_members != initial_live_members - success_assets:
                        raise ApiError(409, 'TRASH_PREVIEW_STALE', '组内成员已变化，请重新预览。', message_key='group_membership_has_changed_preview_it_again')
                    group_ids = set(write.scalars(select(Dataset.id).where(Dataset.id == group_id)).all())
                    group_refs = set(write.scalars(select(ProjectDatasetReference.id).where(ProjectDatasetReference.dataset_id.in_(group_ids))).all()) if group_ids else set()
                    if group_refs != expected_group_references[group_id]:
                        raise ApiError(409, 'TRASH_PREVIEW_STALE', '项目组关联已变化，请重新预览。', message_key='project_group_references_have_changed_preview_them_again')
                    group_tasks = set(write.scalars(select(AssetTask.id).where(AssetTask.dataset_id == group_id, AssetTask.status.in_({'queued', 'running', 'cancelling', 'interrupted'}))).all())
                    if not group_tasks.issubset(expected_tasks):
                        raise ApiError(409, 'TRASH_PREVIEW_STALE', '组导入任务占用已变化，请重新预览。', message_key='group_import_task_usage_has_changed_preview_it_again')
                if not current_refs.issubset(expected_references):
                    raise ApiError(409, 'TRASH_PREVIEW_STALE', '项目或组关联已变化，请重新预览。', message_key='project_or_group_references_have_changed_preview_them_again')
                owned_paths = {str(path) for path in paths_by_asset.get(asset_id, [])}
                calibration_asset_ids = registered_asset_ids | {version.id for version in versions if version.storage_mode == 'managed' and str((settings.data_dir / version.storage_location).resolve()) in owned_paths}
                calibration_dataset_ids = set(write.scalars(select(DatasetMember.dataset_id).where(DatasetMember.asset_id.in_(calibration_asset_ids))).all())
                if calibration_references(write, calibration_asset_ids, calibration_dataset_ids, excluded_asset_ids=registered_asset_ids):
                    protect_calibration_targets(write, calibration_asset_ids, calibration_dataset_ids, deleting_dataset_ids, registered_asset_ids)
                    deferred_assets.add(asset_id)
                    failed.append({'id': asset_id, 'error': '校准目标保留原件和版本；待所选引用组清理后可重试此照片。'})
                    continue
                active_task_ids = set(write.scalars(select(AssetTask.id).join(AssetTaskItem, AssetTaskItem.task_id == AssetTask.id).where(AssetTask.status.in_({'queued', 'running', 'cancelling', 'interrupted'}), AssetTaskItem.asset_id == asset_id)).all())
                if not active_task_ids.issubset(expected_tasks):
                    raise ApiError(409, 'TRASH_PREVIEW_STALE', '导入任务占用已变化，请重新预览。', message_key='import_task_usage_has_changed_preview_it_again')
                current_removals = write.scalars(select(LibraryEntryRemoval)).all()
                affected_removals = [removal for removal in current_removals if removal.entry_type == 'asset' and removal.entry_id == asset_id or (removal.entry_type == 'dataset' and removal.entry_id in selected_group_ids and (asset_id in (removal.member_asset_ids or [])))]
                cleaned = {path for removal in affected_removals for path in removal.cleaned_paths or []}
                plan = CleanupPlan(asset_id, tuple(paths_by_asset.get(asset_id, [])), frozenset(cleaned), frozenset(selected_group_ids))
                file_result = delete_owned_files(plan)
                removed_paths = file_result.removed_paths
                deleted_file_count += len(removed_paths)
                deleted_bytes += file_result.deleted_bytes
                missing_file_count += file_result.missing_file_count
                for path_key in removed_paths:
                    for removal in affected_removals:
                        if path_key in (removal.pending_paths or []) and path_key not in (removal.cleaned_paths or []):
                            removal.cleaned_paths = [*(removal.cleaned_paths or []), path_key]
                            removal.cleanup_status = 'partial'
                asset_changed_datasets = finalize_cleanup(write, file_result)
            for dataset_id in asset_changed_datasets:
                dataset_revision_deltas[dataset_id] = dataset_revision_deltas.get(dataset_id, 0) + 1
            success_assets.add(asset_id)
        except Exception as exc:
            failed.append({'id': asset_id, 'error': str(exc)})
            stale_before_cleanup = isinstance(exc, ApiError) and exc.status_code == 409 and (not success_assets) and (not deleted_file_count)
            with database.write_session() as write:
                for removal in write.scalars(select(LibraryEntryRemoval)).all():
                    if removal.entry_type == 'asset' and removal.entry_id == asset_id or (removal.entry_type == 'dataset' and removal.entry_id in selected_group_ids and (asset_id in (removal.member_asset_ids or []))):
                        removal.cleaned_paths = list(dict.fromkeys([*(removal.cleaned_paths or []), *removed_paths]))
                        removal.cleanup_status = cleanup_status(write, removal)
                        removal.cleanup_error = str(exc)
                if stale_before_cleanup:
                    for removal, _ in records:
                        current = write.get(LibraryEntryRemoval, (removal.entry_type, removal.entry_id))
                        if current and cleanup_status(write, current) == 'trash':
                            current.cleanup_status = 'trash'
                            current.cleanup_error = None
            if stale_before_cleanup:
                raise
    for removal, row in records:
        if removal.entry_type == 'asset' and row.id in success_assets:
            continue
        if removal.entry_type == 'dataset':
            remaining = set(removal.member_asset_ids or []) - success_assets
            if remaining and (not remaining.issubset(deferred_assets)):
                continue
            try:
                with database.write_session() as write:
                    dataset_removal = write.get(LibraryEntryRemoval, ('dataset', row.id))
                    dataset = write.get(Dataset, row.id)
                    original = next((item for item in body.items if item.entry_type == 'dataset' and str(item.id) == row.id))
                    if dataset_removal is None or (dataset_removal.removed_at.replace(tzinfo=UTC) if dataset_removal.removed_at.tzinfo is None else dataset_removal.removed_at.astimezone(UTC)) != (original.removed_at.replace(tzinfo=UTC) if original.removed_at.tzinfo is None else original.removed_at.astimezone(UTC)) or set(dataset_removal.member_asset_ids or []) != remaining:
                        raise ApiError(409, 'TRASH_PREVIEW_STALE', '组已恢复或垃圾桶范围已变化，请重新预览。', message_key='the_group_was_restored_or_the_trash_scope_has_changed_preview_it_again')
                    if dataset and (dataset.revision != original.revision + dataset_revision_deltas.get(row.id, 0) or dataset.id != (str(original.id) if original.id else None)):
                        raise ApiError(409, 'TRASH_PREVIEW_STALE', '组版本已变化，请重新预览。', message_key='group_versions_have_changed_preview_them_again')
                    dataset_rows = write.scalars(select(Dataset).where(Dataset.id == row.id)).all() if dataset else []
                    current_refs = set(write.scalars(select(ProjectDatasetReference.id).where(ProjectDatasetReference.dataset_id == row.id)).all())
                    if not current_refs.issubset(expected_references):
                        raise ApiError(409, 'TRASH_PREVIEW_STALE', '项目关联已变化，请重新预览。', message_key='project_references_have_changed_preview_them_again')
                    active_task_ids = set(write.scalars(select(AssetTask.id).where(AssetTask.dataset_id == row.id, AssetTask.status.in_({'queued', 'running', 'cancelling', 'interrupted'}))).all())
                    if not active_task_ids.issubset(expected_tasks):
                        raise ApiError(409, 'TRASH_PREVIEW_STALE', '导入任务占用已变化，请重新预览。', message_key='import_task_usage_has_changed_preview_it_again')
                    if dataset:
                        if dataset.library_directory:
                            from astrophotoflow.modules.data.library.layout import library_path
                            manifest = library_path(settings.data_dir, Path(dataset.library_directory) / 'dataset.json')
                            if str(manifest) not in original_paths:
                                raise ApiError(409, 'TRASH_PREVIEW_STALE', 'The dataset manifest location changed; preview cleanup again.', message_key='the_dataset_manifest_location_changed_preview_cleanup_again')
                            mirror_result = delete_owned_files(CleanupPlan(dataset.id, (manifest,), frozenset(dataset_removal.cleaned_paths or []), frozenset({dataset.id})))
                            deleted_file_count += len(mirror_result.removed_paths)
                            deleted_bytes += mirror_result.deleted_bytes
                            missing_file_count += mirror_result.missing_file_count
                            if mirror_result.error is not None:
                                raise mirror_result.error
                        registered_asset_ids = [v.id for v in dataset_rows]
                        protect_calibration_targets(write, set(), set(registered_asset_ids), {row.id})
                        write.execute(delete(DatasetMember).where(DatasetMember.dataset_id.in_(registered_asset_ids))) if registered_asset_ids else None
                        affected_project_ids = set()
                        for reference in write.scalars(select(ProjectDatasetReference).where(ProjectDatasetReference.dataset_id == row.id)).all():
                            affected_project_ids.add(reference.project_id)
                            write.delete(reference)
                        for project_id in affected_project_ids:
                            project = write.get(Project, project_id)
                            if project:
                                project.revision += 1
                                project.updated_at = datetime.now(UTC)
                        if dataset_removal:
                            write.delete(dataset_removal)
                        for retained_removal in write.scalars(select(LibraryEntryRemoval).where(LibraryEntryRemoval.entry_type == 'asset', LibraryEntryRemoval.dataset_id.in_(registered_asset_ids))).all():
                            retained_removal.dataset_id = None
                        write.flush()
                        for task in write.scalars(select(AssetTask).where(AssetTask.dataset_id == row.id)).all():
                            task.dataset_id = None
                        write.delete(dataset)
                    elif dataset_removal:
                        write.delete(dataset_removal)
                success_datasets.add(row.id)
            except Exception as exc:
                failed.append({'id': row.id, 'error': str(exc)})
                stale_before_cleanup = isinstance(exc, ApiError) and exc.status_code == 409 and (not success_assets) and (not deleted_file_count)
                with database.write_session() as write:
                    dataset_removal = write.get(LibraryEntryRemoval, ('dataset', row.id))
                    if dataset_removal:
                        dataset_removal.cleanup_status = cleanup_status(write, dataset_removal)
                        dataset_removal.cleanup_error = str(exc)
                    if stale_before_cleanup:
                        for selected_removal, _ in records:
                            current = write.get(LibraryEntryRemoval, (selected_removal.entry_type, selected_removal.entry_id))
                            if current and cleanup_status(write, current) == 'trash':
                                current.cleanup_status = 'trash'
                                current.cleanup_error = None
                if stale_before_cleanup:
                    raise
    return LibraryTrashDeleteOut.model_validate({'deleted_count': len(success_assets), 'deleted_entry_count': len(success_assets) + len(success_datasets), 'deleted_file_count': deleted_file_count, 'deleted_bytes': deleted_bytes, 'missing_file_count': missing_file_count, 'failed': failed})
