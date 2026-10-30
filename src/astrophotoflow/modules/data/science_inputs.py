from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence
from uuid import UUID, uuid4

import blake3
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from astrophotoflow.contracts.assets import AssetClassification, AssetContentAccept, AssetContentObservation, AssetParameters, OutputRegistration
from astrophotoflow.contracts.common import ErrorDetail
from astrophotoflow.contracts.inputs import CheckedOutput, InputReference, ReferenceObservation, ResolveInputsRequest, ResolvedAssetInput, ResolvedInputs, ScienceFormat, ScienceSelection
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.modules.data.common import _asset_out, _id
from astrophotoflow.modules.data.files import find_root, format_for_path, resolve_relative
from astrophotoflow.modules.data.fits_preview import inspect_fits
from astrophotoflow.modules.data.ingestion import _inspect_xisf, _read_hash_and_copy, _role
from astrophotoflow.modules.data.models import Asset, AssetTask, AssetTaskItem, AssetVersion, Dataset, DatasetMember, DatasetVersion, FitsHduMetadata, Project, ProjectAssetReference, ProjectDatasetReference
from astrophotoflow.modules.data.video_preview import first_video_frame
from astrophotoflow.modules.data.files import SUPPORTED_EXTENSIONS


def _error(code: str, message: str) -> ErrorDetail:
    return ErrorDetail(code=code, message=message, fields=[])


def _raise(code: str, message: str, status_code: int = 422) -> None:
    raise ApiError(status_code, code, message)


def _hash(path: Path) -> tuple[str, int, int]:
    try:
        before = path.stat()
        hasher = blake3.blake3()
        size = 0
        with path.open("rb") as stream:
            while chunk := stream.read(8 * 1024 * 1024):
                hasher.update(chunk)
                size += len(chunk)
        after = path.stat()
    except OSError as exc:
        raise ApiError(422, "SOURCE_UNAVAILABLE", "素材文件当前无法完整读取。") from exc
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or size != after.st_size:
        raise ApiError(409, "SOURCE_CHANGED", "素材文件在读取期间发生变化，请重新检查。")
    return f"blake3:{hasher.hexdigest()}", size, after.st_mtime_ns


def _storage_path(settings: Settings, storage_mode: str, storage_location: str) -> Path:
    if storage_mode == "managed":
        try:
            root = settings.data_dir.resolve()
            candidate = (root / storage_location).resolve(strict=True)
            candidate.relative_to(root)
        except OSError as exc:
            raise ApiError(422, "SOURCE_UNAVAILABLE", "素材文件当前无法读取。") from exc
        except ValueError as exc:
            raise ApiError(422, "SOURCE_UNAVAILABLE", "素材存储位置无效。") from exc
        return candidate
    try:
        _, root_id, relative = storage_location.split("/", 2)
        _, root = find_root(settings, root_id)
        return resolve_relative(root, relative)
    except ApiError as exc:
        raise ApiError(422, "SOURCE_UNAVAILABLE", "素材来源当前不可访问。") from exc
    except (ValueError, OSError) as exc:
        raise ApiError(422, "SOURCE_UNAVAILABLE", "素材来源当前不可访问。") from exc


def _asset_path(settings: Settings, version: AssetVersion) -> Path:
    return _storage_path(settings, version.storage_mode, version.storage_location)


def _project(session: Session, project_id: UUID) -> Project:
    project = session.get(Project, _id(project_id))
    if project is None:
        raise not_found()
    return project


def _asset_reference(session: Session, project_id: UUID, version_id: UUID, *, through_dataset: bool = False):
    version = session.get(AssetVersion, _id(version_id))
    asset = session.get(Asset, version.asset_id) if version else None
    if asset is None or asset.status != "active" or version.availability != "available":
        raise ApiError(404, "INVALID_REFERENCE", "固定素材版本不存在或当前不可用。")
    project_id_text = _id(project_id)
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
        raise ApiError(404, "INVALID_REFERENCE", "项目未固定此素材版本。")
    return asset, version


def _validate_selection(session: Session, version: AssetVersion, selection: ScienceSelection) -> None:
    if selection.kind == "whole_file":
        if selection.hdu_index is not None:
            _raise("UNSUPPORTED_SELECTION", "whole_file 选择不能包含 HDU 索引。")
        return
    if selection.kind != "fits_hdu" or selection.hdu_index is None or selection.hdu_index < 0:
        _raise("UNSUPPORTED_SELECTION", "FITS HDU 选择需要非负索引。")
    row = session.scalar(select(FitsHduMetadata).where(
        FitsHduMetadata.asset_version_id == version.id,
        FitsHduMetadata.hdu_index == selection.hdu_index,
    ))
    if version.scientific_metadata and version.scientific_metadata.get("format") != "fits":
        _raise("UNSUPPORTED_SELECTION", "只有 FITS 文件支持 HDU 选择。")
    if row is None or row.supported_kind is None or row.parse_error:
        _raise("UNSUPPORTED_SELECTION", "所选 HDU 不存在或当前不支持科学读取。")


def _dataset_members(session: Session, project_id: UUID, dataset_version_id: UUID, requested):
    version = session.get(DatasetVersion, _id(dataset_version_id))
    dataset = session.get(Dataset, version.dataset_id) if version else None
    if version is None or dataset is None or dataset.status != "active":
        raise ApiError(404, "INVALID_REFERENCE", "固定素材组版本不存在或当前不可用。")
    project_ref = session.scalar(select(ProjectDatasetReference.id).where(
        ProjectDatasetReference.project_id == _id(project_id),
        ProjectDatasetReference.dataset_id == dataset.id,
        ProjectDatasetReference.dataset_version_id == version.id,
    ))
    if project_ref is None:
        raise ApiError(404, "INVALID_REFERENCE", "项目未固定此素材组版本。")
    members = session.scalars(select(DatasetMember).where(
        DatasetMember.dataset_version_id == version.id,
    ).order_by(DatasetMember.position)).all()
    by_position = {item.position: item for item in members}
    indexes = [item.member_index for item in requested]
    if len(indexes) != len(set(indexes)):
        _raise("INVALID_REFERENCE", "素材组成员不能重复选择。")
    if indexes != sorted(indexes):
        _raise("INVALID_REFERENCE", "素材组成员必须按固定原始顺序选择。")
    result = []
    for item in requested:
        member = by_position.get(item.member_index)
        if member is None or member.asset_version_id != _id(item.asset_version_id):
            _raise("INVALID_REFERENCE", "所选成员与固定素材组版本不匹配。")
        asset, asset_version = _asset_reference(session, project_id, item.asset_version_id, through_dataset=True)
        _validate_selection(session, asset_version, item.selection)
        bindings = dict(version.calibration_defaults or {})
        bindings.update(member.calibration_overrides or {})
        result.append((asset, asset_version, member.position, version.id, bindings, item.selection))
    return result


def _reference_rows(session: Session, request: ResolveInputsRequest):
    _project(session, request.project_id)
    result = []
    for reference_index, reference in enumerate(request.references):
        if reference.kind == "asset_version":
            asset, version = _asset_reference(session, request.project_id, reference.asset_version_id)
            _validate_selection(session, version, reference.selection)
            result.append((reference_index, asset, version, None, None, {"bias": None, "dark": None, "flat": None, "dark_flat": None}, reference.selection))
        else:
            result.extend((reference_index, *row) for row in _dataset_members(
                session, request.project_id, reference.dataset_version_id, reference.members
            ))
    return result


def validate_input_references(database: Database, project_id: UUID, references: Sequence[InputReference]) -> None:
    request = ResolveInputsRequest(project_id=project_id, references=list(references))
    with database.read_session() as session:
        _reference_rows(session, request)


def _resolved_asset(settings: Settings, row, input_mode: str, run_directory: Path, *, colour_layout=None):
    reference_index, asset, version, member_index, dataset_version_id, calibration, selection = row
    if not version.content_hash or version.byte_size is None:
        raise ApiError(422, "SOURCE_UNAVAILABLE", "固定素材版本尚未完成内容登记。")
    path = _asset_path(settings, version)
    content_hash, byte_size, mtime_ns = _hash(path)
    if content_hash != version.content_hash or byte_size != version.byte_size:
        raise ApiError(409, "SOURCE_CHANGED", "固定素材内容与已登记版本不同；请先检查并确认内容变化。")
    preparation = "existing_managed" if version.storage_mode == "managed" else "reference"
    read_path = path
    if input_mode == "reproducible" and version.storage_mode == "reference":
        inputs_dir = run_directory / "inputs"
        inputs_dir.mkdir(parents=True, exist_ok=True)
        read_path = inputs_dir / f"{reference_index:04d}-{version.id}{''.join(path.suffixes)}"
        if read_path.exists():
            copied_hash, copied_size, _ = _hash(read_path)
            if copied_hash != content_hash or copied_size != byte_size:
                raise ApiError(409, "SOURCE_CHANGED", "运行输入固定文件已存在但内容不同。")
        else:
            part = read_path.with_name(read_path.name + ".part")
            part.unlink(missing_ok=True)
            copied_hash, copied_size = _read_hash_and_copy(path, part, lambda: False)
            if copied_hash != content_hash or copied_size != byte_size:
                part.unlink(missing_ok=True)
                raise ApiError(409, "SOURCE_CHANGED", "素材在固定输入期间发生变化。")
            os.replace(part, read_path)
        preparation = "materialized"
        mtime_ns = read_path.stat().st_mtime_ns
    metadata = dict(version.scientific_metadata or {})
    if metadata.get('format') == 'fits':
        if colour_layout is not None and metadata.get('colour_layout') not in (None, colour_layout):
            raise ApiError(422, 'UNSUPPORTED_SELECTION', '固定输入的颜色布局与操作要求不一致。')
        if colour_layout is not None and metadata.get('colour_layout') is None:
            metadata.update(colour_layout=colour_layout, colour_layout_source='operation_input')
        try:
            inspected = inspect_fits(read_path, (asset.parameters or {}).get('cfa_pattern'), colour_layout=metadata.get('colour_layout'))
        except Exception as exc:
            raise ApiError(422, 'UNSUPPORTED_SELECTION', '无法确定固定FITS输入的图像布局；未启动软件处理。') from exc
        metadata.update(selected_hdu=inspected['selected_hdu'], hdu_count=len(inspected['hdus']), frame_count=_fits_frame_count(inspected))
    return ResolvedAssetInput(
        kind="asset_version", reference_index=reference_index, asset_id=UUID(asset.id),
        asset_version_id=UUID(version.id), dataset_version_id=UUID(dataset_version_id) if dataset_version_id else None,
        member_index=member_index, asset_revision=asset.revision,
        parameters=asset.parameters or {},
        classification=AssetClassification.model_validate(asset.classification or {}),
        value_sources=asset.value_sources or {}, capture_snapshot=version.capture_snapshot,
        equipment_snapshot=asset.equipment_snapshot or {}, effective_calibration=calibration,
        read_path=read_path, format=metadata.get("format", "other"), selection=selection,
        byte_size=byte_size, content_hash=content_hash, mtime_ns=mtime_ns,
        scientific_metadata=metadata, preparation=preparation,
    )


def resolve_inputs(database: Database, settings: Settings, request: ResolveInputsRequest, *, run_directory: Path) -> ResolvedInputs:
    with database.read_session() as session:
        rows = _reference_rows(session, request)
        required_copy_bytes = sum(version.byte_size or 0 for _, _, version, _, _, _, _ in rows
                                  if request.input_mode == "reproducible" and version.storage_mode == "reference")
    if required_copy_bytes:
        run_directory.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(run_directory).free < required_copy_bytes:
            raise ApiError(422, "INSUFFICIENT_STORAGE", "可用空间不足，无法固定本次科学输入。")
    items = [_resolved_asset(settings, row, request.input_mode, run_directory) for row in rows]
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
        else:
            fixed = session.get(DatasetVersion, str(reference.dataset_version_id))
            dataset = session.get(Dataset, fixed.dataset_id) if fixed else None
            if dataset is None or dataset.status != "active":
                raise ApiError(404, "INVALID_REFERENCE", "固定图像组不存在或已移除。")
            rows = session.scalars(select(DatasetMember).where(DatasetMember.dataset_version_id == fixed.id)).all()
            for member in rows:
                calibrations[member.position] = dict(fixed.calibration_defaults or {})
                calibrations[member.position].update(member.calibration_overrides or {})
            expected = {row.position: row.asset_version_id for row in rows}
            indexes = [item.member_index for item in reference.members]
            if indexes != sorted(set(indexes)) or any(expected.get(item.member_index) != str(item.asset_version_id) for item in reference.members):
                raise ApiError(422, "INVALID_REFERENCE", "图像组固定成员或顺序不匹配。")
            members = [(item.member_index, str(item.asset_version_id), item.selection) for item in reference.members]
            dataset_version_id = str(fixed.id)
        rows = []
        for position, version_id, selection in members:
            version = session.get(AssetVersion, version_id)
            asset = session.get(Asset, version.asset_id) if version else None
            if asset is None or asset.scope != "shared" or asset.status != "active" or version.availability != "available":
                raise ApiError(404, "INVALID_REFERENCE", "固定素材不存在或原件尚未就绪。")
            _validate_selection(session, version, selection)
            calibration = {"bias": None, "dark": None, "flat": None, "dark_flat": None}
            calibration.update(calibrations.get(position, {}))
            rows.append((0, asset, version, position, dataset_version_id, calibration, selection))
    required = sum(version.byte_size or 0 for _, _, version, _, _, _, _ in rows if version.storage_mode == "reference")
    run_directory.mkdir(parents=True, exist_ok=True)
    if required and shutil.disk_usage(run_directory).free < required:
        raise ApiError(422, "INSUFFICIENT_STORAGE", "空间不足，无法固定本次科学输入。")
    items = [_resolved_asset(settings, row, "reproducible", run_directory, colour_layout=colour_layout) for row in rows]
    return ResolvedInputs(input_mode="reproducible", items=items, required_copy_bytes=required,
                          copied_bytes=sum(item.byte_size for item in items if item.preparation == "materialized"))


def observe_reference_inputs(settings: Settings, inputs: ResolvedInputs) -> list[ReferenceObservation]:
    results = []
    for index, item in enumerate(inputs.items):
        if item.kind != "asset_version" or item.preparation != "reference":
            continue
        try:
            content_hash, size, mtime_ns = _hash(item.read_path)
            unchanged = content_hash == item.content_hash and size == item.byte_size and mtime_ns == item.mtime_ns
            results.append(ReferenceObservation(
                input_index=index, observed_at=datetime.now(timezone.utc),
                state="unchanged" if unchanged else "changed", byte_size=size,
                mtime_ns=mtime_ns, content_hash=content_hash,
            ))
        except ApiError as exc:
            state = "missing" if exc.code == "SOURCE_UNAVAILABLE" else "unverified"
            results.append(ReferenceObservation(input_index=index, observed_at=datetime.now(timezone.utc),
                state=state, error=_error(exc.code, exc.message)))
    return results


def observe_asset_content(database: Database, settings: Settings, asset_id: UUID) -> AssetContentObservation:
    with database.read_session() as session:
        asset = session.get(Asset, _id(asset_id))
        if asset is None or asset.current_version_id is None:
            raise not_found()
        version = session.get(AssetVersion, asset.current_version_id)
        if version is None or version.asset_id != asset.id or not version.content_hash:
            raise ApiError(422, "SOURCE_UNAVAILABLE", "素材当前版本尚无已接受的完整内容记录。")
        result = (asset.id, asset.revision, version.id, version.storage_mode, version.content_hash,
                  version.byte_size, version.storage_location, version.scientific_metadata or {})
    aid, revision, version_id, mode, stored_hash, stored_size, location, metadata = result
    if stored_size is None:
        raise ApiError(422, "SOURCE_UNAVAILABLE", "素材当前版本尚无已接受的文件大小。")
    try:
        path = _storage_path(settings, mode, location)
        category = (metadata or {}).get("format") or format_for_path(path)
        if category not in {"fits", "xisf", "image", "raw", "video", "numpy"}:
            with database.read_session() as session:
                current = session.get(Asset, aid)
                if current is None or current.current_version_id != version_id or current.revision != revision:
                    raise ApiError(409, "REVISION_CONFLICT", "素材版本已变化，请重新检查。")
            return AssetContentObservation(
                asset_id=UUID(aid), base_version_id=UUID(version_id), base_revision=revision,
                storage_mode=mode, stored_hash=stored_hash, state="unsupported", observed_hash=None,
                observed_byte_size=None, observed_mtime_ns=None,
                error=_error("UNSUPPORTED_FORMAT", "当前文件格式不支持内容变化确认。"),
            )
        observed_hash, byte_size, mtime_ns = _hash(path)
        state = "unchanged" if observed_hash == stored_hash and byte_size == stored_size else "changed"
        error = None
    except ApiError as exc:
        if exc.code == "SOURCE_UNAVAILABLE":
            state = "missing"
            observed_hash, byte_size, mtime_ns = None, None, None
            error = _error(exc.code, exc.message)
        else:
            raise
    with database.write_session() as session:
        current = session.get(Asset, aid)
        if current is None or current.current_version_id != version_id or current.revision != revision:
            raise ApiError(409, "REVISION_CONFLICT", "素材版本已变化，请重新检查。")
        current_version = session.get(AssetVersion, version_id)
        current_version.availability = {"unchanged": "available", "changed": "changed", "missing": "missing"}.get(state, current_version.availability)
    return AssetContentObservation(
        asset_id=UUID(aid), base_version_id=UUID(version_id), base_revision=revision,
        storage_mode=mode, stored_hash=stored_hash, state=state, observed_hash=observed_hash,
        observed_byte_size=byte_size, observed_mtime_ns=mtime_ns, error=error,
    )


def _parse_content(path: Path, category: str, cfa_pattern: str | None):
    if category == "fits":
        inspected = inspect_fits(path, cfa_pattern)
        return inspected["parsed_parameters"], inspected["hdus"], None
    if category == "xisf":
        return _inspect_xisf(path), [], None
    return {}, [], None


def accept_asset_content(database: Database, settings: Settings, asset_id: UUID, body: AssetContentAccept):
    aid = _id(asset_id)
    base_version_id = _id(body.base_version_id)
    with database.read_session() as session:
        asset = session.get(Asset, aid)
        version = session.get(AssetVersion, base_version_id)
        if asset is None or version is None or version.asset_id != aid:
            raise not_found()
        if asset.revision != body.base_revision or asset.current_version_id != base_version_id:
            raise ApiError(409, "REVISION_CONFLICT", "素材当前版本已变化，请重新读取并检查。")
        if not version.content_hash:
            raise ApiError(422, "SOURCE_UNAVAILABLE", "素材当前版本尚无已接受的完整内容记录。")
        if version.availability == "available":
            raise ApiError(422, "VALIDATION_ERROR", "当前素材没有待确认的内容变化。")
        if version.availability != "changed":
            raise ApiError(422, "SOURCE_UNAVAILABLE", "素材当前版本不可用于内容接纳。")
        mode, location = version.storage_mode, version.storage_location
        current_parameters = dict(asset.parameters or {})
        current_sources = dict(asset.value_sources or {})
        current_classification = dict(asset.classification or {})
        metadata = dict(version.scientific_metadata or {})
        snapshot = version.capture_snapshot
        equipment_ids = (version.camera_id, version.optical_system_id, version.filter_id)
        max_number = session.scalar(select(func.max(AssetVersion.version_number)).where(AssetVersion.asset_id == aid)) or 0
    source = _storage_path(settings, mode, location)
    category = metadata.get("format") or format_for_path(source)
    if category not in {"fits", "xisf", "image", "raw", "video", "numpy"}:
        raise ApiError(422, "UNSUPPORTED_FORMAT", "当前文件格式不支持内容变化确认。")
    observed_hash, observed_size, observed_mtime = _hash(source)
    if observed_hash == version.content_hash:
        raise ApiError(422, "VALIDATION_ERROR", "文件内容与当前素材版本一致，无需接纳新内容。")
    if observed_hash != body.expected_observed_hash:
        raise ApiError(409, "SOURCE_CHANGED", "文件在确认后再次变化，请重新检查。")
    new_version_id = str(uuid4())
    suffix = "".join(source.suffixes[-2:]) if source.name.lower().endswith((".fits.fz", ".fit.fz", '.fts.fz')) else source.suffix
    object_location = (Path("objects") / new_version_id / f"source{suffix.lower()}").as_posix()
    target = settings.data_dir / object_location if mode == "managed" else None
    part = settings.data_dir / "staging" / f"content-{new_version_id}.part" if target is not None else None
    if part is not None:
        part.parent.mkdir(parents=True, exist_ok=True)
        try:
            copied_hash, copied_size = _read_hash_and_copy(source, part, lambda: False)
            if copied_hash != body.expected_observed_hash or copied_size != observed_size:
                raise ApiError(409, "SOURCE_CHANGED", "文件在准备新内容记录时再次变化，请重新检查。")
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(part, target)
        except Exception:
            part.unlink(missing_ok=True)
            raise
        new_location = object_location
    else:
        new_location = location
    try:
        try:
            parsed, hdu_rows, parse_error = _parse_content(target if target is not None else source, category, current_parameters.get("cfa_pattern"))
        except Exception:
            parsed, hdu_rows = {}, []
            parse_error = f"{category.upper()} 元数据解析失败；新内容已完成登记。"
        parameters = dict(current_parameters)
        value_sources = dict(current_sources)
        from astrophotoflow.modules.data.ingestion import PARAMETER_KEYS
        for key, value in parsed.items():
            if key in PARAMETER_KEYS and value_sources.get(key) != "manual":
                parameters[key] = value
                value_sources[key] = "file"
        classification = dict(current_classification)
        for key, value in (parsed.get("classification") or {}).items():
            if value is not None and value_sources.get(f"classification.{key}") != "manual":
                classification[key] = value
                value_sources[f"classification.{key}"] = "file"
        new_role, calibration_level = _role(classification)
        with database.write_session() as session:
            current = session.get(Asset, aid)
            previous = session.get(AssetVersion, base_version_id)
            if current is None or previous is None or current.current_version_id != base_version_id or current.revision != body.base_revision:
                raise ApiError(409, "REVISION_CONFLICT", "素材在内容接纳期间已被修改，请重新检查。")
            if mode == "reference":
                confirmed_hash, confirmed_size, _ = _hash(source)
                if confirmed_hash != body.expected_observed_hash or confirmed_size != observed_size:
                    raise ApiError(409, "SOURCE_CHANGED", "引用文件在内容接纳期间再次变化，请重新检查。")
            version = AssetVersion(
                id=new_version_id, asset_id=aid, version_number=max_number + 1,
                storage_mode=mode, storage_location=new_location, byte_size=observed_size,
                content_hash=body.expected_observed_hash, availability="available",
                camera_id=equipment_ids[0], optical_system_id=equipment_ids[1], filter_id=equipment_ids[2],
                frame_type=classification.get("frame_type"), calibration_level=calibration_level,
                capture_snapshot=snapshot,
                scientific_metadata={**metadata, "format": category, "metadata_status": "failed" if parse_error else "available",
                    "parse_error": parse_error, "observed_parameters": parsed,
                    "registration_source_stamp": {"size": observed_size, "mtime_ns": observed_mtime}},
            )
            session.add(version)
            session.flush()
            current.parameters, current.value_sources = parameters, value_sources
            current.classification, current.role = classification, new_role
            current.current_version_id = new_version_id
            current.revision += 1
            for hdu in hdu_rows:
                session.add(FitsHduMetadata(id=str(uuid4()), asset_version_id=new_version_id, **hdu))
            session.flush()
            response = _asset_out(session, current)
        return response
    except Exception:
        if target is not None:
            target.unlink(missing_ok=True)
            try:
                target.parent.rmdir()
            except OSError:
                pass
        raise


def _fits_frame_count(inspected):
    images = [row for row in inspected['hdus'] if row['shape'] and row['hdu_type'] in {'PrimaryHDU', 'ImageHDU', 'CompImageHDU'}
              and not ((row.get('name') or '').casefold() == 'iccprofile' and row['bitpix'] == 8 and len(row['shape']) == 1)]
    return len(images) if images and all(row['supported_kind'] is not None for row in images) else None


def check_output(settings: Settings, *, run_directory: Path, path: Path, expected_format: ScienceFormat, allow_empty: bool = False,
                 colour_layout: str | None = None, expected_frames: int | None = None) -> CheckedOutput:
    try:
        root = run_directory.resolve(strict=True)
        resolved = path.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ApiError(422, "OUTPUT_UNAVAILABLE", "输出文件不在本次运行目录内或当前无法读取。") from exc
    if not resolved.is_file():
        raise ApiError(422, "OUTPUT_UNAVAILABLE", "输出位置不是完整文件。")
    actual_format = format_for_path(resolved) or "other"
    if actual_format != expected_format:
        raise ApiError(422, "VALIDATION_ERROR", "输出格式与本次运行记录不一致。")
    content_hash, byte_size, mtime_ns = _hash(resolved)
    if allow_empty and actual_format != 'other':
        raise ApiError(422, 'VALIDATION_ERROR', '科学输出不能声明为空文件。')
    if byte_size == 0 and not allow_empty:
        raise ApiError(422, "OUTPUT_UNAVAILABLE", "输出文件为空。")
    scientific_metadata = {"format": actual_format}
    if colour_layout not in {None, 'planar', 'interleaved'}:
        raise ApiError(422, 'VALIDATION_ERROR', '未知的图像颜色布局。')
    if actual_format == "fits":
        try:
            inspected = inspect_fits(resolved, colour_layout=colour_layout, verify_span=True)
            scientific_metadata.update(selected_hdu=inspected["selected_hdu"], hdu_count=len(inspected["hdus"]))
            scientific_metadata['frame_count'] = _fits_frame_count(inspected)
            selected = next((row for row in inspected['hdus'] if row['is_selected']), None)
            if selected is not None:
                scientific_metadata.update({key: selected[key] for key in ('shape', 'bitpix', 'pixel_type', 'bunit')})
            if colour_layout is not None:
                scientific_metadata['colour_layout'] = colour_layout
        except Exception as exc:
            raise ApiError(422, "OUTPUT_UNAVAILABLE", "FITS 输出无法完整解析。") from exc
    elif actual_format == "xisf":
        try:
            scientific_metadata.update(_inspect_xisf(resolved))
        except Exception as exc:
            raise ApiError(422, "OUTPUT_UNAVAILABLE", "XISF 输出无法完整解析。") from exc
    elif actual_format == 'video' and resolved.suffix.lower() == '.ser':
        from astrophotoflow.modules.data.media_sources import ser_info
        info = ser_info(resolved)
        scientific_metadata.update(frame_count=info['count'], width=info['width'], height=info['height'],
                                   channels=info['channels'], pixel_depth=info['pixel_depth'], pixel_type=str(info['dtype']))
    if expected_frames is not None and scientific_metadata.get('frame_count') != expected_frames:
        raise ApiError(422, 'OUTPUT_UNAVAILABLE', '完整输出的实际帧数与软件结果不一致。')
    checked = CheckedOutput(run_directory=root, path=resolved, format=actual_format, byte_size=byte_size,
                           content_hash=content_hash, checked_at=datetime.now(timezone.utc),
                           scientific_metadata=scientific_metadata, mtime_ns=mtime_ns)
    # Catch a replacement made while any format metadata was being read.
    current_hash, current_size, current_mtime = _hash(resolved)
    if (current_hash, current_size, current_mtime) != (content_hash, byte_size, mtime_ns):
        raise ApiError(409, "SOURCE_CHANGED", "输出文件在检查期间发生变化。")
    return checked


def render_output_preview(checked: CheckedOutput, destination: Path, *, selection: ScienceSelection | None = None,
                          max_edge: int, cfa_pattern: str | None = None, auto_stretch: bool = True) -> None:
    from astrophotoflow.modules.data.fits_preview import create_preview
    from astrophotoflow.modules.data.ingestion import _ordinary_image, _raw_image, _xisf_image

    if max_edge < 1:
        raise ApiError(422, "VALIDATION_ERROR", "预览尺寸必须是正整数。")
    source = checked.path.resolve(strict=True)
    content_hash, byte_size, _ = _hash(source)
    if content_hash != checked.content_hash or byte_size != checked.byte_size:
        raise ApiError(409, "SOURCE_CHANGED", "输出文件在预览生成前发生变化。")
    target = destination.resolve(strict=False)
    if source == target:
        raise ApiError(422, "VALIDATION_ERROR", "预览不能覆盖科学输出文件。")
    try:
        if checked.format == "fits":
            layout = (checked.scientific_metadata or {}).get('colour_layout')
            inspected = inspect_fits(source, cfa_pattern, colour_layout=layout)
            if selection is None or selection.kind == "whole_file":
                hdu_index = inspected["selected_hdu"]
            elif selection.kind == "fits_hdu":
                hdu_index = selection.hdu_index
            else:
                hdu_index = None
            row = next((item for item in inspected["hdus"] if item["hdu_index"] == hdu_index), None)
            if row is None or row["supported_kind"] is None:
                raise ApiError(422, "PREVIEW_UNSUPPORTED", "FITS 输出没有可预览的受支持 HDU。")
            if auto_stretch:
                image, _ = create_preview(source, hdu_index, row["supported_kind"], {"cfa_pattern": cfa_pattern, 'colour_layout': layout}, max_edge)
            else:
                from astrophotoflow.modules.data.siril_preview import direct_fits_image
                image = direct_fits_image(source, hdu_index, max_edge, colour_layout=layout)
        elif checked.format == "image":
            image, _ = _ordinary_image(source, max_edge=max_edge)
        elif checked.format == "raw":
            image = _raw_image(source, max_edge)
        elif checked.format == "xisf":
            image, _ = _xisf_image(source, max_edge=max_edge)
        elif checked.format == "video":
            if source.suffix.lower() != ".ser" and shutil.which("ffmpeg") is None:
                raise ApiError(422, "PREVIEW_DEPENDENCY_UNAVAILABLE", "资产服务未找到 FFmpeg，无法生成视频首帧预览。")
            image, _ = first_video_frame(source, max_edge)
        else:
            raise ApiError(422, "PREVIEW_UNSUPPORTED", f"{checked.format} 输出当前不支持生成预览。")
    except ApiError:
        raise
    except ImportError as exc:
        raise ApiError(422, "PREVIEW_DEPENDENCY_UNAVAILABLE", f"生成 {checked.format} 预览所需的解码依赖不可用。") from exc
    except Exception as exc:
        raise ApiError(422, "PREVIEW_FAILED", f"输出预览生成失败：{exc}") from exc
    image.thumbnail((max_edge, max_edge))
    part = target.with_name(target.name + '.' + str(uuid4()) + '.part')
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(part, format="JPEG")
        after_hash, after_size, _ = _hash(source)
        if (after_hash, after_size) != (checked.content_hash, checked.byte_size):
            raise ApiError(409, "SOURCE_CHANGED", "输出文件在预览生成期间发生变化。")
        os.replace(part, target)
    except ApiError:
        raise
    except Exception as exc:
        raise ApiError(422, "PREVIEW_FAILED", f"输出预览写入失败：{exc}") from exc
    finally:
        part.unlink(missing_ok=True)


def _output_registration(session: Session, task: AssetTask, created: bool) -> OutputRegistration:
    item = session.scalar(select(AssetTaskItem).where(AssetTaskItem.task_id == task.id).order_by(AssetTaskItem.position).limit(1))
    asset_id = UUID(item.asset_id) if item and item.asset_id else None
    version_id = UUID(item.asset_version_id) if item and item.asset_version_id else None
    error = task.error or (item.error if item else None)
    error_detail = ErrorDetail(code=str(error.get("code")), message=str(error.get("message")), fields=[]) if error else None
    return OutputRegistration(
        task_id=UUID(task.id), created=created, task_status=task.status,
        asset_id=asset_id, asset_version_id=version_id,
        content_status=item.content_status if item else "pending",
        metadata_status=item.metadata_status if item else "pending",
        preview_status=item.preview_status if item else "pending",
        error=error_detail,
    )


def register_output(database: Database, settings: Settings, *, task_id: UUID, output: CheckedOutput,
                    name: str | None) -> OutputRegistration:
    try:
        relative = output.path.resolve(strict=False).relative_to(output.run_directory.resolve(strict=False)).as_posix()
    except ValueError as exc:
        raise ApiError(422, "OUTPUT_UNAVAILABLE", "输出文件不在本次运行目录内。") from exc
    effective_name = name if name is not None else output.path.stem or output.path.name
    from astrophotoflow.contracts.common import check_name
    try:
        effective_name = check_name(effective_name)
    except ValueError as exc:
        raise ApiError(422, "VALIDATION_ERROR", str(exc)) from exc
    task_id_text = str(task_id)
    identity = f"run-output:{relative}:{output.content_hash}"
    with database.read_session() as session:
        existing = session.get(AssetTask, task_id_text)
        if existing is not None:
            report = existing.report or {}
            if not report.get("output_registration") or report.get("output_identity") != identity or report.get("output_name") != effective_name:
                raise ApiError(409, "TASK_STATE_CONFLICT", "task_id 已用于不同的素材登记操作。")
            return _output_registration(session, existing, False)
    current = check_output(settings, run_directory=output.run_directory, path=output.path, expected_format=output.format,
                           colour_layout=(output.scientific_metadata or {}).get('colour_layout'))
    if (current.content_hash, current.byte_size) != (output.content_hash, output.byte_size):
        raise ApiError(409, "SOURCE_CHANGED", "所选输出在检查后发生变化。")
    suffix = "".join(current.path.suffixes[-2:]).lower() if current.path.name.lower().endswith((".fits.fz", ".fit.fz", '.fts.fz')) else current.path.suffix.lower()
    stored_name = f"0-{uuid4().hex}{suffix}"
    upload_root = settings.data_dir / "upload-staging" / task_id_text
    source_copy = upload_root / stored_name
    upload_root.mkdir(parents=True, exist_ok=True)
    try:
        copied_hash, copied_size = _read_hash_and_copy(current.path, source_copy, lambda: False)
        if copied_hash != current.content_hash or copied_size != current.byte_size:
            raise ApiError(409, "SOURCE_CHANGED", "输出在复制到素材登记暂存区时发生变化。")
        now = datetime.now(timezone.utc)
        report = {
            "output_registration": True, "output_identity": identity, "output_name": effective_name,
            'output_colour_layout': (current.scientific_metadata or {}).get('colour_layout'),
            "upload_source_task_id": task_id_text,
            "upload_files": [{"name": effective_name, "size": current.byte_size, "received": current.byte_size,
                              "stored_name": stored_name}],
        }
        task = AssetTask(
            id=task_id_text, status="queued", sources=[], storage_mode="managed",
            classification={}, parameters=AssetParameters().model_dump(mode="json"),
            import_defaults_snapshot={"parameters": {}, "classification": {}, "equipment_snapshots": {}},
            notes=None, dataset_name=None, target_dataset_id=None, dataset_base_revision=None,
            dataset_id=None, enumeration_completed=True, retry_of_task_id=None, report=report, error=None,
            created_at=now, updated_at=now,
        )
        item = AssetTaskItem(
            id=str(uuid4()), task_id=task_id_text, root_item_id=str(uuid4()), retry_of_item_id=None,
            root_id="__upload__", source_path=stored_name, source_identity=identity, position=0,
            status="queued", content_status="pending", metadata_status="pending", preview_status="pending",
            asset_id=None, asset_version_id=None, error=None, created_at=now, updated_at=now,
        )
        with database.write_session() as session:
            existing = session.get(AssetTask, task_id_text)
            if existing is not None:
                report = existing.report or {}
                if report.get("output_registration") and report.get("output_identity") == identity and report.get("output_name") == effective_name:
                    source_copy.unlink(missing_ok=True)
                    return _output_registration(session, existing, False)
                raise ApiError(409, "TASK_STATE_CONFLICT", "登记任务已由另一个请求创建，请查询任务状态。")
            session.add(task)
            session.add(item)
            session.flush()
            return _output_registration(session, task, True)
    except Exception:
        if source_copy.exists():
            source_copy.unlink()
        try:
            upload_root.rmdir()
        except OSError:
            pass
        raise


def get_output_registration(database: Database, settings: Settings, task_id: UUID) -> OutputRegistration:
    with database.read_session() as session:
        task = session.get(AssetTask, _id(task_id))
        if task is None or not (task.report or {}).get("output_registration"):
            raise not_found()
        return _output_registration(session, task, False)
