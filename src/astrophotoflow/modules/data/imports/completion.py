from __future__ import annotations
import logging
from datetime import UTC, datetime
from pathlib import Path
from sqlalchemy import select
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.calibration.checks import validate_calibration_bindings
from astrophotoflow.modules.data.datasets.bindings import dataset_bindings
from astrophotoflow.modules.data.datasets.calibration import require_subframe
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember
from astrophotoflow.modules.data.datasets.service import publish_dataset_members
from astrophotoflow.modules.data.imports.context import ImportTaskContext
from astrophotoflow.modules.data.imports.models import AssetTask, AssetTaskItem
logger = logging.getLogger(__name__)

def publish_dataset(database: Database, task_data: ImportTaskContext, task_id: str, *, content_ready: bool=True) -> dict | None:
    target_id = task_data.target_dataset_id
    if not target_id:
        return None
    try:
        with database.write_session() as session:
            task = session.get(AssetTask, task_id)
            successes = session.scalars(select(AssetTaskItem).where(AssetTaskItem.task_id == task_id, AssetTaskItem.asset_id.is_not(None)).order_by(AssetTaskItem.position)).all()
            if not successes:
                return None
            dataset = session.get(Dataset, target_id)
            if dataset is None and task.dataset_base_revision is not None:
                raise ApiError(409, 'INVALID_REFERENCE', 'The append destination disappeared. Imported originals are retained.')
            creating = dataset is None
            if dataset is None:
                base_members = []
            else:
                base_members = session.scalars(select(DatasetMember).where(DatasetMember.dataset_id == dataset.id).order_by(DatasetMember.position)).all()
            existing_versions = {member.asset_id for member in base_members}
            additions = []
            fixed = dataset
            bindings = dataset_bindings(fixed) if fixed else {}
            checks_require_content = any((target and target.get('kind') == 'asset' for target in bindings.values()))
            if checks_require_content and (not content_ready):
                return None
            if checks_require_content:
                successes = [item for item in successes if item.content_status == 'available']
            excluded = []
            uploaded_names = {file['stored_name']: file['name'] for file in task_data.upload_files}
            for item in successes:
                if item.asset_id in existing_versions:
                    continue
                try:
                    require_subframe(session.get(Asset, item.asset_id))
                    validate_calibration_bindings(session, [item.asset_id], bindings)
                except ApiError as exc:
                    name = uploaded_names.get(item.source_path, Path(item.source_path).name)
                    excluded.append({'asset_id': item.asset_id, 'name': name, 'code': exc.code, 'message': exc.message})
                    continue
                additions.append((item.asset_id, Path(item.source_path).name if not item.root_id else item.source_path))
                existing_versions.add(item.asset_id)
            if excluded:
                task.report = {**(task.report or {}), 'dataset_publish_error': {'code': 'DATASET_MEMBERS_EXCLUDED', 'files': excluded}, 'dataset_exclusions': excluded}
            if not additions:
                return None
            if dataset is None:
                dataset = Dataset(library_directory=(task.report or {}).get('library_directory'), id=target_id, name=task.dataset_name or '素材集', notes=task.notes, status='active', revision=1)
                session.add(dataset)
                session.flush()
            if not creating:
                expected = task.dataset_base_revision
                if expected is None or dataset.revision != expected:
                    raise RuntimeError(f'DATASET_REVISION_CONFLICT:{expected}:{dataset.revision}')
            publish_dataset_members(session, dataset, [member.asset_id for member in base_members] + [identity for identity, _ in additions], relative_paths=dict(additions))
            if creating:
                dataset.revision = 1
            task.dataset_base_revision = dataset.revision
            task.dataset_id = target_id
            task.report = {**(task.report or {}), 'dataset_id': dataset.id}
            session.flush()
            return {'dataset_id': dataset.id}
    except ApiError as exc:
        with database.write_session() as session:
            task = session.get(AssetTask, task_id)
            task.report = {**(task.report or {}), 'dataset_publish_error': {
                'code': exc.code, 'message': exc.message, 'fields': exc.fields,
            }}
        return None
    except RuntimeError as exc:
        text = str(exc)
        if not text.startswith('DATASET_REVISION_CONFLICT:'):
            raise
        _, expected, observed = text.split(':')
        with database.write_session() as session:
            task = session.get(AssetTask, task_id)
            successful = session.scalars(select(AssetTaskItem.asset_id).where(AssetTaskItem.task_id == task_id, AssetTaskItem.asset_id.is_not(None)).order_by(AssetTaskItem.position)).all()
            dataset = session.get(Dataset, target_id)
            current_members = set()
            if dataset is not None and dataset.id is not None:
                current_members = set(session.scalars(select(DatasetMember.asset_id).where(DatasetMember.dataset_id == dataset.id)).all())
            pending = [identity for identity in successful if identity not in current_members]
            conflict = {'code': 'REVISION_CONFLICT', 'dataset_id': target_id, 'expected_revision': int(expected) if expected != 'None' else None, 'observed_revision': int(observed), 'pending_asset_ids': pending}
            task.report = {**(task.report or {}), 'dataset_publish_error': conflict}
        return None

def finish_task(database: Database, task_id: str, was_cancelled: bool) -> None:
    with database.write_session() as session:
        task = session.get(AssetTask, task_id)
        if task.status == 'interrupted':
            return
        items = session.scalars(select(AssetTaskItem).where(AssetTaskItem.task_id == task_id)).all()
        successes = sum((item.content_status == 'available' for item in items))
        errors = any((item.status in {'failed', 'completed_with_errors'} or item.metadata_status == 'failed' for item in items))
        skipped = sum((item.status == 'skipped' for item in items))
        if was_cancelled:
            status = 'cancelled'
        elif not successes:
            status = 'failed'
        elif errors or (task.report or {}).get('dataset_publish_error'):
            status = 'completed_with_errors'
        else:
            status = 'completed'
        task.status = status
        task.report = {**(task.report or {}), 'counts': {'enumerated': len(items), 'content_succeeded': successes, 'failed': sum((item.status == 'failed' for item in items)), 'skipped': skipped, 'processing_issues': sum((item.status == 'completed_with_errors' or item.metadata_status == 'failed' for item in items)), 'cancelled': sum((item.status == 'cancelled' for item in items))}}
        task.updated_at = datetime.now(UTC)
