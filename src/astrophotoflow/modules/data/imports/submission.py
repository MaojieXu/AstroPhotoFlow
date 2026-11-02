from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from astrophotoflow.contracts.imports import (
    ImportAccepted,
    ImportCreate,
)
from astrophotoflow.core.config import Settings
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.equipment.references import validate_import_equipment
from astrophotoflow.modules.data.equipment.snapshots import capture_defaults_snapshot
from astrophotoflow.modules.data.files import enumerate_local, enumerate_source, find_root, resolve_relative
from astrophotoflow.modules.data.imports.models import AssetTask


def create_import(session: Session, settings: Settings, body: ImportCreate) -> ImportAccepted:
    validate_import_equipment(session, body.parameters.model_dump(mode='json'))
    sources = []
    is_dataset = len(body.sources) > 1 or body.dataset_name is not None
    for source in body.sources:
        if source.root_id is None:
            selected = Path(source.path)
            entries = enumerate_local(selected)
            if not entries:
                raise ApiError(422, 'NO_SUPPORTED_FILES', '所选路径没有当前支持的素材文件。', message_key='the_selected_path_contains_no_currently_supported_asset_files')
            source_path = str(selected.resolve(strict=True))
        else:
            _, root = find_root(settings, source.root_id)
            selected = resolve_relative(root, source.path, allow_empty=True)
            data_root = settings.data_dir.resolve()
            try:
                data_root.relative_to(root)
            except ValueError:
                pass
            else:
                raise ApiError(422, 'VALIDATION_ERROR', '素材根目录不能包含 AstroPhotoFlow 数据目录。', message_key='an_asset_root_must_not_contain_the_astrophotoflow_data_directory')
            entries = list(enumerate_source(settings, source.root_id, source.path, lambda: False, lambda: None))
            source_path = source.path
        kind = 'directory' if selected.is_dir() else 'file'
        if kind == 'directory':
            is_dataset = True
        sources.append({'root_id': source.root_id or '', 'path': source_path, 'kind': kind, 'enumeration_completed': False, 'error': None, 'entries': entries})
    task_id = str(uuid4())
    target_dataset_id = str(uuid4()) if is_dataset else None
    dataset_name = body.dataset_name
    if is_dataset and (not dataset_name):
        primary = sources[0]
        dataset_name = Path(primary['path'].rstrip('/')).name or next((root.path.name for root in settings.import_roots if root.id == primary['root_id']), '素材集')
    task = AssetTask(id=task_id, status='queued', sources=sources, storage_mode=body.storage_mode, classification=body.classification.model_dump(mode='json', exclude_unset=True), parameters=body.parameters.model_dump(mode='json', exclude_unset=True), notes=body.notes, dataset_name=dataset_name, import_defaults_snapshot=capture_defaults_snapshot(session, body.capture_preset_id, body.parameters).model_dump(mode='json', exclude_unset=True), target_dataset_id=target_dataset_id, dataset_base_revision=None, dataset_id=None, enumeration_completed=False, retry_of_task_id=None, report={}, error=None, created_at=datetime.now(UTC), updated_at=datetime.now(UTC))
    session.add(task)
    session.flush()
    return ImportAccepted.model_validate({'task_id': UUID(task_id), 'status': 'queued'})
