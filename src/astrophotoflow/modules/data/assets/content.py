from __future__ import annotations

import logging
import os
from copy import deepcopy
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import func, select

from astrophotoflow.contracts.assets import AssetContentAccept, AssetContentObservation
from astrophotoflow.contracts.snapshots import VersionCaptureSnapshot
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.core.localization import exception_error, localized_error, workspace_locale
from astrophotoflow.modules.data.assets.mapping import asset_out
from astrophotoflow.modules.data.assets.metadata import (
    asset_classification,
    asset_parameters,
    capture_role,
    set_asset_classification,
    set_asset_parameters,
)
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion, FitsHduMetadata
from astrophotoflow.modules.data.common import uuid_text
from astrophotoflow.modules.data.files import format_for_path
from astrophotoflow.modules.data.formats.fits import inspect_fits
from astrophotoflow.modules.data.formats.xisf import inspect_xisf
from astrophotoflow.modules.data.science.files import hash_file, read_hash_and_copy, resolve_storage_path

logger = logging.getLogger(__name__)

def observe_asset_content(database: Database, settings: Settings, asset_id: UUID) -> AssetContentObservation:
    with database.read_session() as session:
        asset = session.get(Asset, uuid_text(asset_id))
        if asset is None or asset.current_version_id is None:
            raise not_found()
        version = session.get(AssetVersion, asset.current_version_id)
        if version is None or version.asset_id != asset.id or not version.content_hash:
            raise ApiError(422, "SOURCE_UNAVAILABLE", "素材当前版本尚无已接受的完整内容记录。", message_key='the_current_asset_version_has_no_accepted_complete_content_record')
        result = (asset.id, asset.revision, version.id, version.storage_mode, version.content_hash,
                  version.byte_size, version.storage_location, version.scientific_metadata or {})
    aid, revision, version_id, mode, stored_hash, stored_size, location, metadata = result
    if stored_size is None:
        raise ApiError(422, "SOURCE_UNAVAILABLE", "素材当前版本尚无已接受的文件大小。", message_key='the_current_asset_version_has_no_accepted_file_size')
    try:
        path = resolve_storage_path(settings, mode, location)
        category = (metadata or {}).get("format") or format_for_path(path)
        if category not in {"fits", "xisf", "image", "raw", "video", "numpy"}:
            with database.read_session() as session:
                current = session.get(Asset, aid)
                if current is None or current.current_version_id != version_id or current.revision != revision:
                    raise ApiError(409, "REVISION_CONFLICT", "素材版本已变化，请重新检查。", message_key='the_asset_version_has_changed_check_it_again')
            return AssetContentObservation(
                asset_id=UUID(aid), base_version_id=UUID(version_id), base_revision=revision,
                storage_mode=mode, stored_hash=stored_hash, state="unsupported", observed_hash=None,
                observed_byte_size=None, observed_mtime_ns=None,
                error=localized_error(workspace_locale(settings.workspace), 'UNSUPPORTED_FORMAT', 'content_confirmation_unsupported'),
            )
        observed_hash, byte_size, mtime_ns = hash_file(path)
        state = "unchanged" if observed_hash == stored_hash and byte_size == stored_size else "changed"
        error = None
    except ApiError as exc:
        if exc.code == "SOURCE_UNAVAILABLE":
            state = "missing"
            observed_hash, byte_size, mtime_ns = None, None, None
            error = exception_error(workspace_locale(settings.workspace), exc, code='SOURCE_UNAVAILABLE', message_key='the_asset_source_is_currently_inaccessible')
        else:
            raise
    with database.write_session() as session:
        current = session.get(Asset, aid)
        if current is None or current.current_version_id != version_id or current.revision != revision:
            raise ApiError(409, "REVISION_CONFLICT", "素材版本已变化，请重新检查。", message_key='the_asset_version_has_changed_check_it_again')
        current_version = session.get(AssetVersion, version_id)
        current_version.availability = {"unchanged": "available", "changed": "changed", "missing": "missing"}.get(state, current_version.availability)
    return AssetContentObservation(
        asset_id=UUID(aid), base_version_id=UUID(version_id), base_revision=revision,
        storage_mode=mode, stored_hash=stored_hash, state=state, observed_hash=observed_hash,
        observed_byte_size=byte_size, observed_mtime_ns=str(mtime_ns) if mtime_ns is not None else None, error=error,
    )


def parse_content(path: Path, category: str, cfa_pattern: str | None):
    if category == "fits":
        inspected = inspect_fits(path, cfa_pattern)
        return inspected["parsed_parameters"], inspected["hdus"], None
    if category == "xisf":
        return inspect_xisf(path), [], None
    return {}, [], None


def accept_asset_content(database: Database, settings: Settings, asset_id: UUID, body: AssetContentAccept):
    aid = uuid_text(asset_id)
    base_version_id = uuid_text(body.base_version_id)
    with database.read_session() as session:
        asset = session.get(Asset, aid)
        version = session.get(AssetVersion, base_version_id)
        if asset is None or version is None or version.asset_id != aid:
            raise not_found()
        if asset.revision != body.base_revision or asset.current_version_id != base_version_id:
            raise ApiError(409, "REVISION_CONFLICT", "素材当前版本已变化，请重新读取并检查。", message_key='the_current_asset_version_has_changed_read_and_check_it_again')
        if not version.content_hash:
            raise ApiError(422, "SOURCE_UNAVAILABLE", "素材当前版本尚无已接受的完整内容记录。", message_key='the_current_asset_version_has_no_accepted_complete_content_record')
        if version.availability == "available":
            raise ApiError(422, "VALIDATION_ERROR", "当前素材没有待确认的内容变化。", message_key='there_is_no_pending_content_change_to_confirm_for_this_asset')
        if version.availability != "changed":
            raise ApiError(422, "SOURCE_UNAVAILABLE", "素材当前版本不可用于内容接纳。", message_key='the_current_asset_version_cannot_be_used_to_accept_new_content')
        mode, location = version.storage_mode, version.storage_location
        current_parameters = dict(asset_parameters(asset) or {})
        current_sources = dict(asset.value_sources or {})
        current_classification = dict(asset_classification(asset) or {})
        metadata = dict(version.scientific_metadata or {})
        previous_snapshot = VersionCaptureSnapshot.model_validate(version.capture_snapshot or {})
        accepted_equipment = deepcopy(asset.equipment_snapshot or {})
        equipment_ids = (version.camera_id, version.optical_system_id, version.filter_id)
        max_number = session.scalar(select(func.max(AssetVersion.version_number)).where(AssetVersion.asset_id == aid)) or 0
    source = resolve_storage_path(settings, mode, location)
    category = metadata.get("format") or format_for_path(source)
    if category not in {"fits", "xisf", "image", "raw", "video", "numpy"}:
        raise ApiError(422, "UNSUPPORTED_FORMAT", "当前文件格式不支持内容变化确认。", message_key='content_change_confirmation_is_not_supported_for_this_file_format')
    observed_hash, observed_size, observed_mtime = hash_file(source)
    if observed_hash == version.content_hash:
        raise ApiError(422, "VALIDATION_ERROR", "文件内容与当前素材版本一致，无需接纳新内容。", message_key='the_file_content_matches_the_current_asset_version_no_new_content_needs_to_')
    if observed_hash != body.expected_observed_hash:
        raise ApiError(409, "SOURCE_CHANGED", "文件在确认后再次变化，请重新检查。", message_key='the_file_changed_again_after_confirmation_check_it_again')
    new_version_id = str(uuid4())
    suffix = "".join(source.suffixes[-2:]) if source.name.lower().endswith((".fits.fz", ".fit.fz", '.fts.fz')) else source.suffix
    object_location = (Path("objects") / new_version_id / f"source{suffix.lower()}").as_posix()
    target = settings.data_dir / object_location if mode == "managed" else None
    part = settings.data_dir / "staging" / f"content-{new_version_id}.part" if target is not None else None
    if part is not None:
        part.parent.mkdir(parents=True, exist_ok=True)
        try:
            copied_hash, copied_size = read_hash_and_copy(source, part, lambda: False)
            if copied_hash != body.expected_observed_hash or copied_size != observed_size:
                raise ApiError(409, "SOURCE_CHANGED", "文件在准备新内容记录时再次变化，请重新检查。", message_key='the_file_changed_again_while_preparing_a_content_record_check_it_again')
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(part, target)
        except Exception:
            logger.exception("Accepted content metadata parsing failed")
            part.unlink(missing_ok=True)
            raise
        new_location = object_location
    else:
        new_location = location
    try:
        try:
            parsed, hdu_rows, parse_error = parse_content(target if target is not None else source, category, current_parameters.get("cfa_pattern"))
        except Exception:
            logger.exception("Accepted content metadata parsing failed")
            parsed, hdu_rows = {}, []
            parse_error = f"{category.upper()} 元数据解析失败；新内容已完成登记。"
        parameters = dict(current_parameters)
        value_sources = dict(current_sources)
        from astrophotoflow.modules.data.assets.metadata import PARAMETER_KEYS
        for key, value in parsed.items():
            if key in PARAMETER_KEYS and value_sources.get(key) != "manual":
                parameters[key] = value
                value_sources[key] = "file"
        classification = dict(current_classification)
        for key, value in (parsed.get("classification") or {}).items():
            if value is not None and value_sources.get(f"classification.{key}") != "manual":
                classification[key] = value
                value_sources[f"classification.{key}"] = "file"
        new_role, calibration_level = capture_role(classification)
        with database.write_session() as session:
            current = session.get(Asset, aid)
            previous = session.get(AssetVersion, base_version_id)
            if current is None or previous is None or current.current_version_id != base_version_id or current.revision != body.base_revision:
                raise ApiError(409, "REVISION_CONFLICT", "素材在内容接纳期间已被修改，请重新检查。", message_key='the_asset_was_modified_while_new_content_was_being_accepted_check_it_again')
            if mode == "reference":
                confirmed_hash, confirmed_size, _ = hash_file(source)
                if confirmed_hash != body.expected_observed_hash or confirmed_size != observed_size:
                    raise ApiError(409, "SOURCE_CHANGED", "引用文件在内容接纳期间再次变化，请重新检查。", message_key='the_referenced_file_changed_again_during_content_acceptance_check_it_again')
            version = AssetVersion(
                id=new_version_id, asset_id=aid, version_number=max_number + 1,
                storage_mode=mode, storage_location=new_location, byte_size=observed_size,
                content_hash=body.expected_observed_hash, availability="available",
                camera_id=equipment_ids[0], optical_system_id=equipment_ids[1], filter_id=equipment_ids[2],
                frame_type=classification.get("frame_type"), calibration_level=calibration_level,
                capture_snapshot=VersionCaptureSnapshot.model_validate({
                    "parameters": parameters, "classification": classification,
                    "equipment_snapshot": accepted_equipment,
                    "import_provenance": {
                        "value_sources": value_sources, "observed_parameters": parsed,
                        "defaults_snapshot": previous_snapshot.import_provenance.defaults_snapshot if previous_snapshot.import_provenance else {},
                    },
                }).model_dump(mode="json"),
                scientific_metadata={**metadata, "format": category, "metadata_status": "failed" if parse_error else "available",
                    "parse_error": parse_error, "observed_parameters": parsed,
                    "registration_source_stamp": {"size": observed_size, "mtime_ns": observed_mtime}},
            )
            session.add(version)
            session.flush()
            set_asset_parameters(current, parameters)
            current.value_sources = value_sources
            set_asset_classification(current, classification)
            current.role = new_role
            current.current_version_id = new_version_id
            current.revision += 1
            for hdu in hdu_rows:
                session.add(FitsHduMetadata(id=str(uuid4()), asset_version_id=new_version_id, **hdu))
            session.flush()
            response = asset_out(session, current).model_dump()
        return response
    except Exception:
        if target is not None:
            target.unlink(missing_ok=True)
            try:
                target.parent.rmdir()
            except OSError:
                pass
        raise
