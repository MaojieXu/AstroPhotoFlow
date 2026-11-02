from __future__ import annotations

import logging
import os
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from uuid import uuid4

from sqlalchemy import select

import astrophotoflow.modules.data.imports.errors as stage_imports_errors
import astrophotoflow.modules.data.imports.metadata as stage_imports_metadata
import astrophotoflow.modules.data.imports.progress as stage_imports_progress
import astrophotoflow.modules.data.media.import_previews as stage_media_import_previews
import astrophotoflow.modules.data.science.files as stage_science_files
from astrophotoflow.contracts.snapshots import VersionCaptureSnapshot
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.localization import error_message, localized_error, workspace_locale
from astrophotoflow.modules.data.assets.metadata import (
    PARAMETER_KEYS,
    asset_parameters,
    capture_role,
    classification_columns,
    parameter_columns,
)
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion, FitsHduMetadata
from astrophotoflow.modules.data.equipment.models import Equipment
from astrophotoflow.modules.data.files import SUPPORTED_EXTENSIONS, find_root, format_for_path, resolve_relative
from astrophotoflow.modules.data.formats.fits import PREVIEW_ALGORITHM_VERSION, inspect_fits
from astrophotoflow.modules.data.formats.raster import read_raster_preview
from astrophotoflow.modules.data.formats.raw import read_raw_preview
from astrophotoflow.modules.data.formats.video import first_video_frame
from astrophotoflow.modules.data.formats.xisf import inspect_xisf, read_xisf_preview
from astrophotoflow.modules.data.imports.context import ImportTaskContext
from astrophotoflow.modules.data.imports.errors import IngestionError
from astrophotoflow.modules.data.imports.models import AssetTaskItem
from astrophotoflow.modules.data.media.recipes import describe_recipe, preview_context, save_group_recipe
from astrophotoflow.modules.data.science.files import read_hash_and_copy

logger = logging.getLogger(__name__)

def register_asset(database: Database, settings: Settings, task_data: ImportTaskContext, item_id: str) -> None:
    with database.read_session() as session:
        item = session.get(AssetTaskItem, item_id)
        if item.asset_version_id is not None:
            return
        root_id, source_path = item.root_id, item.source_path
    if root_id == "__upload__":
        upload = next(file for file in task_data.upload_files if file["stored_name"] == source_path)
        asset_name = task_data.output_name if task_data.output_registration else upload["name"]
        original = settings.data_dir / "upload-staging" / task_data.upload_source_task_id / source_path
        location = ""
    elif not root_id:
        original = Path(source_path).resolve(strict=True)
        asset_name = original.name
        location = ""
    else:
        root_spec, root = find_root(settings, root_id)
        original = resolve_relative(root, source_path)
        asset_name = Path(source_path).name
        location = f"roots/{root_spec.id}/{source_path}"
    if not original.is_file():
        raise IngestionError("SOURCE_UNAVAILABLE", "所选来源不是可读文件。", message_key='import_source_unreadable')
    observed_stamp = (task_data.source_stamps.get((root_id, source_path)) or stage_science_files.source_stamp(original)) if root_id != "__upload__" else None
    if observed_stamp is not None and stage_science_files.source_stamp(original) != observed_stamp:
        raise IngestionError("SOURCE_CHANGED", "来源文件在任务受理后发生变化，请确认来源并重新导入。", message_key='import_source_changed')
    category = format_for_path(original)
    if category not in SUPPORTED_EXTENSIONS.values() and task_data.output_registration:
        category = "other"
    if category not in SUPPORTED_EXTENSIONS.values() and category != "other":
        raise IngestionError("UNSUPPORTED_FORMAT", "该文件格式不在本阶段入库清单中。", message_key='import_format_unsupported')
    parsed, hdu_rows, parse_error = {}, [], None
    defaults = task_data.import_defaults_snapshot or {}
    if category in {"fits", "xisf"}:
        try:
            if category == "xisf":
                parsed = inspect_xisf(original)
            else:
                inspected = inspect_fits(original, task_data.parameters.get("cfa_pattern"), colour_layout=task_data.output_colour_layout)
                parsed, hdu_rows = inspected["parsed_parameters"], inspected["hdus"]
        except Exception:
            logger.exception("Import metadata parsing failed")
            parse_error = error_message(workspace_locale(settings.workspace), '', 'import_parse_pending_content', {'format': category.upper()})
    parameters, value_sources = stage_imports_metadata.current_asset_parameters(task_data.parameters, parsed, defaults.get("parameters"))
    if category == "fits" and not parse_error and parameters.get("cfa_pattern") and not parsed.get("cfa_pattern") and not task_data.parameters.get("cfa_pattern"):
        hdu_rows = inspect_fits(original, parameters["cfa_pattern"], colour_layout=task_data.output_colour_layout)["hdus"]
    classification, classification_sources = stage_imports_metadata.current_classification(
        task_data.classification, parsed.get("classification") or {}, defaults.get("classification") or {})
    value_sources.update(classification_sources)
    role, calibration_level = capture_role(classification)
    version_id, asset_id = str(uuid4()), str(uuid4())
    if task_data.storage_mode == "managed":
        suffix = "".join(original.suffixes[-2:]) if original.name.lower().endswith((".fits.fz", ".fit.fz", '.fts.fz')) else original.suffix
        location = (Path("objects") / version_id / f"source{suffix.lower()}").as_posix()
    metadata_status = "failed" if parse_error else "available" if category in {"fits", "xisf"} else "unsupported"
    with database.write_session() as session:
        item = session.get(AssetTaskItem, item_id)
        equipment_snapshot = {
            key: deepcopy(defaults["equipment_snapshots"][str(parameters[key])])
            for key in ("camera_id", "optical_system_id", "filter_id")
            if parameters.get(key) is not None
        }
        for key, frozen in defaults.get("selected_equipment", {}).items():
            if value_sources.get(key) == "preset":
                equipment_snapshot[key] = deepcopy(frozen)
        equipment_links = {
            key: value if value is not None and session.get(Equipment, str(value)) is not None else None
            for key in ("camera_id", "optical_system_id", "filter_id")
            for value in (parameters.get(key),)
        }
        asset = Asset(id=asset_id, name=Path(asset_name).stem or asset_name, scope="shared", owner_project_id=None,
                      role=role, current_version_id=None, **classification_columns(classification), **parameter_columns(parameters),
                      equipment_snapshot=equipment_snapshot, value_sources=value_sources,
                      notes=task_data.notes if task_data.target_dataset_id is None else None,
                      status="active", revision=1)
        session.add(asset)
        session.flush()
        session.add(AssetVersion(
            id=version_id, asset_id=asset_id, version_number=1, storage_mode=task_data.storage_mode,
            storage_location=location, byte_size=None, content_hash=None, availability="unknown",
            camera_id=equipment_links["camera_id"], optical_system_id=equipment_links["optical_system_id"],
            filter_id=equipment_links["filter_id"], frame_type=classification.get("frame_type"),
            calibration_level=calibration_level,
            capture_snapshot=VersionCaptureSnapshot.model_validate({
                "parameters": {key: parameters.get(key) for key in PARAMETER_KEYS},
                "classification": classification, "equipment_snapshot": deepcopy(equipment_snapshot),
                "import_provenance": {"value_sources": deepcopy(value_sources), "observed_parameters": deepcopy(parsed),
                                      "defaults_snapshot": deepcopy(defaults)},
            }).model_dump(mode="json"),
            scientific_metadata={"format": category, "metadata_status": metadata_status,
                                 **({'export_provenance': task_data.output_provenance} if task_data.output_provenance is not None else {}),
                                 **({'colour_layout': task_data.output_colour_layout} if task_data.output_colour_layout is not None else {}),
                                 "parse_error": parse_error, "observed_parameters": parsed,
                                 "registration_source_stamp": observed_stamp},
        ))
        session.flush()
        asset.current_version_id = version_id
        item.asset_id, item.asset_version_id = asset_id, version_id
        item.metadata_status, item.status = metadata_status, "running"
        item.error = {"code": f"{category.upper()}_PARSE_FAILED", "message": parse_error} if parse_error else None
        item.updated_at = datetime.now(UTC)
        for row in hdu_rows:
            session.add(FitsHduMetadata(id=str(uuid4()), asset_version_id=version_id, **row))


def materialize_content(database: Database, settings: Settings, task_data: ImportTaskContext, item_id: str) -> str | None:
    # Retain this entry point for recovery and direct maintenance callers.
    register_asset(database, settings, task_data, item_id)
    with database.read_session() as session:
        item = session.get(AssetTaskItem, item_id)
        if item.content_status == "available":
            refresh = item.metadata_status == "failed"
            asset_id, version_id = item.asset_id, item.asset_version_id
            if not refresh:
                return None
        else:
            refresh = False
        version = session.get(AssetVersion, item.asset_version_id)
        root_id, source_path = item.root_id, item.source_path
        mode, location = version.storage_mode, version.storage_location
        observed_stamp = (version.scientific_metadata or {}).get("registration_source_stamp")
    if refresh:
        return stage_imports_metadata.refresh_fits_metadata(database, settings, item_id, asset_id, version_id)
    if stage_imports_progress.task_cancelled(database, task_data.id):
        return "CANCELLED"
    final = settings.data_dir / location if mode == "managed" else None
    # Only complete files reach the allocated object path. A crash after rename
    # can leave the database pending; resume hashes that object without recopying.
    if final is not None and final.is_file():
        original = final
    elif root_id == "__upload__":
        original = settings.data_dir / "upload-staging" / task_data.upload_source_task_id / source_path
    elif not root_id:
        original = Path(source_path).resolve(strict=True)
    else:
        _, root = find_root(settings, root_id)
        original = resolve_relative(root, source_path)
    stage = None
    if final is not None and original != final and root_id != "__upload__":
        stage = settings.data_dir / "staging" / task_data.id / f"{item_id}.part"
        stage.parent.mkdir(parents=True, exist_ok=True)
        stage.unlink(missing_ok=True)
    try:
        if observed_stamp is not None and original != final and stage_science_files.source_stamp(original) != observed_stamp:
            raise IngestionError("SOURCE_CHANGED", "来源文件在登记后发生变化，请确认来源并重新导入。", message_key='import_source_changed_registered')
        progress = task_data.progress
        last_check, cancelled = 0.0, False
        def should_cancel():
            nonlocal last_check, cancelled
            if monotonic() - last_check >= 0.25:
                cancelled = stage_imports_progress.task_cancelled(database, task_data.id)
                last_check = monotonic()
            return cancelled
        content_hash, byte_size = read_hash_and_copy(original, stage, should_cancel,
            (lambda size: progress.copied(item_id, size)) if progress is not None else None)
        if observed_stamp is not None and original != final and stage_science_files.source_stamp(original) != observed_stamp:
            raise IngestionError("SOURCE_CHANGED", "来源文件在后台读取时发生变化，请确认来源并重新导入。", message_key='import_source_changed_reading')
        if stage_imports_progress.task_cancelled(database, task_data.id):
            return "CANCELLED"
        if final is not None and original != final:
            final.parent.mkdir(parents=True, exist_ok=True)
            os.replace(stage if stage is not None else original, final)
        with database.write_session() as session:
            item = session.get(AssetTaskItem, item_id)
            version = session.get(AssetVersion, item.asset_version_id)
            version.content_hash, version.byte_size, version.availability = content_hash, byte_size, "available"
            item.content_status = "available"
            item.updated_at = datetime.now(UTC)
        return None
    finally:
        if stage is not None:
            stage.unlink(missing_ok=True)


def prepare_preview(database: Database, settings: Settings, task_data: ImportTaskContext, item_id: str) -> None:
    task_id = task_data.id
    if stage_imports_progress.task_cancelled(database, task_id):
        with database.write_session() as session:
            session.get(AssetTaskItem, item_id).status = "cancelled"
        return
    with database.read_session() as session:
        item = session.get(AssetTaskItem, item_id)
        version = session.get(AssetVersion, item.asset_version_id) if item.asset_version_id else None
        item_data = {
            "format": (version.scientific_metadata or {}).get("format") if version else format_for_path(Path(item.source_path)),
            "root_id": item.root_id,
            "asset_id": item.asset_id, "asset_version_id": item.asset_version_id,
            "content_status": item.content_status,
        }
    if item_data["content_status"] != "available":
        return
    context = preview_context(database, task_id, item_data["asset_version_id"])
    if item_data["format"] in {"image", "raw", "xisf", "video"}:
        with database.read_session() as session:
            version = session.get(AssetVersion, item_data["asset_version_id"])
            source_location, source_mode = version.storage_location, version.storage_mode
        try:
            if source_mode == "managed":
                image_path = settings.data_dir / source_location
            else:
                _, root_path = find_root(settings, item_data["root_id"])
                image_path = resolve_relative(root_path, item.source_path)
            if item_data["format"] == "video":
                image, display = first_video_frame(image_path, 100)
            elif item_data["format"] == "raw":
                image, display = read_raw_preview(image_path), {"algorithm": PREVIEW_ALGORITHM_VERSION}
            elif item_data["format"] == "xisf":
                image, display = read_xisf_preview(image_path, auto=context["auto"], auto_stretch=context["auto_stretch"])
            else:
                image, stretch_display = read_raster_preview(image_path, auto=context["auto"], auto_stretch=context["auto_stretch"])
                display = {"algorithm": PREVIEW_ALGORITHM_VERSION, **(stretch_display or {})}
            display = describe_recipe(context, display)
            stage_media_import_previews.save_preview(database, settings, item_data["asset_version_id"], 0, "thumbnail", 100, image, display)
            save_group_recipe(database, context, display)
            with database.write_session() as session:
                item = session.get(AssetTaskItem, item_id)
                item.preview_status = "available"
                item.status = "completed_with_errors" if item.metadata_status == "failed" else "completed"
                if item.metadata_status != "failed":
                    item.error = None
                item.updated_at = datetime.now(UTC)
        except Exception as exc:
            logger.exception("image preview failed task_id=%s item_id=%s", task_id, item_id)
            with database.write_session() as session:
                item = session.get(AssetTaskItem, item_id)
                item.preview_status, item.status = "failed", "completed_with_errors"
                item.error = stage_imports_errors.import_error(settings, exc, code='PREVIEW_FAILED', message_key='import_preview_failed')
                item.updated_at = datetime.now(UTC)
        return
    if item_data["format"] not in {"fits", "video"}:
        with database.write_session() as session:
            item = session.get(AssetTaskItem, item_id)
            item.preview_status, item.status = "unsupported", "completed"
            item.updated_at = datetime.now(UTC)
        return
    if item_data["format"] != "fits":
        with database.write_session() as session:
            item = session.get(AssetTaskItem, item_id)
            item.preview_status, item.status = "unsupported", "completed"
        return
    with database.read_session() as session:
        hdu = session.scalar(select(FitsHduMetadata).where(
            FitsHduMetadata.asset_version_id == item_data["asset_version_id"],
            FitsHduMetadata.is_selected.is_(True),
        ))
        version = session.get(AssetVersion, item_data["asset_version_id"])
        asset = session.get(Asset, item_data["asset_id"])
        hdu_index = hdu.hdu_index if hdu else None
        parameters = dict(asset_parameters(asset) or {})
        source_location = version.storage_location
        source_mode = version.storage_mode
        root_id, source_path = item_data.get("root_id"), item.source_path
    if hdu_index is None:
        with database.write_session() as session:
            item = session.get(AssetTaskItem, item_id)
            version = session.get(AssetVersion, item.asset_version_id)
            parse_error = (version.scientific_metadata or {}).get("parse_error")
            item.metadata_status = "failed" if parse_error else "unsupported"
            item.preview_status = "unsupported"
            item.status = "completed_with_errors" if parse_error else "completed"
            item.error = {"code": "FITS_PARSE_FAILED", "message": parse_error} if parse_error else None
        return
    try:
        if source_mode == "managed":
            image_path = settings.data_dir / source_location
        else:
            _root_obj, root_path = find_root(settings, root_id)
            image_path = resolve_relative(root_path, source_path)
        if stage_imports_progress.task_cancelled(database, task_id):
            raise IngestionError("CANCELLED", "文件处理已取消。", message_key='import_cancelled')
        with database.read_session() as session:
            version_for_parse = session.get(AssetVersion, item_data["asset_version_id"])
            hdu_for_parse = session.scalar(select(FitsHduMetadata).where(
                FitsHduMetadata.asset_version_id == item_data["asset_version_id"],
                FitsHduMetadata.is_selected.is_(True),
            ))
            current_version = version_for_parse
        preview_state, preview_error, display = stage_media_import_previews.fit_preview_rows(
            database, settings, current_version.id,
            [{"hdu_index": hdu_index, "is_selected": True, "supported_kind": hdu_for_parse.supported_kind}],
            parameters, image_path, context=context,
        )
        if display is not None:
            save_group_recipe(database, context, display)
        with database.write_session() as session:
            item = session.get(AssetTaskItem, item_id)
            item.preview_status = preview_state
            item.metadata_status = "available"
            item.status = "completed_with_errors" if preview_error else "completed"
            item.error = {"code": "PREVIEW_FAILED", "message": preview_error} if preview_error else None
            item.updated_at = datetime.now(UTC)
    except IngestionError as exc:
        if exc.code == "CANCELLED":
            with database.write_session() as session:
                item = session.get(AssetTaskItem, item_id)
                item.status = "cancelled"
            return
        with database.write_session() as session:
            item = session.get(AssetTaskItem, item_id)
            item.preview_status = "failed"
            item.status = "completed_with_errors"
            item.error = stage_imports_errors.import_error(settings, exc, code='IMPORT_FAILED', message_key='import_copy_failed')
    except Exception:
        logger.exception("preview failed task_id=%s item_id=%s", task_id, item_id)
        with database.write_session() as session:
            item = session.get(AssetTaskItem, item_id)
            item.preview_status = "failed"
            item.status = "completed_with_errors"
            item.error = localized_error(workspace_locale(settings.workspace), 'PREVIEW_FAILED', 'import_preview_failed').model_dump()


def run_content_item(database: Database, settings: Settings, task_data: ImportTaskContext, item_id: str) -> None:
    try:
        with database.write_session() as session:
            item = session.get(AssetTaskItem, item_id)
            item.status = "running"
            item.updated_at = datetime.now(UTC)
        error = materialize_content(database, settings, task_data, item_id)
        if error == "CANCELLED":
            with database.write_session() as session:
                session.get(AssetTaskItem, item_id).status = "cancelled"
        elif error is None:
            with database.write_session() as session:
                item = session.get(AssetTaskItem, item_id)
                if item.content_status == "available" and item.metadata_status != "failed" and item.preview_status in {"available", "unsupported"}:
                    item.status = "completed"
    except Exception as exc:
        logger.exception("asset content failed task_id=%s item_id=%s", task_data.id, item_id)
        code = exc.code if isinstance(exc, (IngestionError, ApiError)) else "CONTENT_READ_FAILED"
        with database.write_session() as session:
            item = session.get(AssetTaskItem, item_id)
            item.status = "cancelled" if code == "CANCELLED" else "failed"
            item.content_status = "pending" if code == "CANCELLED" else "failed"
            item.error = None if code == 'CANCELLED' else stage_imports_errors.import_error(settings, exc, code=code, message_key='import_copy_failed')
            if code == "SOURCE_CHANGED":
                session.get(AssetVersion, item.asset_version_id).availability = "changed"
            item.updated_at = datetime.now(UTC)
    finally:
        if task_data.progress is not None:
            task_data.progress.flush()
