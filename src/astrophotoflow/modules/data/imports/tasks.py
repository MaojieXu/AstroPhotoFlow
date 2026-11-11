from __future__ import annotations
from copy import deepcopy
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session
from astrophotoflow.contracts.imports import AssetTaskOut, AssetTaskPage, ImportAccepted, ImportTaskStateOut, RetryCreate
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.core.localization import localized_error
from astrophotoflow.modules.data.datasets.models import Dataset
from astrophotoflow.modules.data.imports.models import AssetTask, AssetTaskItem

def task_out(session, task: AssetTask, items_limit: int, items_offset: int) -> AssetTaskOut:
    total = session.scalar(select(func.count()).select_from(AssetTaskItem).where(AssetTaskItem.task_id == task.id)) or 0
    items = session.scalars(select(AssetTaskItem).where(AssetTaskItem.task_id == task.id).order_by(AssetTaskItem.position, AssetTaskItem.id).limit(items_limit).offset(items_offset)).all()
    completed = session.scalar(select(func.count()).select_from(AssetTaskItem).where(AssetTaskItem.task_id == task.id, AssetTaskItem.status.in_({'completed', 'completed_with_errors', 'failed', 'cancelled', 'skipped'}))) or 0
    from astrophotoflow.modules.data.datasets.models import DatasetMember
    owners = {identity: (dataset_id, name) for identity, dataset_id, name in session.execute(
        select(DatasetMember.asset_id, Dataset.id, Dataset.name).join(Dataset, Dataset.id == DatasetMember.dataset_id)
        .where(DatasetMember.asset_id.in_([row.asset_id for row in items if row.asset_id])))}
    return AssetTaskOut.model_validate({'id': UUID(task.id), 'status': task.status, 'sources': task.sources, 'storage_mode': task.storage_mode, 'classification': task.classification, 'parameters': task.parameters, 'notes': task.notes, 'dataset_name': task.dataset_name, 'target_dataset_id': UUID(task.target_dataset_id) if task.target_dataset_id else None, 'dataset_base_revision': task.dataset_base_revision, 'dataset_id': UUID(task.dataset_id) if task.dataset_id else None, 'enumeration_completed': task.enumeration_completed, 'retry_of_task_id': UUID(task.retry_of_task_id) if task.retry_of_task_id else None, 'report': task.report or {}, 'error': task.error, 'created_at': task.created_at.replace(tzinfo=UTC) if task.created_at.tzinfo is None else task.created_at.astimezone(UTC), 'updated_at': task.updated_at.replace(tzinfo=UTC) if task.updated_at.tzinfo is None else task.updated_at.astimezone(UTC), 'items': [{'dataset_id': UUID(owners[row.asset_id][0]) if row.asset_id in owners else None, 'dataset_name': owners.get(row.asset_id, (None, None))[1], 'id': UUID(row.id), 'task_id': UUID(row.task_id), 'root_item_id': UUID(row.root_item_id), 'retry_of_item_id': UUID(row.retry_of_item_id) if row.retry_of_item_id else None, 'root_id': row.root_id, 'source_path': row.source_path, 'position': row.position, 'status': row.status, 'content_status': row.content_status, 'metadata_status': row.metadata_status, 'preview_status': row.preview_status, 'asset_id': UUID(row.asset_id) if row.asset_id else None, 'error': row.error, 'created_at': row.created_at.replace(tzinfo=UTC) if row.created_at.tzinfo is None else row.created_at.astimezone(UTC), 'updated_at': row.updated_at.replace(tzinfo=UTC) if row.updated_at.tzinfo is None else row.updated_at.astimezone(UTC)} for row in items], 'items_total': total, 'items_completed': completed, 'items_limit': items_limit, 'items_offset': items_offset})

def list_asset_tasks(session: Session, limit: int=50, offset: int=0, status: Literal['queued', 'running', 'cancelling', 'completed', 'completed_with_errors', 'failed', 'cancelled', 'interrupted', 'all']='all') -> AssetTaskPage:
    filters = [] if status == 'all' else [AssetTask.status == status]
    total = session.scalar(select(func.count()).select_from(AssetTask).where(*filters)) or 0
    page = select(AssetTask.id, AssetTask.status, AssetTask.dataset_name, AssetTask.target_dataset_id, AssetTask.dataset_id, AssetTask.enumeration_completed, AssetTask.error, AssetTask.created_at, AssetTask.updated_at, AssetTask.report['destination'].label('destination'), AssetTask.report['registration'].label('registration'), AssetTask.report['content'].label('content'), AssetTask.report['preview'].label('preview'), AssetTask.report['dataset_exclusions'].label('dataset_exclusions'), AssetTask.report['dataset_publish_error'].label('dataset_publish_error')).where(*filters).order_by(AssetTask.created_at.desc(), AssetTask.id).limit(limit).offset(offset).cte('task_page')
    completed = AssetTaskItem.status.in_({'completed', 'completed_with_errors', 'failed', 'cancelled', 'skipped'})
    counts = select(AssetTaskItem.task_id, func.count().label('items_total'), func.sum(case((completed, 1), else_=0)).label('items_completed')).where(AssetTaskItem.task_id.in_(select(page.c.id))).group_by(AssetTaskItem.task_id).subquery()
    rows = session.execute(select(*page.c, func.coalesce(counts.c.items_total, 0).label('items_total'), func.coalesce(counts.c.items_completed, 0).label('items_completed')).outerjoin(counts, counts.c.task_id == page.c.id).order_by(page.c.created_at.desc(), page.c.id)).mappings()
    items = []
    for row in rows:
        item = dict(row)
        for key in ('id', 'target_dataset_id', 'dataset_id'):
            if item[key] is not None:
                item[key] = UUID(item[key])
        item['report'] = {key: item.pop(key) for key in ('registration', 'content', 'preview', 'destination')}
        item['report']['dataset_exclusions'] = item.pop('dataset_exclusions') or []
        item['report']['dataset_publish_error'] = item.pop('dataset_publish_error')
        for key in ('created_at', 'updated_at'):
            value = item[key]
            item[key] = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        items.append(item)
    return AssetTaskPage.model_validate({'items': items, 'total': total, 'limit': limit, 'offset': offset})

def get_asset_task(session: Session, task_id: UUID, items_limit: int=50, items_offset: int=0) -> AssetTaskOut:
    task = session.get(AssetTask, str(task_id))
    if task is None:
        raise not_found()
    return AssetTaskOut.model_validate(task_out(session, task, items_limit, items_offset))

def cancel_asset_task(session: Session, task_id: UUID) -> ImportTaskStateOut:
    task = session.get(AssetTask, str(task_id))
    if task is None:
        raise not_found()
    if task.status not in {'queued', 'running', 'cancelling', 'interrupted'}:
        raise ApiError(409, 'TASK_STATE_CONFLICT', '当前任务状态不能取消。', message_key='this_task_cannot_be_canceled_in_its_current_state')
    task.status = 'cancelling' if task.status in {'running', 'cancelling'} else 'cancelled'
    task.updated_at = datetime.now(UTC)
    if task.status == 'cancelled':
        for item in session.scalars(select(AssetTaskItem).where(AssetTaskItem.task_id == task.id, AssetTaskItem.status.in_({'queued', 'interrupted', 'running'}))).all():
            item.status = 'cancelled'
            item.updated_at = datetime.now(UTC)
    return ImportTaskStateOut.model_validate({'task_id': UUID(task.id), 'status': task.status})

def resume_asset_task(session: Session, task_id: UUID) -> ImportAccepted:
    task = session.get(AssetTask, str(task_id))
    if task is None:
        raise not_found()
    if task.status != 'interrupted':
        raise ApiError(409, 'TASK_STATE_CONFLICT', '只有服务中断的任务可恢复。', message_key='only_tasks_interrupted_by_the_service_can_be_resumed')
    if (task.report or {}).get('upload_manifest') and (not (task.report or {}).get('upload_complete')):
        raise ApiError(409, 'UPLOAD_REQUIRES_SELECTION', '上传未完成，请重新选择文件并创建导入批次。', message_key='the_upload_is_incomplete_select_files_again_and_create_a_new_import_batch')
    task.status = 'queued'
    task.error = None
    task.updated_at = datetime.now(UTC)
    for item in session.scalars(select(AssetTaskItem).where(AssetTaskItem.task_id == task.id, AssetTaskItem.status == 'interrupted')).all():
        item.status = 'queued'
        item.updated_at = datetime.now(UTC)
    return ImportAccepted.model_validate({'task_id': UUID(task.id), 'status': 'queued'})

def retry_asset_task(session: Session, task_id: UUID, body: RetryCreate) -> ImportAccepted:
    original = session.get(AssetTask, str(task_id))
    if original is None:
        raise not_found()
    if original.status not in {'failed', 'completed_with_errors', 'cancelled'}:
        raise ApiError(409, 'TASK_STATE_CONFLICT', '当前任务状态不能重试。', message_key='this_task_cannot_be_retried_in_its_current_state')
    selected_ids = [str(value) for value in body.item_ids]
    if len(set(selected_ids)) != len(selected_ids):
        raise ApiError(422, 'VALIDATION_ERROR', '重试项不能重复。', message_key='retry_entries_must_not_be_duplicated')
    items = session.scalars(select(AssetTaskItem).where(AssetTaskItem.task_id == original.id, AssetTaskItem.id.in_(selected_ids)).order_by(AssetTaskItem.position)).all()
    if len(items) != len(selected_ids):
        raise not_found()
    if any((item.status == 'skipped' or not (item.content_status in {'pending', 'failed'} or item.metadata_status == 'failed' or item.preview_status in {'pending', 'failed'}) for item in items)):
        raise ApiError(422, 'VALIDATION_ERROR', '所选项没有失败或未完成阶段，不能重试。', message_key='the_selected_entry_has_no_failed_or_incomplete_stage_to_retry')
    source_task = session.get(AssetTask, original.retry_of_task_id) if original.retry_of_task_id else original
    retry_task_id = str(uuid4())
    target_dataset_id = source_task.target_dataset_id
    dataset = session.get(Dataset, target_dataset_id) if target_dataset_id else None
    source_stamps = {(entry['root_id'], entry['path']): entry.get('source_stamp') for source in original.sources for entry in source.get('entries', [])}
    retry_task = AssetTask(id=retry_task_id, status='queued', sources=[{'root_id': item.root_id, 'path': item.source_path, 'kind': 'file', 'enumeration_completed': True, 'error': None, 'entries': [{'root_id': item.root_id, 'path': item.source_path, 'source_stamp': source_stamps.get((item.root_id, item.source_path))}]} for item in items], storage_mode=source_task.storage_mode, classification=source_task.classification, parameters=source_task.parameters, notes=source_task.notes, dataset_name=source_task.dataset_name, import_defaults_snapshot=source_task.import_defaults_snapshot, target_dataset_id=target_dataset_id, dataset_base_revision=dataset.revision if dataset else None, dataset_id=source_task.dataset_id, enumeration_completed=True, retry_of_task_id=original.id, report={**{key: deepcopy(source_task.report[key]) for key in ('output_registration', 'output_name', 'output_colour_layout', 'output_provenance', 'output_identity', 'output_calibration_evidence', 'output_value_sources', 'output_processing_calibration') if key in (source_task.report or {})}, 'destination': deepcopy((source_task.report or {}).get('destination')), 'library_capture_profile': (source_task.report or {}).get('library_capture_profile'), 'library_directory': (source_task.report or {}).get('library_directory'), 'calibration_status': (source_task.report or {}).get('calibration_status', 'Unknown'), 'calibration_reason': (source_task.report or {}).get('calibration_reason'), 'preview_stretch_groups': (original.report or {}).get('preview_stretch_groups', {}), 'upload_manifest': bool((source_task.report or {}).get('upload_manifest')), 'upload_complete': bool((source_task.report or {}).get('upload_complete')), 'upload_source_task_id': (source_task.report or {}).get('upload_source_task_id', source_task.id), 'upload_files': (source_task.report or {}).get('upload_files', [])}, error=None, created_at=datetime.now(UTC), updated_at=datetime.now(UTC))
    context = deepcopy((source_task.report or {}).get('destination'))
    if context and context.get('project_id'):
        previous_link = context.get('project_link') or {}
        context['project_base_revision'] = previous_link.get('project_revision', context['project_base_revision'])
        context['project_link'] = {'state': 'pending'}
        retry_task.report = {**retry_task.report, 'destination': context}
    session.add(retry_task)
    if original.image_import_plan:
        retry_task.image_import_plan = deepcopy(original.image_import_plan)
    if (original.report or {}).get('agent_batch'):
        batch = original.report['agent_batch']
        retry_task.report = {**retry_task.report, 'agent_batch': {**batch, 'root_task_id': batch.get('root_task_id') or original.id}}
    session.flush()
    for position, item in enumerate(items):
        source_item = session.get(AssetTaskItem, item.retry_of_item_id) if item.retry_of_item_id else item
        root_item = source_item.root_item_id if source_item else item.root_item_id
        session.add(AssetTaskItem(id=str(uuid4()), task_id=retry_task_id, root_item_id=root_item, retry_of_item_id=item.id, root_id=item.root_id, source_path=item.source_path, source_identity=item.source_identity, position=position, status='queued', content_status=item.content_status, metadata_status=item.metadata_status, preview_status=item.preview_status, asset_id=item.asset_id, error=None, created_at=datetime.now(UTC), updated_at=datetime.now(UTC)))
    session.flush()
    return ImportAccepted.model_validate({'task_id': UUID(retry_task_id), 'status': 'queued'})

def mark_interrupted_tasks(database: Database, *, locale='en') -> int:
    count = 0
    with database.write_session() as session:
        tasks = session.scalars(select(AssetTask).where(AssetTask.status.in_({'queued', 'running', 'cancelling'}))).all()
        for task in tasks:
            task.status = 'interrupted'
            task.error = localized_error(locale, 'SERVICE_INTERRUPTED', 'import_interrupted').model_dump()
            task.updated_at = datetime.now(UTC)
            count += 1
        running_items = session.scalars(select(AssetTaskItem).where(AssetTaskItem.status == 'running')).all()
        for item in running_items:
            item.status = 'interrupted'
            item.updated_at = datetime.now(UTC)
    return count
