from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import delete, select

from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.localization import error_message, workspace_locale
from astrophotoflow.modules.data.assets.metadata import (
    PARAMETER_KEYS,
    asset_classification,
    asset_parameters,
    capture_role,
    set_asset_classification,
    set_asset_parameters,
)
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion, FitsHduMetadata
from astrophotoflow.modules.data.files import find_root, resolve_relative
from astrophotoflow.modules.data.formats.fits import inspect_fits
from astrophotoflow.modules.data.formats.xisf import inspect_xisf
from astrophotoflow.modules.data.imports.models import AssetTaskItem
from astrophotoflow.modules.data.media.models import Preview
from astrophotoflow.modules.data.media.thumbnail_batches import THUMBNAIL_STANDALONE

logger = logging.getLogger(__name__)

def current_asset_parameters(request_values: dict, file_values: dict, defaults: dict | None = None) -> tuple[dict, dict]:
    values, sources = {}, {}
    for key in PARAMETER_KEYS:
        if key in request_values:
            values[key], sources[key] = request_values[key], "manual"
        elif file_values.get(key) is not None:
            values[key], sources[key] = file_values[key], "file"
        elif key in (defaults or {}):
            values[key], sources[key] = defaults[key], "manual"
        else:
            values[key] = "standard" if key == "parameter_mode" else None
            sources[key] = "unknown"
    return values, sources


def current_classification(request_values: dict, file_values: dict, defaults: dict) -> tuple[dict, dict]:
    values, sources = {}, {}
    for key in ("frame_class", "frame_type"):
        if key in request_values:
            values[key], sources[f"classification.{key}"] = request_values[key], "manual"
            continue
        observed, supplied = file_values.get(key), defaults.get(key)
        values[key] = observed if observed is not None else supplied
        sources[f"classification.{key}"] = "file" if observed is not None else "manual" if supplied is not None else "unknown"
    if values["frame_class"] == "video":
        values["frame_type"] = None
        sources["classification.frame_type"] = sources["classification.frame_class"]
    return values, sources


def refresh_fits_metadata(database: Database, settings: Settings, item_id: str, asset_id: str, version_id: str) -> str | None:
    with database.read_session() as session:
        item = session.get(AssetTaskItem, item_id)
        version = session.get(AssetVersion, version_id)
        asset = session.get(Asset, asset_id)
        root_id, source_path = item.root_id, item.source_path
        storage_mode, storage_location = version.storage_mode, version.storage_location
        category = (version.scientific_metadata or {}).get("format")
        colour_layout = (version.scientific_metadata or {}).get('colour_layout')
        current_parameters, value_sources = dict(asset_parameters(asset) or {}), dict(asset.value_sources or {})
    if storage_mode == "managed":
        path = settings.data_dir / storage_location
    try:
        if storage_mode != "managed":
            _, root = find_root(settings, root_id)
            path = resolve_relative(root, source_path)
        if category == "xisf":
            hdu_rows, parsed = [], inspect_xisf(path)
        else:
            manual_cfa = current_parameters.get("cfa_pattern") if value_sources.get("cfa_pattern") == "manual" else None
            result = inspect_fits(path, manual_cfa, colour_layout=colour_layout)
            hdu_rows, parsed = result["hdus"], result["parsed_parameters"]
        error = None
    except Exception:
        logger.exception("Import FITS metadata parsing failed")
        hdu_rows, parsed = [], {}
        error = error_message(workspace_locale(settings.workspace), '', 'import_parse_failed', {'format': category.upper()})
    with database.write_session() as session:
        item = session.get(AssetTaskItem, item_id)
        asset = session.get(Asset, asset_id)
        version = session.get(AssetVersion, version_id)
        session.execute(delete(FitsHduMetadata).where(FitsHduMetadata.asset_version_id == version_id))
        for row in hdu_rows:
            session.add(FitsHduMetadata(id=str(uuid4()), asset_version_id=version_id, **row))
        parameters = dict(asset_parameters(asset) or {})
        sources = dict(asset.value_sources or {})
        for key, value in parsed.items():
            if key in PARAMETER_KEYS and sources.get(key) != "manual":
                parameters[key] = value
                sources[key] = "file"
        classification = dict(asset_classification(asset) or {})
        for key, value in (parsed.get("classification") or {}).items():
            if value is not None and sources.get(f"classification.{key}") != "manual":
                classification[key] = value
                sources[f"classification.{key}"] = "file"
        set_asset_classification(asset, classification)
        asset.role = capture_role(classification)[0]
        set_asset_parameters(asset, parameters)
        asset.value_sources = sources
        version.scientific_metadata = {
            **(version.scientific_metadata or {}),
            "metadata_status": "failed" if error else "available",
            "parse_error": error,
            "observed_parameters": parsed,
        }
        item.metadata_status = "failed" if error else "available"
        item.preview_status = "pending"
        for preview in session.scalars(select(Preview).where(
            Preview.asset_version_id == version_id, Preview.size == "thumbnail",
        )).all():
            if preview.algorithm_version == THUMBNAIL_STANDALONE:
                preview.status = "failed" if error else "queued"
                preview.error = str(error) if error else None
            else:
                preview.status = "pending"
        item.error = {"code": f"{category.upper()}_PARSE_FAILED", "message": error} if error else None
        item.updated_at = datetime.now(UTC)
    return error
