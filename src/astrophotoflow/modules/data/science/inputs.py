from __future__ import annotations
import shutil
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from astrophotoflow.contracts.inputs import InputReference, ReferenceObservation, ResolvedAssetInput, ResolvedInputs, ResolveInputsRequest, ScienceSelection
from astrophotoflow.contracts.metadata import AssetClassification
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.core.localization import exception_error, workspace_locale
from astrophotoflow.modules.data.assets.metadata import asset_classification, asset_parameters
from astrophotoflow.modules.data.assets.models import Asset, FitsHduMetadata
from astrophotoflow.modules.data.assets.storage import asset_path
from astrophotoflow.modules.data.common import uuid_text
from astrophotoflow.modules.data.datasets.bindings import dataset_bindings
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember
from astrophotoflow.modules.data.formats.fits import inspect_fits
from astrophotoflow.modules.data.projects.models import Project, ProjectAssetReference, ProjectDatasetReference
from astrophotoflow.modules.data.science.files import hash_file, materialize_input
from astrophotoflow.modules.data.science.outputs import fits_frame_hdus

def raise_input_error(code: str, message: str, status_code: int=422, *, message_key: str) -> None:
    raise ApiError(status_code, code, message, message_key=message_key)

def require_project(session: Session, project_id: UUID) -> Project:
    project = session.get(Project, uuid_text(project_id))
    if project is None:
        raise not_found()
    return project

def require_asset_reference(session: Session, project_id: UUID, asset_id: UUID, *, through_dataset: bool = False) -> Asset:
    from astrophotoflow.modules.data.assets.visibility import not_removed
    asset = session.scalar(select(Asset).where(Asset.id == str(asset_id), Asset.status == 'active', not_removed('asset', Asset.id)))
    if asset is None or asset.availability != 'available':
        raise ApiError(404, 'INVALID_REFERENCE', 'The asset is missing or its original is not ready.', message_key='the_asset_is_missing_or_its_original_is_not_ready')
    if asset.scope == 'project':
        allowed = asset.owner_project_id == str(project_id)
    elif through_dataset:
        allowed = True
    else:
        allowed = session.scalar(select(ProjectAssetReference.id).where(ProjectAssetReference.project_id == str(project_id), ProjectAssetReference.asset_id == asset.id)) is not None
    if not allowed:
        raise not_found()
    return asset

def validate_selection(session: Session, version: Asset, selection: ScienceSelection) -> None:
    if selection.kind == 'whole_file':
        if selection.hdu_index is not None:
            raise_input_error('UNSUPPORTED_SELECTION', 'whole_file 选择不能包含 HDU 索引。', message_key='whole_file_hdu_forbidden')
        return
    if selection.kind != 'fits_hdu' or selection.hdu_index is None or selection.hdu_index < 0:
        raise_input_error('UNSUPPORTED_SELECTION', 'FITS HDU 选择需要非负索引。', message_key='fits_hdu_index_required')
    row = session.scalar(select(FitsHduMetadata).where(FitsHduMetadata.asset_id == version.id, FitsHduMetadata.hdu_index == selection.hdu_index))
    if version.scientific_metadata and version.scientific_metadata.get('format') != 'fits':
        raise_input_error('UNSUPPORTED_SELECTION', '只有 FITS 文件支持 HDU 选择。', message_key='fits_selection_only')
    if row is None or row.supported_kind is None or row.parse_error:
        raise_input_error('UNSUPPORTED_SELECTION', '所选 HDU 不存在或当前不支持科学读取。', message_key='fits_hdu_unavailable')

def current_dataset_members(session, dataset_id, asset_ids=None):
    from astrophotoflow.modules.data.assets.visibility import not_removed
    dataset = session.scalar(select(Dataset).where(Dataset.id == str(dataset_id), Dataset.status == 'active', not_removed('dataset', Dataset.id)))
    if dataset is None:
        raise not_found()
    members = session.scalars(select(DatasetMember).where(DatasetMember.dataset_id == dataset.id).order_by(DatasetMember.position)).all()
    if asset_ids is not None:
        selected = [str(identity) for identity in asset_ids]
        if len(selected) != len(set(selected)) or set(selected) - {member.asset_id for member in members}:
            raise ApiError(422, 'INVALID_REFERENCE', 'Selected assets no longer belong to the dataset.', message_key='selected_assets_no_longer_belong_to_the_dataset')
        members = [member for member in members if member.asset_id in selected]
    if not members:
        raise ApiError(422, 'INVALID_REFERENCE', 'The dataset selection is empty.', message_key='the_dataset_selection_is_empty')
    return dataset, members


def dataset_members(session: Session, project_id: UUID, dataset_id: UUID, requested, selection):
    dataset, members = current_dataset_members(session, dataset_id, requested)
    reference = session.scalar(select(ProjectDatasetReference.id).where(ProjectDatasetReference.project_id == str(project_id), ProjectDatasetReference.dataset_id == dataset.id))
    if reference is None:
        raise not_found()
    result = []
    for member in members:
        asset = require_asset_reference(session, project_id, member.asset_id, through_dataset=True)
        validate_selection(session, asset, selection)
        result.append((asset, member.position, dataset.id, dataset_bindings(dataset), selection))
    return result


def reference_rows(session: Session, request: ResolveInputsRequest):
    require_project(session, request.project_id)
    result = []
    for index, reference in enumerate(request.references):
        if reference.kind == 'asset':
            asset = require_asset_reference(session, request.project_id, reference.asset_id)
            validate_selection(session, asset, reference.selection)
            result.append((index, asset, None, None, dict(asset.calibration or {}), reference.selection))
        else:
            result.extend((index, *row) for row in dataset_members(session, request.project_id, reference.dataset_id, reference.asset_ids, reference.selection))
    return result

def validate_input_references(database: Database, project_id: UUID, references: Sequence[InputReference]) -> None:
    request = ResolveInputsRequest(project_id=project_id, references=list(references))
    with database.read_session() as session:
        reference_rows(session, request)


def referenced_asset_ids(database: Database, references: Sequence[InputReference]) -> set[str]:
    """Inspect current IDs for active-call protection without preparing bytes."""
    identities = set()
    with database.read_session() as session:
        for reference in references:
            if reference.kind == 'asset':
                identities.add(str(reference.asset_id))
                asset = session.get(Asset, str(reference.asset_id))
                bindings = asset.calibration or {} if asset else {}
            else:
                dataset = session.get(Dataset, str(reference.dataset_id))
                if dataset is None:
                    continue
                members = session.scalars(select(DatasetMember).where(DatasetMember.dataset_id == dataset.id)).all()
                identities.update(member.asset_id for member in members if reference.asset_ids is None or member.asset_id in {str(value) for value in reference.asset_ids})
                bindings = dataset_bindings(dataset)
            identities.update(str(target['id']) for target in bindings.values() if target and target.get('kind') == 'asset')
    return identities

def resolve_asset(settings: Settings, row, input_mode: str, run_directory: Path, *, colour_layout=None):
    reference_index, asset, member_index, dataset_id, calibration, selection = row
    if not asset.content_hash or asset.byte_size is None:
        raise ApiError(422, 'SOURCE_UNAVAILABLE', '固定素材版本尚未完成内容登记。', message_key='content_registration_is_incomplete_for_this_fixed_asset')
    path = asset_path(settings, asset)
    content_hash, byte_size, mtime_ns = hash_file(path)
    if content_hash != asset.content_hash or byte_size != asset.byte_size:
        raise ApiError(409, 'SOURCE_CHANGED', '文件内容与登记原件不同。请恢复原件，或将修改后的文件作为新素材导入。', message_key='asset_original_changed_reimport')
    preparation = 'existing_managed' if asset.storage_mode == 'managed' else 'reference'
    read_path = path
    if input_mode == 'reproducible' and asset.storage_mode == 'reference':
        inputs_dir = run_directory / 'inputs'
        inputs_dir.mkdir(parents=True, exist_ok=True)
        read_path = inputs_dir / f"{reference_index:04d}-{asset.id}{''.join(path.suffixes)}"
        materialize_input(path, read_path, content_hash, byte_size)
        preparation = 'materialized'
        mtime_ns = read_path.stat().st_mtime_ns
    metadata = dict(asset.scientific_metadata or {})
    if metadata.get('format') == 'fits':
        if colour_layout is not None and metadata.get('colour_layout') not in (None, colour_layout):
            raise ApiError(422, 'UNSUPPORTED_SELECTION', '固定输入的颜色布局与操作要求不一致。', message_key='the_fixed_input_color_layout_does_not_match_the_operation_requirements')
        if colour_layout is not None and metadata.get('colour_layout') is None:
            metadata.update(colour_layout=colour_layout, colour_layout_source='operation_input')
        try:
            inspected = inspect_fits(read_path, (asset_parameters(asset) or {}).get('cfa_pattern'), colour_layout=metadata.get('colour_layout'))
        except Exception as exc:
            raise ApiError(422, 'UNSUPPORTED_SELECTION', '无法确定固定FITS输入的图像布局；未启动软件处理。', message_key='cannot_determine_the_fixed_fits_input_image_layout_software_processing_was_') from exc
        frames = fits_frame_hdus(inspected)
        metadata.update(selected_hdu=inspected['selected_hdu'], hdu_count=len(inspected['hdus']), frame_count=len(frames) or None)
        if len(frames) > 1:
            metadata['frame_hdus'] = frames
    return ResolvedAssetInput(calibration_status=asset.calibration_status, calibration_evidence=asset.calibration_evidence or {}, kind='asset', reference_index=reference_index, asset_id=UUID(asset.id), dataset_id=UUID(dataset_id) if dataset_id else None, member_index=member_index, asset_revision=asset.revision, parameters=asset_parameters(asset) or {}, classification=AssetClassification.model_validate(asset_classification(asset) or {}), value_sources=asset.value_sources or {}, capture_snapshot=asset.capture_snapshot, equipment_snapshot=asset.equipment_snapshot or {}, effective_calibration=calibration, read_path=read_path, format=metadata.get('format', 'other'), selection=selection, byte_size=byte_size, content_hash=content_hash, mtime_ns=mtime_ns, scientific_metadata=metadata, preparation=preparation)

def resolve_inputs(database: Database, settings: Settings, request: ResolveInputsRequest, *, run_directory: Path) -> ResolvedInputs:
    with database.read_session() as session:
        rows = reference_rows(session, request)
        required_copy_bytes = sum((version.byte_size or 0 for _, version, _, _, _, _ in rows if request.input_mode == 'reproducible' and version.storage_mode == 'reference'))
    if required_copy_bytes:
        run_directory.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(run_directory).free < required_copy_bytes:
            raise ApiError(422, 'INSUFFICIENT_STORAGE', '可用空间不足，无法固定本次科学输入。', message_key='insufficient_available_space_to_fix_the_scientific_inputs_for_this_run')
    items = [resolve_asset(settings, row, request.input_mode, run_directory) for row in rows]
    copied_bytes = sum((item.byte_size for item in items if item.preparation == 'materialized'))
    return ResolvedInputs(input_mode=request.input_mode, items=items, required_copy_bytes=required_copy_bytes, copied_bytes=copied_bytes)

def _canvas_input_rows(session: Session, reference: InputReference):
    from astrophotoflow.modules.data.assets.visibility import not_removed
    if reference.kind == 'asset':
        selected = [(None, str(reference.asset_id), reference.selection)]
        dataset_id, bindings = None, None
    else:
        dataset, members = current_dataset_members(session, reference.dataset_id, reference.asset_ids)
        selected = [(member.position, member.asset_id, reference.selection) for member in members]
        dataset_id, bindings = dataset.id, dataset_bindings(dataset)
    rows = []
    for position, asset_id, selection in selected:
        asset = session.scalar(select(Asset).where(Asset.id == asset_id, Asset.scope == 'shared', Asset.status == 'active', not_removed('asset', Asset.id)))
        if asset is None or asset.availability != 'available':
            raise ApiError(404, 'INVALID_REFERENCE', 'The asset is missing or its original is not ready.', message_key='the_asset_is_missing_or_its_original_is_not_ready')
        validate_selection(session, asset, selection)
        rows.append((0, asset, position, dataset_id, dict(asset.calibration or {}) if bindings is None else dict(bindings), selection))
    return rows


def resolve_canvas_input_groups(database: Database, settings: Settings, references: dict[str, tuple[InputReference, str | None]], *, run_directory: Path) -> dict[str, ResolvedInputs]:
    with database.read_session() as session:
        snapshots = {key: _canvas_input_rows(session, reference) for key, (reference, _) in references.items()}
    required = {key: sum(asset.byte_size or 0 for _, asset, _, _, _, _ in rows if asset.storage_mode == 'reference') for key, rows in snapshots.items()}
    run_directory.mkdir(parents=True, exist_ok=True)
    if sum(required.values()) and shutil.disk_usage(run_directory).free < sum(required.values()):
        raise ApiError(422, 'INSUFFICIENT_STORAGE', 'Insufficient space to fix scientific inputs.', message_key='insufficient_space_to_fix_scientific_inputs')
    results = {}
    for key, rows in snapshots.items():
        directory = (run_directory / key).resolve()
        if not directory.is_relative_to(run_directory.resolve()):
            raise ApiError(422, 'INVALID_REFERENCE', 'Files and scientific images require their respective input ports.', message_key='files_and_scientific_images_require_their_respective_input_ports')
        items = [resolve_asset(settings, row, 'reproducible', directory, colour_layout=references[key][1]) for row in rows]
        results[key] = ResolvedInputs(input_mode='reproducible', items=items, required_copy_bytes=required[key],
                                     copied_bytes=sum(item.byte_size for item in items if item.preparation == 'materialized'))
    return results


def resolve_canvas_inputs(database: Database, settings: Settings, reference: InputReference, *, run_directory: Path, colour_layout=None) -> ResolvedInputs:
    return resolve_canvas_input_groups(database, settings, {'.': (reference, colour_layout)}, run_directory=run_directory)['.']


def observe_reference_inputs(settings: Settings, inputs: ResolvedInputs) -> list[ReferenceObservation]:
    results = []
    for index, item in enumerate(inputs.items):
        if item.kind != 'asset' or item.preparation != 'reference':
            continue
        try:
            content_hash, size, mtime_ns = hash_file(item.read_path)
            unchanged = content_hash == item.content_hash and size == item.byte_size and (mtime_ns == item.mtime_ns)
            results.append(ReferenceObservation(input_index=index, observed_at=datetime.now(UTC), state='unchanged' if unchanged else 'changed', byte_size=size, mtime_ns=mtime_ns, content_hash=content_hash))
        except ApiError as exc:
            state = 'missing' if exc.code == 'SOURCE_UNAVAILABLE' else 'unverified'
            results.append(ReferenceObservation(input_index=index, observed_at=datetime.now(UTC), state=state, error=exception_error(workspace_locale(settings.workspace), exc, code='SOURCE_UNAVAILABLE', message_key='the_asset_source_is_currently_inaccessible')))
    return results
