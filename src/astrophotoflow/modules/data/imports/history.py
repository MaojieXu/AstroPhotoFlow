"""Compact terminal import plans without discarding request or file identities."""
import json
from copy import deepcopy
from uuid import UUID

from sqlalchemy import select

from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.imports.models import AssetTask


def compact_completed_imports(database, settings, *, remove_unused_inspections=False, task_ids=None, inspection_ids=None):
    reclaimed, compacted, scans = 0, [], set()
    with database.write_session() as session:
        tasks = session.scalars(select(AssetTask)).all()
        by_id = {task.id: task for task in tasks}
        protected = set()
        for task in tasks:
            if task.status == 'completed':
                continue
            current = task
            while current and current.id not in protected:
                protected.add(current.id)
                root_id = (current.image_import_plan or {}).get('root_task_id')
                if root_id:
                    protected.add(root_id)
                current = by_id.get(current.retry_of_task_id)
        for task in tasks:
            if task_ids is not None and task.id not in task_ids:
                continue
            root_id = (task.image_import_plan or {}).get('root_task_id', task.id)
            if task.status != 'completed' or task.id in protected or root_id in protected:
                continue
            scan = (task.image_import_plan or {}).get('scan_id')
            if scan:
                scans.add(str(UUID(scan)))
            if (task.report or {}).get('history_compacted'):
                continue
            before = len(json.dumps([task.sources, task.image_import_plan, task.import_defaults_snapshot], ensure_ascii=False).encode())
            task.sources = [{key: deepcopy(value) for key, value in source.items() if key != 'entries'} for source in task.sources]
            task.import_defaults_snapshot = {}
            plan = deepcopy(task.image_import_plan)
            if plan:
                published = set(plan.get('publication', {}).get('published_file_ids', []))
                if set(plan.get('files', {})).issubset(published):
                    plan = {key: value for key, value in plan.items() if key in {
                        'request_id', 'scan_id', 'destination', 'storage_mode', 'accept_unknown', 'root_task_id',
                        'publication', 'publication_requests', 'files'}}
                    plan['files'] = {identity: {} for identity in plan.get('files', {})}
                    task.image_import_plan = plan
            task.report = {**(task.report or {}), 'history_compacted': True}
            after = len(json.dumps([task.sources, task.image_import_plan, task.import_defaults_snapshot], ensure_ascii=False).encode())
            reclaimed += max(0, before - after)
            compacted.append(task.id)
        protected_scans = {(task.image_import_plan or {}).get('scan_id') for task in tasks
                           if task.status != 'completed' or task.id in protected}
    directory = (settings.data_dir / 'import-inspections').resolve()
    if not directory.is_relative_to(settings.data_dir.resolve()):
        raise ApiError(409, 'INVALID_STORAGE_PATH', 'Inspection directory is outside the workspace data directory.')
    if remove_unused_inspections and all(task.status == 'completed' for task in tasks):
        for path in directory.glob('*.json'):
            try:
                scans.add(str(UUID(path.stem)))
            except ValueError:
                continue
    removed = []
    if inspection_ids is not None:
        scans.intersection_update(inspection_ids)
    for identity in sorted(scans - protected_scans):
        path = directory / (identity + '.json')
        if path.exists():
            if not path.resolve().is_relative_to(directory):
                raise ApiError(409, 'INVALID_STORAGE_PATH', 'Inspection manifest resolves outside the inspection directory.')
            path.unlink()
            removed.append(identity)
    return {'task_ids': compacted, 'payload_bytes_removed': reclaimed, 'removed_scan_ids': removed,
            'retained_request_receipts': len(tasks)}
