from __future__ import annotations
from datetime import UTC
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from astrophotoflow.contracts.trash import LibraryEntriesRemove, LibraryEntriesRemoveOut, LibraryTrashPage, LibraryTrashRestoreOut, LibraryTrashSelection
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember
from astrophotoflow.modules.data.trash.models import LibraryEntryRemoval
from astrophotoflow.modules.data.trash.scope import cleanup_status, trash_item

def remove_library_entries(session: Session, body: LibraryEntriesRemove) -> LibraryEntriesRemoveOut:
    removals = set(session.execute(select(LibraryEntryRemoval.entry_type, LibraryEntryRemoval.entry_id)).all())
    checked = []
    for item in body.items:
        record_id = str(item.id)
        if item.entry_type == 'asset':
            record = session.get(Asset, record_id)
            if record is None or record.scope != 'shared' or record.status != 'active':
                raise not_found()
            if record.revision != item.revision:
                raise ApiError(409, 'REVISION_CONFLICT', 'The selected record changed.', message_key='another_window_changed_the_configuration_read_it_again_before_saving')
        else:
            record = session.get(Dataset, record_id)
            if record is None or record.status != 'active':
                raise not_found()
            if record.revision != item.revision:
                raise ApiError(409, 'REVISION_CONFLICT', 'The selected record changed.', message_key='another_window_changed_the_configuration_read_it_again_before_saving')
            if record.id != (str(item.id) if item.id else None):
                raise ApiError(409, 'REVISION_CONFLICT', '数据集成员版本已变化，请重新读取后删除。', message_key='dataset_member_versions_have_changed_read_them_again_before_deletion')
        checked.append((item.entry_type, record_id, record.id if item.entry_type == 'dataset' else None))
    added = 0
    for entry_type, entry_id, dataset_id in checked:
        if (entry_type, entry_id) not in removals:
            member_asset_ids = []
            if entry_type == 'dataset' and dataset_id:
                member_asset_ids = list(session.scalars(select(Asset.id).join(DatasetMember, DatasetMember.asset_id == Asset.id).where(DatasetMember.dataset_id == dataset_id).distinct()).all())
            session.add(LibraryEntryRemoval(entry_type=entry_type, entry_id=entry_id, dataset_id=dataset_id, member_asset_ids=member_asset_ids, cleanup_status='trash'))
            added += 1
    session.flush()
    return LibraryEntriesRemoveOut.model_validate({'removed_count': added})

def library_trash(session: Session, limit: int=50, offset: int=0, group_id: UUID | None=None) -> LibraryTrashPage:
    if group_id is not None:
        group_id_text = str(group_id)
        group_removal = session.get(LibraryEntryRemoval, ('dataset', group_id_text))
        if group_removal is None:
            raise not_found()
        asset_ids = list(dict.fromkeys(group_removal.member_asset_ids or []))
        assets = session.scalars(select(Asset).where(Asset.id.in_(asset_ids)).order_by(Asset.name, Asset.id).limit(limit).offset(offset)).all() if asset_ids else []
        items = []
        for asset in assets:
            asset_removal = session.get(LibraryEntryRemoval, ('asset', asset.id))
            if asset_removal is not None:
                items.append(trash_item(session, asset_removal, group_id_text))
            else:
                virtual = LibraryEntryRemoval(entry_type='asset', entry_id=asset.id, dataset_id=group_removal.dataset_id, member_asset_ids=[], pending_paths=[], cleaned_paths=[], cleaned_asset_ids=[], cleanup_status='trash', cleanup_error=None, removed_at=group_removal.removed_at)
                items.append(trash_item(session, virtual, group_id_text))
        return LibraryTrashPage.model_validate({'items': items, 'total': len(asset_ids), 'limit': limit, 'offset': offset})
    total = session.scalar(select(func.count()).select_from(LibraryEntryRemoval)) or 0
    removals = session.scalars(select(LibraryEntryRemoval).order_by(LibraryEntryRemoval.removed_at.desc(), LibraryEntryRemoval.entry_type, LibraryEntryRemoval.entry_id).limit(limit).offset(offset)).all()
    return LibraryTrashPage.model_validate({'items': [trash_item(session, removal) for removal in removals], 'total': total, 'limit': limit, 'offset': offset})

def restore_library_trash(session: Session, body: LibraryTrashSelection) -> LibraryTrashRestoreOut:
    restored = 0
    restored_asset_ids = set()
    for item in sorted(body.items, key=lambda item: item.entry_type == 'dataset'):
        removal = session.get(LibraryEntryRemoval, (item.entry_type, str(item.id)))
        source_dataset_id = str(item.source_dataset_id) if item.source_dataset_id else None
        source_group = session.get(LibraryEntryRemoval, ('dataset', source_dataset_id)) if source_dataset_id else None
        if removal is None and item.entry_type == 'asset' and (source_group is not None) and (str(item.id) in (source_group.member_asset_ids or [])):
            removal = LibraryEntryRemoval(entry_type='asset', entry_id=str(item.id), removed_at=source_group.removed_at, cleanup_status='trash', member_asset_ids=[], pending_paths=[], cleaned_paths=[], cleaned_asset_ids=[])
            removal.source_dataset_id = source_dataset_id
        if removal is None or cleanup_status(session, removal) != 'trash':
            raise ApiError(409, 'TRASH_STATE_CONFLICT', '该记录已清理或状态已变化，不能恢复。', message_key='this_record_was_cleaned_up_or_its_state_has_changed_and_cannot_be_restored')
        row = session.get(Asset if item.entry_type == 'asset' else Dataset, removal.entry_id)
        if row is None or row.revision != item.revision or (removal.removed_at.replace(tzinfo=UTC) if removal.removed_at.tzinfo is None else removal.removed_at.astimezone(UTC)) != (item.removed_at.replace(tzinfo=UTC) if item.removed_at.tzinfo is None else item.removed_at.astimezone(UTC)):
            raise ApiError(409, 'REVISION_CONFLICT', '垃圾桶记录已变化，请重新读取。', message_key='trash_records_have_changed_read_them_again')
        if isinstance(row, Asset) and row.id != (str(item.id) if item.id else None):
            raise ApiError(409, 'REVISION_CONFLICT', '照片版本已变化，请重新读取。', message_key='photo_versions_have_changed_read_them_again')
        if isinstance(row, Dataset) and row.id != (str(item.id) if item.id else None):
            raise ApiError(409, 'REVISION_CONFLICT', '数据集版本已变化，请重新读取。', message_key='datasets_have_changed_read_them_again')
        if source_dataset_id and item.entry_type == 'asset':
            source_group = session.get(LibraryEntryRemoval, ('dataset', source_dataset_id))
            if source_group is None or removal.entry_id not in (source_group.member_asset_ids or []):
                raise ApiError(409, 'TRASH_STATE_CONFLICT', '照片已不属于该组的待清理范围。', message_key='the_photo_no_longer_belongs_to_this_group_s_cleanup_selection')
            source_group.member_asset_ids = [asset_id for asset_id in source_group.member_asset_ids if asset_id != removal.entry_id]
            if session.get(LibraryEntryRemoval, ('asset', removal.entry_id)) is not None:
                session.delete(session.get(LibraryEntryRemoval, ('asset', removal.entry_id)))
        else:
            session.delete(removal)
        if item.entry_type == 'asset':
            restored_asset_ids.add(removal.entry_id)
        else:
            restored_asset_ids.update(removal.member_asset_ids or [])
        restored += 1
    for asset_id in restored_asset_ids:
        removal = session.get(LibraryEntryRemoval, ('asset', asset_id))
        if removal is not None:
            session.delete(removal)
        for group_removal in session.scalars(select(LibraryEntryRemoval).where(LibraryEntryRemoval.entry_type == 'dataset')).all():
            if asset_id in (group_removal.member_asset_ids or []):
                group_removal.member_asset_ids = [member_id for member_id in group_removal.member_asset_ids if member_id != asset_id]
    return LibraryTrashRestoreOut.model_validate({'restored_count': restored})
