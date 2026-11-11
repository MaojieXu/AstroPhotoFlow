from __future__ import annotations
import logging
import os
from datetime import UTC, datetime
from uuid import uuid4
from sqlalchemy import select
import astrophotoflow.modules.data.imports.errors as stage_imports_errors
import astrophotoflow.modules.data.imports.progress as stage_imports_progress
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.localization import localized_error, workspace_locale
from astrophotoflow.modules.data.files import enumerate_source
from astrophotoflow.modules.data.imports.models import AssetTask, AssetTaskItem
logger = logging.getLogger(__name__)

def set_enumeration(database: Database, task_id: str, sources: list[dict], complete: bool) -> None:
    with database.write_session() as session:
        task = session.get(AssetTask, task_id)
        task.sources = sources
        task.enumeration_completed = complete
        task.updated_at = datetime.now(UTC)

def register_source_item(database: Database, task_id: str, entry: dict, position: int, known: set[str], *, locale='en') -> None:
    identity = entry['identity']
    with database.write_session() as session:
        duplicate = identity in known
        item = AssetTaskItem(id=str(uuid4()), task_id=task_id, root_item_id=str(uuid4()), retry_of_item_id=None, root_id=entry['root_id'], source_path=entry['path'], source_identity=identity, position=position, status='skipped' if duplicate or entry.get('format') is None else 'queued', content_status='skipped' if duplicate or entry.get('format') is None else 'pending', metadata_status='unsupported' if duplicate or entry.get('format') is None else 'pending', preview_status='unsupported' if duplicate or entry.get('format') is None else 'pending', error=localized_error(locale, 'DUPLICATE_SOURCE', 'import_duplicate').model_dump() if duplicate else localized_error(locale, 'UNSUPPORTED_FORMAT', 'import_format_unsupported').model_dump() if entry.get('format') is None else entry.get('error'))
        if entry.get('error'):
            item.status = 'failed'
            item.content_status = 'failed'
            item.metadata_status = 'unsupported'
            item.preview_status = 'unsupported'
            item.error = entry['error']
        session.add(item)
        session.flush()
    if not duplicate and entry.get('format') is not None and (not entry.get('error')):
        known.add(identity)

def enumerate_task(database: Database, settings: Settings, task_id: str, sources: list[dict], *, upload_manifest: bool=False) -> None:
    if upload_manifest:
        return
    known = set()
    with database.read_session() as session:
        existing = session.scalars(select(AssetTaskItem).where(AssetTaskItem.task_id == task_id)).all()
        known.update((item.source_identity for item in existing))
        already_registered = set(known)
        position = max((item.position for item in existing), default=-1) + 1
    for source in sources:
        if source.get('enumeration_completed'):
            continue
        stop_state = [False]

        def stopped(stop_state=stop_state) -> bool:
            value = stage_imports_progress.task_cancelled(database, task_id)
            if value:
                stop_state[0] = True
            return value
        try:
            for entry in source['entries'] if 'entries' in source else enumerate_source(settings, source['root_id'], source['path'], stopped, lambda stop_state=stop_state: stop_state.__setitem__(0, True)):
                if stopped():
                    break
                if entry['identity'] in already_registered:
                    continue
                register_source_item(database, task_id, entry, position, known, locale=workspace_locale(settings.workspace))
                position += 1
        except ApiError as exc:
            source['error'] = stage_imports_errors.import_error(settings, exc, code='IMPORT_FAILED', message_key='import_copy_failed')
            source['enumeration_completed'] = True
        else:
            source['enumeration_completed'] = not stop_state[0]
        set_enumeration(database, task_id, sources, all((item.get('enumeration_completed', False) for item in sources)))
        if stop_state[0]:
            break
    sort_task_items(database, task_id, sources)

def sort_task_items(database: Database, task_id: str, sources: list[dict]) -> None:
    with database.write_session() as session:
        items = session.scalars(select(AssetTaskItem).where(AssetTaskItem.task_id == task_id)).all()

        def order(item: AssetTaskItem):
            for index, source in enumerate(sources):
                if source['root_id'] != item.root_id:
                    continue
                source_path = source['path'].rstrip('/')
                if not source_path or item.source_path == source_path or item.source_path.startswith(source_path + (os.sep if not source['root_id'] else '/')):
                    return (index, item.source_path.casefold(), item.source_path)
            return (len(sources), item.source_path.casefold(), item.source_path)
        ordered = sorted(items, key=order)
        count = len(ordered)
        for item in ordered:
            item.position += count
        session.flush()
        for position, item in enumerate(ordered):
            item.position = position
