from __future__ import annotations

import shutil
from collections.abc import AsyncIterable
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from astrophotoflow.contracts.imports import (
    ImportAccepted,
    ImportTaskStateOut,
    UploadImportCreate,
    UploadReceipt,
)
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.core.localization import localized_error, workspace_locale
from astrophotoflow.modules.data.equipment.references import validate_import_equipment
from astrophotoflow.modules.data.equipment.snapshots import capture_defaults_snapshot
from astrophotoflow.modules.data.imports.models import AssetTask, AssetTaskItem


def create_upload(session: Session, settings: Settings, body: UploadImportCreate) -> ImportAccepted:
    validate_import_equipment(session, body.parameters.model_dump(mode='json'))
    defaults_snapshot = capture_defaults_snapshot(session, body.parameters, body.equipment).model_dump(mode='json', exclude_unset=True)
    task_id = str(uuid4())
    staging = settings.data_dir / 'upload-staging' / task_id
    staging.mkdir(parents=True, exist_ok=True)
    files = []
    sources = []
    now = datetime.now(UTC)
    for position, file in enumerate(body.files):
        suffix = ''.join(Path(file.name).suffixes[-2:]) if file.name.lower().endswith(('.fits.fz', '.fit.fz', '.fts.fz')) else Path(file.name).suffix
        stored_name = f'{position}{suffix.lower()}'
        files.append({'name': file.name, 'size': file.size, 'received': 0, 'stored_name': stored_name})
        sources.append({'root_id': '__upload__', 'path': stored_name, 'kind': 'file', 'enumeration_completed': True, 'error': None})
        session.add(AssetTaskItem(id=str(uuid4()), task_id=task_id, root_item_id=str(uuid4()), retry_of_item_id=None, root_id='__upload__', source_path=stored_name, source_identity=f'upload:{task_id}:{position}', position=position, status='queued', content_status='pending', metadata_status='pending', preview_status='pending', error=None, created_at=now, updated_at=now))
    create_dataset = body.create_dataset or len(body.files) > 1
    task = AssetTask(id=task_id, status='queued', sources=sources, storage_mode='managed', classification=body.classification.model_dump(mode='json', exclude_unset=True), parameters=body.parameters.model_dump(mode='json', exclude_unset=True), import_defaults_snapshot=defaults_snapshot, notes=body.notes, dataset_name=body.dataset_name or body.files[0].name if create_dataset else None, target_dataset_id=str(uuid4()) if create_dataset else None, dataset_base_revision=None, dataset_id=None, enumeration_completed=True, retry_of_task_id=None, report={'upload_manifest': True, 'upload_files': files}, error=None, created_at=now, updated_at=now)
    session.add(task)
    session.flush()
    return ImportAccepted.model_validate({'task_id': UUID(task_id), 'status': 'queued'})

async def upload_file(database: Database, settings: Settings, task_id: UUID, index: int, chunks: AsyncIterable[bytes]) -> UploadReceipt:
    with database.read_session() as session:
        task = session.get(AssetTask, str(task_id))
        files = (task.report or {}).get('upload_files', []) if task else []
        if task is None or not (task.report or {}).get('upload_manifest') or index < 0 or (index >= len(files)):
            raise not_found()
        entry = dict(files[index])
        if entry['received'] != 0:
            raise ApiError(409, 'UPLOAD_ALREADY_RECEIVED', '该文件已上传；请重新选择文件创建导入批次。', message_key='this_file_has_already_been_uploaded_select_files_again_to_create_a_new_impo')
    target = settings.data_dir / 'upload-staging' / str(task_id) / entry['stored_name']
    received = 0
    try:
        with target.open('xb') as stream:
            async for chunk in chunks:
                stream.write(chunk)
                received += len(chunk)
    except Exception as exc:
        with database.write_session() as session:
            task = session.get(AssetTask, str(task_id))
            if task and task.status == 'queued':
                task.status = 'failed'
                task.error = localized_error(workspace_locale(settings.workspace), 'UPLOAD_FAILED', 'upload_interrupted').model_dump()
                task.updated_at = datetime.now(UTC)
                for item in session.scalars(select(AssetTaskItem).where(AssetTaskItem.task_id == task.id)).all():
                    item.status, item.content_status, item.error = ('failed', 'failed', task.error)
                    item.updated_at = datetime.now(UTC)
        shutil.rmtree(settings.data_dir / 'upload-staging' / str(task_id), ignore_errors=True)
        raise ApiError(400, 'UPLOAD_FAILED', '文件上传中断，请重新选择文件创建导入批次。', message_key='the_upload_was_interrupted_select_files_again_to_create_a_new_import_batch') from exc
    if received != entry['size']:
        target.unlink(missing_ok=True)
        raise ApiError(400, 'UPLOAD_SIZE_MISMATCH', '上传文件大小与选择时记录不一致，请重新选择文件。', message_key='the_upload_size_differs_from_the_selected_file_size_select_the_file_again')
    with database.write_session() as session:
        task = session.get(AssetTask, str(task_id))
        files = list((task.report or {}).get('upload_files', []))
        files[index] = {**files[index], 'received': received}
        task.report = {**(task.report or {}), 'upload_files': files}
        task.updated_at = datetime.now(UTC)
    return UploadReceipt.model_validate({'received': received})

def start_upload_import(session: Session, task_id: UUID) -> ImportAccepted:
    task = session.get(AssetTask, str(task_id))
    if task is None or not (task.report or {}).get('upload_manifest'):
        raise not_found()
    if any(file['received'] != file['size'] for file in task.report['upload_files']):
        raise ApiError(409, 'UPLOAD_INCOMPLETE', '所有文件上传完成后才能开始导入。', message_key='all_file_uploads_must_finish_before_import_can_start')
    if task.status != 'queued':
        raise ApiError(409, 'TASK_STATE_CONFLICT', '该上传批次已开始处理。', message_key='processing_has_already_started_for_this_upload_batch')
    task.report = {**task.report, 'upload_complete': True}
    task.updated_at = datetime.now(UTC)
    return ImportAccepted.model_validate({'task_id': UUID(task.id), 'status': 'queued'})

def fail_upload(session: Session, settings: Settings, task_id: UUID) -> ImportTaskStateOut:
    task = session.get(AssetTask, str(task_id))
    if task is None or not (task.report or {}).get('upload_manifest'):
        raise not_found()
    if task.status != 'queued':
        raise ApiError(409, 'TASK_STATE_CONFLICT', '后台处理已开始，不能按上传失败取消。', message_key='background_processing_has_started_it_cannot_be_canceled_as_an_upload_failur')
    task.status = 'failed'
    task.error = localized_error(workspace_locale(settings.workspace), 'UPLOAD_FAILED', 'upload_incomplete').model_dump()
    task.updated_at = datetime.now(UTC)
    for item in session.scalars(select(AssetTaskItem).where(AssetTaskItem.task_id == task.id)).all():
        item.status = 'failed'
        item.content_status = 'failed'
        item.error = task.error
        item.updated_at = datetime.now(UTC)
    shutil.rmtree(settings.data_dir / 'upload-staging' / task.id, ignore_errors=True)
    return ImportTaskStateOut.model_validate({'task_id': UUID(task.id), 'status': task.status})
