from __future__ import annotations
import logging
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import UTC, datetime
from threading import Condition
from sqlalchemy import func, select
import astrophotoflow.modules.data.imports.completion as stage_imports_completion
import astrophotoflow.modules.data.imports.enumeration as stage_imports_enumeration
import astrophotoflow.modules.data.imports.errors as stage_imports_errors
import astrophotoflow.modules.data.imports.progress as stage_imports_progress
import astrophotoflow.modules.data.imports.stages as stage_imports_stages
import astrophotoflow.modules.data.imports.workers as stage_imports_workers
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.localization import localized_error, workspace_locale
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember
from astrophotoflow.modules.data.imports.context import ImportTaskContext
from astrophotoflow.modules.data.imports.models import AssetTask, AssetTaskItem
from astrophotoflow.modules.data.imports.progress import ImportProgress
from astrophotoflow.modules.data.media.display import DisplayPreviews
logger = logging.getLogger(__name__)

def process_task(database: Database, settings: Settings, task_id: str, workers=None) -> None:
    if workers is None:
        with stage_imports_workers.import_workers(settings) as owned_workers:
            return process_task(database, settings, task_id, owned_workers)
    try:
        with database.write_session() as session:
            task = session.get(AssetTask, task_id)
            if task is None or task.status != 'queued':
                return
            task.status = 'running'
            task.updated_at = datetime.now(UTC)
            task_data = ImportTaskContext.from_task(task)
        if not task_data.retry_of_task_id:
            stage_imports_enumeration.enumerate_task(database, settings, task_id, task_data.sources, upload_manifest=task_data.upload_manifest)
        with database.read_session() as session:
            items = session.scalars(select(AssetTaskItem).where(AssetTaskItem.task_id == task_id).order_by(AssetTaskItem.position)).all()
            item_ids = [item.id for item in items if item.status in {'queued', 'interrupted', 'running'}]
            counted = {item.id for item in items if item.asset_id is not None or item.status in {'failed', 'skipped'}}
        progress = ImportProgress(database, task_id)
        task_data.progress = progress
        task_data.source_stamps = {(entry['root_id'], entry['path']): entry['source_stamp'] for source in task_data.sources for entry in source.get('entries', []) if entry.get('source_stamp')}
        task_data.metadata_snapshots = {(entry['root_id'], entry['path']): entry['metadata_snapshot'] for source in task_data.sources for entry in source.get('entries', []) if entry.get('metadata_snapshot')}
        stage_imports_progress.registration_progress(database, task_id, len(items), len(counted))
        registered_ids = []
        file_workers, preview_workers = workers
        condition = Condition()
        registration_finished = False

        def wake_copy(_future):
            with condition:
                condition.notify()

        def copy_registered():
            pending = set()
            index = 0
            try:
                while True:
                    with condition:
                        finished = {future for future in pending if future.done()}
                        pending.difference_update(finished)
                        for future in finished:
                            future.result()
                        while index < len(registered_ids) and len(pending) < settings.file_workers * 2:
                            future = file_workers.submit(stage_imports_stages.run_content_item, database, settings, task_data, registered_ids[index])
                            pending.add(future)
                            future.add_done_callback(wake_copy)
                            index += 1
                        if registration_finished and index == len(registered_ids) and (not pending):
                            return
                        if any((future.done() for future in pending)):
                            continue
                        condition.wait()
            finally:
                wait(pending)
                for future in pending:
                    future.result()
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix='asset-copy-dispatch') as dispatcher:
            copied = dispatcher.submit(copy_registered)
            try:
                for item_id in item_ids:
                    if stage_imports_progress.task_cancelled(database, task_id):
                        with database.write_session() as session:
                            session.get(AssetTaskItem, item_id).status = 'cancelled'
                        continue
                    try:
                        stage_imports_stages.register_asset(database, settings, task_data, item_id)
                    except Exception as exc:
                        logger.exception('asset registration failed task_id=%s item_id=%s', task_id, item_id)
                        with database.write_session() as session:
                            item = session.get(AssetTaskItem, item_id)
                            item.status, item.content_status = ('failed', 'failed')
                            item.metadata_status, item.preview_status = ('unsupported', 'unsupported')
                            item.error = stage_imports_errors.import_error(settings, exc, code='REGISTRATION_FAILED', message_key='import_registration_failed')
                    else:
                        with condition:
                            registered_ids.append(item_id)
                            condition.notify()
                    progress.update()
                publication = None
                if not task_data.image_import_plan:
                    publication = stage_imports_completion.publish_dataset(database, task_data, task_id, content_ready=False)
                progress.flush(registration_completed=not stage_imports_progress.task_cancelled(database, task_id))
            finally:
                with condition:
                    registration_finished = True
                    condition.notify()
            copied.result()
        progress.flush(content_completed=not stage_imports_progress.task_cancelled(database, task_id))
        if task_data.image_import_plan:
            from astrophotoflow.modules.data.imports.explicit import settle_image_import
            settle_image_import(database, task_id)
        elif publication is None:
            stage_imports_completion.publish_dataset(database, task_data, task_id)
        with database.write_session() as session:
            for item_id in registered_ids:
                item = session.get(AssetTaskItem, item_id)
                if item.content_status == 'available' and item.status != 'cancelled':
                    if item.preview_status == 'pending':
                        item.preview_status = 'not_requested'
                    item.status = 'completed_with_errors' if item.metadata_status == 'failed' else 'completed'
        progress.flush()
        stage_imports_completion.finish_task(database, task_id, stage_imports_progress.task_cancelled(database, task_id))
        cover_id = None
        with database.read_session() as session:
            task = session.get(AssetTask, task_id)
            dataset = session.get(Dataset, task.dataset_id) if task.dataset_id else None
            if dataset is not None and dataset.id:
                cover_id = session.scalar(select(DatasetMember.asset_id).where(DatasetMember.dataset_id == dataset.id).order_by(DatasetMember.position).limit(1))
                incoming = set(session.scalars(select(AssetTaskItem.asset_id).where(AssetTaskItem.task_id == task_id, AssetTaskItem.id.in_(registered_ids))))
                if cover_id not in incoming:
                    cover_id = None
        if cover_id is not None:
            try:
                DisplayPreviews(database, settings, preview_workers, recover=False).schedule(cover_id)
            except Exception:
                logger.exception('cover preview could not be scheduled task_id=%s', task_id)
    except Exception:
        logger.exception('asset import task failed task_id=%s', task_id)
        with database.write_session() as session:
            task = session.get(AssetTask, task_id)
            if task is not None and task.status not in {'cancelled', 'interrupted'}:
                task.status = 'completed_with_errors' if session.scalar(select(func.count()).select_from(AssetTaskItem).where(AssetTaskItem.task_id == task_id, AssetTaskItem.content_status == 'available')) else 'failed'
                task.error = localized_error(workspace_locale(settings.workspace), 'INTERNAL_ERROR', 'import_background_failed').model_dump()
                task.updated_at = datetime.now(UTC)
