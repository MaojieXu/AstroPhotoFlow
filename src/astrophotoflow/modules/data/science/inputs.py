from __future__ import annotations

import os
import shutil
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from astrophotoflow.contracts.inputs import (
    InputReference,
    ReferenceObservation,
    ResolvedAssetInput,
    ResolvedInputs,
    ResolveInputsRequest,
    ScienceSelection,
)
from astrophotoflow.contracts.metadata import AssetClassification
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.core.localization import exception_error, workspace_locale
from astrophotoflow.modules.data.assets.metadata import (
    asset_classification,
    asset_parameters,
)
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion, FitsHduMetadata
from astrophotoflow.modules.data.assets.storage import asset_path
from astrophotoflow.modules.data.calibration.service import latest_configuration
from astrophotoflow.modules.data.common import uuid_text
from astrophotoflow.modules.data.datasets.bindings import default_bindings, member_bindings
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember, DatasetVersion
from astrophotoflow.modules.data.formats.fits import inspect_fits
from astrophotoflow.modules.data.projects.models import Project, ProjectAssetReference, ProjectDatasetReference
from astrophotoflow.modules.data.science.files import hash_file, read_hash_and_copy
from astrophotoflow.modules.data.science.outputs import fits_frame_count


def raise_input_error(code: str, message: str, status_code: int = 422, *, message_key: str) -> None:
    raise ApiError(status_code, code, message, message_key=message_key)


def require_project(session: Session, project_id: UUID) -> Project:
    project = session.get(Project, uuid_text(project_id))
    if project is None:
        raise not_found()
    return project


def require_asset_reference(session: Session, project_id: UUID, version_id: UUID, *, through_dataset: bool = False):
    version = session.get(AssetVersion, uuid_text(version_id))
    asset = session.get(Asset, version.asset_id) if version else None
    if asset is None or asset.status != "active" or version.availability != "available":
        raise ApiError(404, "INVALID_REFERENCE", "固定素材版本不存在或当前不可用。", message_key='the_fixed_asset_version_is_missing_or_unavailable')
    project_id_text = uuid_text(project_id)
    if asset.scope == "project":
        allowed = asset.owner_project_id == project_id_text
    elif through_dataset:
        allowed = True
    else:
        allowed = session.scalar(select(ProjectAssetReference.id).where(
            ProjectAssetReference.project_id == project_id_text,
            ProjectAssetReference.asset_version_id == version.id,
        )) is not None
    if not allowed:
        raise ApiError(404, "INVALID_REFERENCE", "项目未固定此素材版本。", message_key='the_project_does_not_reference_this_fixed_asset_version')
    return asset, version


def validate_selection(session: Session, version: AssetVersion, selection: ScienceSelection) -> None:
    if selection.kind == "whole_file":
        if selection.hdu_index is not None:
            raise_input_error("UNSUPPORTED_SELECTION", "whole_file 选择不能包含 HDU 索引。", message_key='whole_file_hdu_forbidden')
        return
    if selection.kind != "fits_hdu" or selection.hdu_index is None or selection.hdu_index < 0:
        raise_input_error("UNSUPPORTED_SELECTION", "FITS HDU 选择需要非负索引。", message_key='fits_hdu_index_required')
    row = session.scalar(select(FitsHduMetadata).where(
        FitsHduMetadata.asset_version_id == version.id,
        FitsHduMetadata.hdu_index == selection.hdu_index,
    ))
    if version.scientific_metadata and version.scientific_metadata.get("format") != "fits":
        raise_input_error("UNSUPPORTED_SELECTION", "只有 FITS 文件支持 HDU 选择。", message_key='fits_selection_only')
    if row is None or row.supported_kind is None or row.parse_error:
        raise_input_error("UNSUPPORTED_SELECTION", "所选 HDU 不存在或当前不支持科学读取。", message_key='fits_hdu_unavailable')


def dataset_members(session: Session, project_id: UUID, dataset_version_id: UUID, requested):
    version = session.get(DatasetVersion, uuid_text(dataset_version_id))
    dataset = session.get(Dataset, version.dataset_id) if version else None
    if version is None or dataset is None or dataset.status != "active":
        raise ApiError(404, "INVALID_REFERENCE", "固定素材组版本不存在或当前不可用。", message_key='the_fixed_asset_group_version_is_missing_or_unavailable')
    project_ref = session.scalar(select(ProjectDatasetReference.id).where(
        ProjectDatasetReference.project_id == uuid_text(project_id),
        ProjectDatasetReference.dataset_id == dataset.id,
        ProjectDatasetReference.dataset_version_id == version.id,
    ))
    if project_ref is None:
        raise ApiError(404, "INVALID_REFERENCE", "项目未固定此素材组版本。", message_key='the_project_does_not_reference_this_fixed_asset_group_version')
    members = session.scalars(select(DatasetMember).where(
        DatasetMember.dataset_version_id == version.id,
    ).order_by(DatasetMember.position)).all()
    by_position = {item.position: item for item in members}
    indexes = [item.member_index for item in requested]
    if len(indexes) != len(set(indexes)):
        raise_input_error("INVALID_REFERENCE", "素材组成员不能重复选择。", message_key='group_members_duplicate')
    if indexes != sorted(indexes):
        raise_input_error("INVALID_REFERENCE", "素材组成员必须按固定原始顺序选择。", message_key='group_member_order')
    result = []
    for item in requested:
        member = by_position.get(item.member_index)
        if member is None or member.asset_version_id != uuid_text(item.asset_version_id):
            raise_input_error("INVALID_REFERENCE", "所选成员与固定素材组版本不匹配。", message_key='group_members_mismatch')
        asset, asset_version = require_asset_reference(session, project_id, item.asset_version_id, through_dataset=True)
        validate_selection(session, asset_version, item.selection)
        bindings = dict(default_bindings(version) or {})
        bindings.update(member_bindings(member) or {})
        result.append((asset, asset_version, member.position, version.id, bindings, item.selection, None))
    return result


def reference_rows(session: Session, request: ResolveInputsRequest):
    require_project(session, request.project_id)
    result = []
    for reference_index, reference in enumerate(request.references):
        if reference.kind == "asset_version":
            asset, version = require_asset_reference(session, request.project_id, reference.asset_version_id)
            validate_selection(session, version, reference.selection)
            configuration = latest_configuration(session, version.id, reference.binding_version_id)
            bindings = {"bias": None, "dark": None, "flat": None, "dark_flat": None}
            if configuration:
                bindings.update(configuration.bindings)
            result.append((reference_index, asset, version, None, None, bindings, reference.selection,
                           configuration.id if configuration else None))
        else:
            result.extend((reference_index, *row) for row in dataset_members(
                session, request.project_id, reference.dataset_version_id, reference.members
            ))
    return result


def validate_input_references(database: Database, project_id: UUID, references: Sequence[InputReference]) -> None:
    request = ResolveInputsRequest(project_id=project_id, references=list(references))
    with database.read_session() as session:
        reference_rows(session, request)


def resolve_asset(settings: Settings, row, input_mode: str, run_directory: Path, *, colour_layout=None):
    reference_index, asset, version, member_index, dataset_version_id, calibration, selection, binding_version_id = row
    if not version.content_hash or version.byte_size is None:
        raise ApiError(422, "SOURCE_UNAVAILABLE", "固定素材版本尚未完成内容登记。", message_key='content_registration_is_incomplete_for_this_fixed_asset_version')
    path = asset_path(settings, version)
    content_hash, byte_size, mtime_ns = hash_file(path)
    if content_hash != version.content_hash or byte_size != version.byte_size:
        raise ApiError(409, "SOURCE_CHANGED", "固定素材内容与已登记版本不同；请先检查并确认内容变化。", message_key='the_fixed_asset_content_differs_from_the_registered_version_check_and_confi')
    preparation = "existing_managed" if version.storage_mode == "managed" else "reference"
    read_path = path
    if input_mode == "reproducible" and version.storage_mode == "reference":
        inputs_dir = run_directory / "inputs"
        inputs_dir.mkdir(parents=True, exist_ok=True)
        read_path = inputs_dir / f"{reference_index:04d}-{version.id}{''.join(path.suffixes)}"
        if read_path.exists():
            copied_hash, copied_size, _ = hash_file(read_path)
            if copied_hash != content_hash or copied_size != byte_size:
                raise ApiError(409, "SOURCE_CHANGED", "运行输入固定文件已存在但内容不同。", message_key='a_fixed_input_file_already_exists_with_different_content')
        else:
            part = read_path.with_name(read_path.name + ".part")
            part.unlink(missing_ok=True)
            copied_hash, copied_size = read_hash_and_copy(path, part, lambda: False)
            if copied_hash != content_hash or copied_size != byte_size:
                part.unlink(missing_ok=True)
                raise ApiError(409, "SOURCE_CHANGED", "素材在固定输入期间发生变化。", message_key='the_asset_changed_while_its_input_was_being_fixed')
            os.replace(part, read_path)
        preparation = "materialized"
        mtime_ns = read_path.stat().st_mtime_ns
    metadata = dict(version.scientific_metadata or {})
    if metadata.get('format') == 'fits':
        if colour_layout is not None and metadata.get('colour_layout') not in (None, colour_layout):
            raise ApiError(422, 'UNSUPPORTED_SELECTION', '固定输入的颜色布局与操作要求不一致。', message_key='the_fixed_input_color_layout_does_not_match_the_operation_requirements')
        if colour_layout is not None and metadata.get('colour_layout') is None:
            metadata.update(colour_layout=colour_layout, colour_layout_source='operation_input')
        try:
            inspected = inspect_fits(read_path, (asset_parameters(asset) or {}).get('cfa_pattern'), colour_layout=metadata.get('colour_layout'))
        except Exception as exc:
            raise ApiError(422, 'UNSUPPORTED_SELECTION', '无法确定固定FITS输入的图像布局；未启动软件处理。', message_key='cannot_determine_the_fixed_fits_input_image_layout_software_processing_was_') from exc
        metadata.update(selected_hdu=inspected['selected_hdu'], hdu_count=len(inspected['hdus']), frame_count=fits_frame_count(inspected))
    return ResolvedAssetInput(
        kind="asset_version", reference_index=reference_index, asset_id=UUID(asset.id),
        asset_version_id=UUID(version.id), dataset_version_id=UUID(dataset_version_id) if dataset_version_id else None,
        member_index=member_index, asset_revision=asset.revision,
        parameters=asset_parameters(asset) or {},
        classification=AssetClassification.model_validate(asset_classification(asset) or {}),
        value_sources=asset.value_sources or {}, capture_snapshot=version.capture_snapshot,
        equipment_snapshot=asset.equipment_snapshot or {}, effective_calibration=calibration,
        binding_version_id=UUID(binding_version_id) if binding_version_id else None,
        read_path=read_path, format=metadata.get("format", "other"), selection=selection,
        byte_size=byte_size, content_hash=content_hash, mtime_ns=mtime_ns,
        scientific_metadata=metadata, preparation=preparation,
    )


def resolve_inputs(database: Database, settings: Settings, request: ResolveInputsRequest, *, run_directory: Path) -> ResolvedInputs:
    with database.read_session() as session:
        rows = reference_rows(session, request)
        required_copy_bytes = sum(version.byte_size or 0 for _, _, version, _, _, _, _, _ in rows
                                  if request.input_mode == "reproducible" and version.storage_mode == "reference")
    if required_copy_bytes:
        run_directory.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(run_directory).free < required_copy_bytes:
            raise ApiError(422, "INSUFFICIENT_STORAGE", "可用空间不足，无法固定本次科学输入。", message_key='insufficient_available_space_to_fix_the_scientific_inputs_for_this_run')
    items = [resolve_asset(settings, row, request.input_mode, run_directory) for row in rows]
    copied_bytes = sum(item.byte_size for item in items if item.preparation == "materialized")
    return ResolvedInputs(input_mode=request.input_mode, items=items,
                          required_copy_bytes=required_copy_bytes, copied_bytes=copied_bytes)


def resolve_canvas_inputs(database: Database, settings: Settings, reference: InputReference,
                          *, run_directory: Path, colour_layout=None) -> ResolvedInputs:
    with database.read_session() as session:
        calibrations = {}
        if reference.kind == "asset_version":
            members = [(None, str(reference.asset_version_id), reference.selection)]
            dataset_version_id = None
            configuration = latest_configuration(session, str(reference.asset_version_id), reference.binding_version_id)
        else:
            fixed = session.get(DatasetVersion, str(reference.dataset_version_id))
            dataset = session.get(Dataset, fixed.dataset_id) if fixed else None
            if dataset is None or dataset.status != "active":
                raise ApiError(404, "INVALID_REFERENCE", "固定图像组不存在或已移除。", message_key='the_fixed_image_group_is_missing_or_has_been_removed')
            rows = session.scalars(select(DatasetMember).where(DatasetMember.dataset_version_id == fixed.id)).all()
            for member in rows:
                calibrations[member.position] = dict(default_bindings(fixed) or {})
                calibrations[member.position].update(member_bindings(member) or {})
            expected = {row.position: row.asset_version_id for row in rows}
            indexes = [item.member_index for item in reference.members]
            if indexes != sorted(set(indexes)) or any(expected.get(item.member_index) != str(item.asset_version_id) for item in reference.members):
                raise ApiError(422, "INVALID_REFERENCE", "图像组固定成员或顺序不匹配。", message_key='fixed_image_group_membership_or_order_does_not_match')
            members = [(item.member_index, str(item.asset_version_id), item.selection) for item in reference.members]
            dataset_version_id = str(fixed.id)
        rows = []
        for position, version_id, selection in members:
            version = session.get(AssetVersion, version_id)
            asset = session.get(Asset, version.asset_id) if version else None
            if asset is None or asset.scope != "shared" or asset.status != "active" or version.availability != "available":
                raise ApiError(404, "INVALID_REFERENCE", "固定素材不存在或原件尚未就绪。", message_key='the_fixed_asset_is_missing_or_its_original_is_not_ready')
            validate_selection(session, version, selection)
            calibration = {"bias": None, "dark": None, "flat": None, "dark_flat": None}
            binding_version_id = None
            if dataset_version_id is None and configuration:
                calibration.update(configuration.bindings)
                binding_version_id = configuration.id
            else:
                calibration.update(calibrations.get(position, {}))
            rows.append((0, asset, version, position, dataset_version_id, calibration, selection, binding_version_id))
    required = sum(version.byte_size or 0 for _, _, version, _, _, _, _, _ in rows if version.storage_mode == "reference")
    run_directory.mkdir(parents=True, exist_ok=True)
    if required and shutil.disk_usage(run_directory).free < required:
        raise ApiError(422, "INSUFFICIENT_STORAGE", "空间不足，无法固定本次科学输入。", message_key='insufficient_space_to_fix_the_scientific_inputs_for_this_run')
    items = [resolve_asset(settings, row, "reproducible", run_directory, colour_layout=colour_layout) for row in rows]
    return ResolvedInputs(input_mode="reproducible", items=items, required_copy_bytes=required,
                          copied_bytes=sum(item.byte_size for item in items if item.preparation == "materialized"))


def observe_reference_inputs(settings: Settings, inputs: ResolvedInputs) -> list[ReferenceObservation]:
    results = []
    for index, item in enumerate(inputs.items):
        if item.kind != "asset_version" or item.preparation != "reference":
            continue
        try:
            content_hash, size, mtime_ns = hash_file(item.read_path)
            unchanged = content_hash == item.content_hash and size == item.byte_size and mtime_ns == item.mtime_ns
            results.append(ReferenceObservation(
                input_index=index, observed_at=datetime.now(UTC),
                state="unchanged" if unchanged else "changed", byte_size=size,
                mtime_ns=mtime_ns, content_hash=content_hash,
            ))
        except ApiError as exc:
            state = "missing" if exc.code == "SOURCE_UNAVAILABLE" else "unverified"
            results.append(ReferenceObservation(input_index=index, observed_at=datetime.now(UTC),
                state=state, error=exception_error(workspace_locale(settings.workspace), exc, code='SOURCE_UNAVAILABLE', message_key='the_asset_source_is_currently_inaccessible')))
    return results
