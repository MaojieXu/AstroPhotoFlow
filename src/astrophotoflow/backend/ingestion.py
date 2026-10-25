from __future__ import annotations
import json
import logging
import os
import tempfile
import time
from io import BytesIO
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import numpy as np
from PIL import Image, ImageOps
from sqlalchemy import delete, func, select

from .db import Database
from .errors import ApiError, invalid_reference, not_found
from .files import SUPPORTED_EXTENSIONS, enumerate_source, find_root, format_for_path, resolve_relative
from .fits_preview import PARSER_VERSION, PREVIEW_ALGORITHM_VERSION, _display, create_preview, inspect_fits, stretch_bounds
from .models import (
    Asset, AssetTask, AssetTaskItem, AssetVersion, Dataset, DatasetMember,
    DatasetVersion, Equipment, FitsHduMetadata, Preview,
)
from ..config import Settings
from .video_preview import first_video_frame
from pillow_heif import register_heif_opener


register_heif_opener(thumbnails=False)


logger = logging.getLogger("astrophotoflow.service.ingestion")
PARAMETER_KEYS = (
    "camera_id", "optical_system_id", "filter_id", "parameter_mode", "iso", "gain", "offset",
    "exposure_seconds", "integration_seconds", "sensor_temperature_c", "binning_x", "binning_y", "cfa_pattern",
)
CALIBRATION_TYPES = {"bias", "dark", "flat", "dark_flat"}


class IngestionError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _check_equipment(session, value: Any, expected: str) -> None:
    if value is None:
        return
    row = session.get(Equipment, str(value))
    if row is None or row.kind != expected:
        raise invalid_reference(f"参数中的设备必须是现存的 {expected} 设备。")


def validate_import_equipment(session, parameters: dict) -> None:
    for key, kind in (
        ("camera_id", "camera"), ("optical_system_id", "optical_system"), ("filter_id", "filter")
    ):
        _check_equipment(session, parameters.get(key), kind)


def _role(classification: dict) -> tuple[str, str | None]:
    frame_type = classification.get("frame_type")
    if frame_type in CALIBRATION_TYPES:
        level = "master" if classification.get("frame_class") == "masterframe" else "individual"
        return "calibration", level
    return "raw", None


def _item_error(session, item: AssetTaskItem, code: str, message: str) -> None:
    item.status = "failed"
    item.error = {"code": code, "message": message}
    item.updated_at = datetime.now(timezone.utc)
    session.flush()


def _cancelled(database: Database, task_id: str) -> bool:
    with database.read_session() as session:
        status = session.scalar(select(AssetTask.status).where(AssetTask.id == task_id))
    return status in {"cancelling", "cancelled", "interrupted"}


def _set_enumeration(database: Database, task_id: str, sources: list[dict], complete: bool) -> None:
    with database.write_session() as session:
        task = session.get(AssetTask, task_id)
        task.sources = sources
        task.enumeration_completed = complete
        task.updated_at = datetime.now(timezone.utc)


def _source_item(
    database: Database, task_id: str, entry: dict, position: int, known: set[str]
) -> None:
    identity = entry["identity"]
    with database.write_session() as session:
        duplicate = identity in known
        item = AssetTaskItem(
            id=str(uuid4()), task_id=task_id, root_item_id=str(uuid4()), retry_of_item_id=None,
            root_id=entry["root_id"], source_path=entry["path"], source_identity=identity,
            position=position, status="skipped" if duplicate or entry.get("format") is None else "queued",
            content_status="skipped" if duplicate or entry.get("format") is None else "pending",
            metadata_status="unsupported" if duplicate or entry.get("format") is None else "pending",
            preview_status="unsupported" if duplicate or entry.get("format") is None else "pending",
            error=(
                {"code": "DUPLICATE_SOURCE", "message": "同一批次的重复来源只处理一次。"}
                if duplicate else
                {"code": "UNSUPPORTED_FORMAT", "message": "该文件格式不在本阶段入库清单中。"}
                if entry.get("format") is None else
                entry.get("error")
            ),
        )
        if entry.get("error"):
            item.status = "failed"
            item.content_status = "failed"
            item.metadata_status = "unsupported"
            item.preview_status = "unsupported"
            item.error = entry["error"]
        session.add(item)
        session.flush()
    if not duplicate and entry.get("format") is not None and not entry.get("error"):
        known.add(identity)



def _enumerate_task(database: Database, settings: Settings, task_id: str, task_data: dict) -> None:
    sources = task_data["sources"]
    if task_data.get("upload_manifest"):
        return
    known = set()
    with database.read_session() as session:
        existing = session.scalars(select(AssetTaskItem).where(AssetTaskItem.task_id == task_id)).all()
        known.update(item.source_identity for item in existing)
        already_registered = set(known)
        position = max((item.position for item in existing), default=-1) + 1

    for source in sources:
        if source.get("enumeration_completed"):
            continue
        stop_state = [False]
        def stopped() -> bool:
            value = _cancelled(database, task_id)
            if value:
                stop_state[0] = True
            return value
        try:
            for entry in enumerate_source(settings, source["root_id"], source["path"], stopped, lambda: stop_state.__setitem__(0, True)):
                if entry["identity"] in already_registered:
                    continue
                _source_item(database, task_id, entry, position, known)
                position += 1
        except ApiError as exc:
            source["error"] = {"code": exc.code, "message": exc.message}
            source["enumeration_completed"] = True
        else:
            source["enumeration_completed"] = not stop_state[0]
        _set_enumeration(
            database, task_id, sources,
            all(item.get("enumeration_completed", False) for item in sources),
        )
        if stop_state[0]:
            break
    _sort_task_items(database, task_id, sources)


def _sort_task_items(database: Database, task_id: str, sources: list[dict]) -> None:
    with database.write_session() as session:
        items = session.scalars(
            select(AssetTaskItem).where(AssetTaskItem.task_id == task_id)
        ).all()

        def order(item: AssetTaskItem):
            for index, source in enumerate(sources):
                if source["root_id"] != item.root_id:
                    continue
                source_path = source["path"].rstrip("/")
                if not source_path or item.source_path == source_path or item.source_path.startswith(source_path + "/"):
                    return index, item.source_path.casefold(), item.source_path
            return len(sources), item.source_path.casefold(), item.source_path

        ordered = sorted(items, key=order)
        count = len(ordered)
        for item in ordered:
            item.position += count
        session.flush()
        for position, item in enumerate(ordered):
            item.position = position


def _read_hash_and_copy(path: Path, stage_path: Path | None, cancelled) -> tuple[str, int]:
    try:
        import blake3
    except ImportError as exc:
        raise IngestionError("SERVICE_NOT_CONFIGURED", "资产服务缺少 BLAKE3 依赖。") from exc
    hasher = blake3.blake3()
    total = 0
    destination = stage_path.open("xb") if stage_path is not None else None
    try:
        with path.open("rb") as source:
            while chunk := source.read(8 * 1024 * 1024):
                if cancelled():
                    raise IngestionError("CANCELLED", "文件处理已取消。")
                hasher.update(chunk)
                total += len(chunk)
                if destination is not None:
                    destination.write(chunk)
            if destination is not None:
                destination.flush()
                os.fsync(destination.fileno())
    finally:
        if destination is not None:
            destination.close()
    return f"blake3:{hasher.hexdigest()}", total


def _current_asset_parameters(request_values: dict, file_values: dict) -> tuple[dict, dict]:
    values, sources = {}, {}
    for key in PARAMETER_KEYS:
        requested = request_values.get(key)
        parsed = file_values.get(key)
        if requested is not None:
            values[key] = requested
            sources[key] = "manual"
        elif parsed is not None:
            values[key] = parsed
            sources[key] = "file"
        else:
            values[key] = None if key != "parameter_mode" else request_values.get(key, "standard")
            sources[key] = "unknown" if key != "parameter_mode" else "manual"
    return values, sources


def _fit_preview_rows(database: Database, settings: Settings, version_id: str, hdu_rows: list[dict], parameters: dict, path: Path, missing_only: bool = False, stretch: tuple[float, float] | None = None, group_key: str | None = None, reference_version_id: str | None = None) -> tuple[str, str | None, dict | None]:
    selected = next((row for row in hdu_rows if row["is_selected"]), None)
    if selected is None:
        return "unsupported", None, None
    if selected["supported_kind"] in {"xtrans", "quad_bayer"}:
        return "unsupported", f"{selected['supported_kind']} CFA 已登记；当前暂不支持其马赛克彩色预览。", None
    failed = None
    display = None
    for size, edge in (("thumbnail", 100),):
        try:
            if missing_only:
                with database.read_session() as session:
                    existing = session.scalar(select(Preview.id).where(
                        Preview.asset_version_id == version_id, Preview.hdu_index == selected["hdu_index"],
                        Preview.size == size, Preview.algorithm_version == PREVIEW_ALGORITHM_VERSION,
                        Preview.status == "available",
                    ))
                if existing:
                    continue
            image, display = create_preview(path, selected["hdu_index"], selected["supported_kind"], parameters, edge, stretch)
            if group_key is not None:
                display.update(stretch_group=group_key, stretch_reference_version_id=reference_version_id or version_id)
            preview_id = str(uuid4())
            relative = Path("previews") / version_id / f"{PREVIEW_ALGORITHM_VERSION}-{selected['hdu_index']}-thumbnail.jpg"
            final = settings.data_dir / relative
            final.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix=preview_id, suffix=".tmp", dir=final.parent)
            os.close(fd)
            try:
                image.save(temporary, format="JPEG", quality=80, optimize=False)
                os.replace(temporary, final)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            with database.write_session() as session:
                preview = session.scalar(select(Preview).where(
                    Preview.asset_version_id == version_id, Preview.hdu_index == selected["hdu_index"],
                    Preview.size == size, Preview.algorithm_version == PREVIEW_ALGORITHM_VERSION,
                ))
                if preview is None:
                    preview = Preview(
                        id=preview_id, asset_version_id=version_id, hdu_index=selected["hdu_index"],
                        size=size, width=image.width, height=image.height, storage_path=relative.as_posix(),
                        mime_type="image/jpeg", display_parameters=display,
                        algorithm_version=PREVIEW_ALGORITHM_VERSION, status="available", error=None,
                    )
                    session.add(preview)
                else:
                    preview.width, preview.height = image.width, image.height
                    preview.storage_path, preview.mime_type = relative.as_posix(), "image/jpeg"
                    preview.display_parameters, preview.status, preview.error = display, "available", None
        except Exception:
            logger.exception("preview failed version_id=%s size=%s", version_id, size)
            failed = "所选图像 HDU 的预览生成失败。"
            with database.write_session() as session:
                preview = session.scalar(select(Preview).where(
                    Preview.asset_version_id == version_id, Preview.hdu_index == selected["hdu_index"],
                    Preview.size == size, Preview.algorithm_version == PREVIEW_ALGORITHM_VERSION,
                ))
                if preview is None:
                    preview = Preview(
                        id=str(uuid4()), asset_version_id=version_id, hdu_index=selected["hdu_index"],
                        size=size, width=0, height=0, storage_path="", mime_type="image/jpeg",
                        display_parameters={"algorithm": PREVIEW_ALGORITHM_VERSION},
                        algorithm_version=PREVIEW_ALGORITHM_VERSION, status="failed", error=failed,
                    )
                    session.add(preview)
                else:
                    preview.width, preview.height = 0, 0
                    preview.storage_path, preview.status, preview.error = "", "failed", failed
                    preview.display_parameters = {"algorithm": PREVIEW_ALGORITHM_VERSION}
    return ("failed" if failed else "available"), failed, display if not failed else None


def _save_preview(database: Database, settings: Settings, version_id: str, hdu_index: int, size: str, edge: int, image: Image.Image, display_parameters: dict | None = None) -> None:
    image.thumbnail((edge, edge), Image.Resampling.LANCZOS)
    preview_id = str(uuid4())
    relative = Path("previews") / version_id / f"{PREVIEW_ALGORITHM_VERSION}-{hdu_index}-thumbnail.jpg"
    final = settings.data_dir / relative
    final.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=preview_id, suffix=".tmp", dir=final.parent)
    os.close(fd)
    try:
        image.convert("RGB").save(temporary, format="JPEG", quality=80, optimize=False)
        os.replace(temporary, final)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    with database.write_session() as session:
        preview = session.scalar(select(Preview).where(
            Preview.asset_version_id == version_id, Preview.hdu_index == hdu_index,
            Preview.size == size, Preview.algorithm_version == PREVIEW_ALGORITHM_VERSION,
        ))
        if preview is None:
            preview = Preview(
                id=preview_id, asset_version_id=version_id, hdu_index=hdu_index, size=size,
                width=image.width, height=image.height, storage_path=relative.as_posix(),
                mime_type="image/jpeg", display_parameters=display_parameters or {"algorithm": PREVIEW_ALGORITHM_VERSION},
                algorithm_version=PREVIEW_ALGORITHM_VERSION, status="available", error=None,
            )
            session.add(preview)
        else:
            preview.width, preview.height = image.width, image.height
            preview.storage_path, preview.mime_type = relative.as_posix(), "image/jpeg"
            preview.display_parameters = display_parameters or {"algorithm": PREVIEW_ALGORITHM_VERSION}
            preview.status, preview.error = "available", None


def _ordinary_image(path: Path, stretch: tuple[float, float] | None = None) -> tuple[Image.Image, dict | None]:
    with Image.open(path) as source:
        source.seek(0)
        image = ImageOps.exif_transpose(source)
        if image.mode in {"I;16", "I;16B", "I;16L", "I", "F"}:
            values = np.asarray(image, dtype=np.float32)
            low, high = stretch if stretch is not None else stretch_bounds(values)
            return _display(values, (low, high)), {"stretch_low": low, "stretch_high": high}
        return image.convert("RGB").copy(), None


def _xisf_image(path: Path, stretch: tuple[float, float] | None = None) -> tuple[Image.Image, dict]:
    from xisf import XISF

    reader = XISF(str(path))
    metadata = reader.get_images_metadata()[0]
    color_space = str(metadata.get("colorSpace", "")).casefold()
    channels = metadata["geometry"][2]
    array = reader.read_image(0, data_format="channels_last")
    if color_space == "gray" and channels == 1:
        if array.ndim == 3 and array.shape[-1] == 1:
            array = array[..., 0]
        if array.ndim != 2:
            raise ValueError("XISF 灰度图像数据形状无效。")
    elif color_space == "rgb" and channels == 3:
        if array.ndim != 3 or array.shape[-1] != 3:
            raise ValueError("XISF RGB 图像必须包含三个通道。")
    else:
        raise ValueError(f"不支持 XISF 色彩布局：{metadata.get('colorSpace', 'unknown')}")
    low, high = stretch if stretch is not None else stretch_bounds(array)
    return _display(array, (low, high)), {"stretch_low": low, "stretch_high": high}


def _xisf_layout(path: Path) -> str:
    from xisf import XISF

    metadata = XISF(str(path)).get_images_metadata()[0]
    return f"{metadata.get('colorSpace')}:{metadata.get('sampleFormat')}"


def _preview_group_key(version: AssetVersion, asset: Asset, layout: str) -> str:
    parameters = asset.parameters or {}
    observed = (version.scientific_metadata or {}).get("observed_parameters") or {}
    return json.dumps([
        (version.scientific_metadata or {}).get("format"), layout,
        (asset.classification or {}).get("frame_class"), version.frame_type,
        parameters.get("camera_id"), parameters.get("filter_id") or observed.get("filter_name"),
        parameters.get("exposure_seconds"), parameters.get("gain"), parameters.get("offset"),
        parameters.get("binning_x"), parameters.get("binning_y"),
    ], ensure_ascii=False, separators=(",", ":"))


def _task_stretch(database: Database, task_id: str, group_key: str) -> tuple[tuple[float, float] | None, str | None]:
    with database.read_session() as session:
        profile = ((session.get(AssetTask, task_id).report or {}).get("preview_stretch_groups") or {}).get(group_key)
    if profile is None:
        return None, None
    return (profile["low"], profile["high"]), profile["reference_version_id"]


def _save_task_stretch(database: Database, task_id: str, group_key: str, display: dict, version_id: str) -> None:
    with database.write_session() as session:
        task = session.get(AssetTask, task_id)
        report = dict(task.report or {})
        groups = dict(report.get("preview_stretch_groups") or {})
        if group_key not in groups:
            groups[group_key] = {
                "low": display["stretch_low"], "high": display["stretch_high"],
                "reference_version_id": version_id,
            }
            task.report = {**report, "preview_stretch_groups": groups}


def _backfill_stretch(database: Database, version_id: str, layout: str) -> tuple[str | None, str | None, tuple[float, float] | None, str | None]:
    with database.read_session() as session:
        version = session.get(AssetVersion, version_id)
        asset = session.get(Asset, version.asset_id)
        task_id = session.scalar(select(AssetTaskItem.task_id).where(AssetTaskItem.asset_version_id == version_id).limit(1))
        group_key = _preview_group_key(version, asset, layout)
    stretch, reference_id = _task_stretch(database, task_id, group_key) if task_id else (None, None)
    return task_id, group_key, stretch, reference_id


def _raw_image(path: Path) -> Image.Image:
    import rawpy

    with rawpy.imread(str(path)) as raw:
        try:
            thumbnail = raw.extract_thumb()
            if thumbnail.format == rawpy.ThumbFormat.JPEG:
                with Image.open(BytesIO(thumbnail.data)) as image:
                    if max(image.size) >= 100:
                        return ImageOps.exif_transpose(image).convert("RGB").copy()
            elif thumbnail.format == rawpy.ThumbFormat.BITMAP:
                image = Image.fromarray(thumbnail.data)
                if max(image.size) >= 100:
                    return image.convert("RGB").copy()
        except (rawpy.LibRawError, OSError, ValueError):
            pass
        return Image.fromarray(raw.postprocess(half_size=True, output_bps=8, output_color=rawpy.ColorSpace.sRGB)).convert("RGB")


def backfill_missing_previews(database: Database, settings: Settings) -> dict[str, int]:
    with database.read_session() as session:
        versions = session.scalars(select(AssetVersion).join(Asset, Asset.id == AssetVersion.asset_id)
            .where(Asset.scope == "shared")).all()
        rows = [(row.id, row.storage_mode, row.storage_location, row.scientific_metadata or {}) for row in versions]
    generated = failed = 0
    for version_id, mode, location, metadata in rows:
        if metadata.get("format") not in {"image", "raw", "xisf", "fits", "video"}:
            continue
        with database.read_session() as session:
            selected = session.scalar(select(FitsHduMetadata).where(
                FitsHduMetadata.asset_version_id == version_id, FitsHduMetadata.is_selected.is_(True)
            ))
            available = set(session.scalars(select(Preview.size).where(
                Preview.asset_version_id == version_id, Preview.hdu_index == (selected.hdu_index if selected else 0),
                Preview.algorithm_version == PREVIEW_ALGORITHM_VERSION, Preview.status == "available",
            )).all())
        if "thumbnail" in available:
            continue
        try:
            if mode == "managed":
                path = settings.data_dir / location
            else:
                _, root_id, relative = location.split("/", 2)
                _, root = find_root(settings, root_id)
                path = resolve_relative(root, relative)
            if metadata.get("format") in {"raw", "xisf"}:
                if metadata["format"] == "raw":
                    image, display = _raw_image(path), {"algorithm": PREVIEW_ALGORITHM_VERSION}
                else:
                    task_id, group_key, stretch, reference_id = _backfill_stretch(database, version_id, _xisf_layout(path))
                    image, display = _xisf_image(path, stretch)
                    display.update(stretch_group=group_key, stretch_reference_version_id=reference_id or version_id)
                _save_preview(database, settings, version_id, 0, "thumbnail", 100, image, display)
                if metadata["format"] == "xisf" and task_id and reference_id is None:
                    _save_task_stretch(database, task_id, group_key, display, version_id)
            elif metadata.get("format") == "fits":
                if selected is None:
                    raise ValueError("FITS 没有已选中的图像 HDU。")
                if selected.supported_kind in {"xtrans", "quad_bayer"}:
                    continue
                with database.read_session() as session:
                    version = session.get(AssetVersion, version_id)
                    asset = session.get(Asset, version.asset_id)
                    hdu_rows = [{"hdu_index": selected.hdu_index, "is_selected": True, "supported_kind": selected.supported_kind}]
                    parameters = dict(asset.parameters or {})
                task_id, group_key, stretch, reference_id = _backfill_stretch(database, version_id, f"{selected.supported_kind}:{selected.bitpix}")
                _, error, display = _fit_preview_rows(database, settings, version_id, hdu_rows, parameters, path, missing_only=True, stretch=stretch, group_key=group_key, reference_version_id=reference_id)
                if error:
                    raise ValueError(error)
                if display is not None and task_id and reference_id is None:
                    _save_task_stretch(database, task_id, group_key, display, version_id)
            elif metadata.get("format") == "video":
                image, display = first_video_frame(path, 100)
                _save_preview(database, settings, version_id, 0, "thumbnail", 100, image, display)
            else:
                with Image.open(path) as source:
                    layout = source.mode
                if layout in {"I;16", "I;16B", "I;16L", "I", "F"}:
                    task_id, group_key, stretch, reference_id = _backfill_stretch(database, version_id, layout)
                else:
                    task_id, group_key, stretch, reference_id = None, None, None, None
                image, stretch_display = _ordinary_image(path, stretch)
                if stretch_display is not None:
                    stretch_display.update(stretch_group=group_key, stretch_reference_version_id=reference_id or version_id)
                _save_preview(database, settings, version_id, 0, "thumbnail", 100, image, stretch_display)
                if stretch_display is not None and task_id and reference_id is None:
                    _save_task_stretch(database, task_id, group_key, stretch_display, version_id)
            generated += 1
        except Exception:
            logger.exception("preview backfill failed version_id=%s", version_id)
            failed += 1
    return {"generated": generated, "failed": failed}


def _refresh_fits_metadata(database: Database, settings: Settings, item_id: str, asset_id: str, version_id: str) -> str | None:
    with database.read_session() as session:
        item = session.get(AssetTaskItem, item_id)
        version = session.get(AssetVersion, version_id)
        asset = session.get(Asset, asset_id)
        root_id, source_path = item.root_id, item.source_path
        storage_mode, storage_location = version.storage_mode, version.storage_location
        current_parameters, value_sources = dict(asset.parameters or {}), dict(asset.value_sources or {})
    if storage_mode == "managed":
        path = settings.data_dir / storage_location
    try:
        if storage_mode != "managed":
            _, root = find_root(settings, root_id)
            path = resolve_relative(root, source_path)
        result = inspect_fits(path, current_parameters.get("cfa_pattern"))
        hdu_rows = result["hdus"]
        parsed = result["parsed_parameters"]
        error = None
    except Exception:
        hdu_rows, parsed = [], {}
        error = "FITS 元数据解析失败；原始文件已完成内容入库。"
    with database.write_session() as session:
        item = session.get(AssetTaskItem, item_id)
        asset = session.get(Asset, asset_id)
        version = session.get(AssetVersion, version_id)
        session.execute(delete(FitsHduMetadata).where(FitsHduMetadata.asset_version_id == version_id))
        for row in hdu_rows:
            session.add(FitsHduMetadata(id=str(uuid4()), asset_version_id=version_id, **row))
        parameters = dict(asset.parameters or {})
        sources = dict(asset.value_sources or {})
        for key, value in parsed.items():
            if key in PARAMETER_KEYS and sources.get(key) != "manual":
                parameters[key] = value
                sources[key] = "file"
        asset.parameters, asset.value_sources = parameters, sources
        version.scientific_metadata = {
            **(version.scientific_metadata or {}),
            "metadata_status": "failed" if error else "available",
            "parse_error": error,
            "observed_parameters": parsed,
        }
        item.metadata_status = "failed" if error else "available"
        item.error = {"code": "FITS_PARSE_FAILED", "message": error} if error else None
        item.updated_at = datetime.now(timezone.utc)
    return error


def _create_asset_content(
    database: Database, settings: Settings, task_data: dict, item_id: str
) -> str | None:
    with database.read_session() as session:
        item = session.get(AssetTaskItem, item_id)
        if item.content_status == "available" and item.asset_id and item.asset_version_id:
            asset_id, version_id = item.asset_id, item.asset_version_id
            refresh_metadata = item.metadata_status == "failed"
            if not refresh_metadata:
                return None
        else:
            asset_id, version_id, refresh_metadata = None, None, False
        item_snapshot = {
            "root_id": item.root_id, "source_path": item.source_path, "source_identity": item.source_identity,
            "position": item.position,
        }
        task_snapshot = dict(task_data)

    if refresh_metadata:
        return _refresh_fits_metadata(database, settings, item_id, asset_id, version_id)

    asset_name = Path(item_snapshot["source_path"]).stem or Path(item_snapshot["source_path"]).name
    if item_snapshot["root_id"] == "__upload__":
        upload_file = next(file for file in task_snapshot["upload_files"] if file["stored_name"] == item_snapshot["source_path"])
        asset_name = upload_file["name"]
        original = settings.data_dir / "upload-staging" / task_snapshot["upload_source_task_id"] / item_snapshot["source_path"]
        root_spec = None
    else:
        root_spec, root = find_root(settings, item_snapshot["root_id"])
        original = resolve_relative(root, item_snapshot["source_path"])
    if not original.is_file():
        raise IngestionError("SOURCE_UNAVAILABLE", "所选来源不是可读文件。")
    category = format_for_path(original)
    if category not in SUPPORTED_EXTENSIONS.values():
        raise IngestionError("UNSUPPORTED_FORMAT", "该文件格式不在本阶段入库清单中。")

    version_id = str(uuid4())
    asset_id = str(uuid4())
    stage_path = None
    final_path = None
    relative_location = f"roots/{root_spec.id}/{item_snapshot['source_path']}" if root_spec else ""
    if task_snapshot["storage_mode"] == "managed":
        suffix = "".join(original.suffixes[-2:]) if original.name.lower().endswith((".fits.fz", ".fit.fz")) else original.suffix
        relative_location = (Path("objects") / version_id / f"source{suffix.lower()}").as_posix()
        stage_path = settings.data_dir / "staging" / task_snapshot["id"] / f"{item_id}.part"
        final_path = settings.data_dir / relative_location
        stage_path.parent.mkdir(parents=True, exist_ok=True)
        stage_path.unlink(missing_ok=True)
    try:
        content_hash, byte_size = _read_hash_and_copy(original, stage_path, lambda: _cancelled(database, task_snapshot["id"]))
        processing_path = stage_path if stage_path is not None else original
        is_fits = category == "fits"
        request_parameters = task_snapshot["parameters"]
        parsed, hdu_rows, parse_error = {}, [], None
        if is_fits:
            try:
                result = inspect_fits(processing_path, request_parameters.get("cfa_pattern"))
                hdu_rows = result["hdus"]
                parsed = result["parsed_parameters"]
            except Exception:
                parse_error = "FITS 元数据解析失败；原始文件已完成内容入库。"
        if _cancelled(database, task_snapshot["id"]):
            return "CANCELLED"
        if final_path is not None:
            final_path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(stage_path, final_path)
        classification = task_snapshot["classification"]
        role, calibration_level = _role(classification)
        current_parameters, value_sources = _current_asset_parameters(request_parameters, parsed)
        value_sources["classification.frame_class"] = "manual"
        value_sources["classification.frame_type"] = "manual"
        version_snapshot = {key: current_parameters.get(key) for key in PARAMETER_KEYS}
        version_science = {
            "format": category,
            "metadata_status": "failed" if parse_error else "unsupported" if not is_fits else "available",
            "parse_error": parse_error,
            "observed_parameters": parsed,
        }
        with database.write_session() as session:
            item = session.get(AssetTaskItem, item_id)
            asset = Asset(
                id=asset_id, name=Path(asset_name).stem or asset_name,
                scope="shared", owner_project_id=None, role=role, current_version_id=None,
                classification=classification, parameters=current_parameters, value_sources=value_sources,
                notes=task_snapshot["notes"] if task_snapshot["target_dataset_id"] is None else None,
                status="active", revision=1,
            )
            version = AssetVersion(
                id=version_id, asset_id=asset_id, version_number=1, storage_mode=task_snapshot["storage_mode"],
                storage_location=relative_location, byte_size=byte_size, content_hash=content_hash,
                availability="available", camera_id=current_parameters.get("camera_id"),
                optical_system_id=current_parameters.get("optical_system_id"),
                filter_id=current_parameters.get("filter_id"), capture_profile_id=None,
                frame_type=classification.get("frame_type"), calibration_level=calibration_level,
                capture_snapshot=version_snapshot, scientific_metadata=version_science,
            )
            session.add(asset)
            session.flush()
            session.add(version)
            session.flush()
            asset.current_version_id = version_id
            item.asset_id = asset_id
            item.asset_version_id = version_id
            item.content_status = "available"
            item.metadata_status = "failed" if parse_error else "unsupported" if not is_fits else "available"
            item.status = "completed_with_errors" if parse_error else "running"
            item.error = {"code": "FITS_PARSE_FAILED", "message": parse_error} if parse_error else None
            item.updated_at = datetime.now(timezone.utc)
            for row in hdu_rows:
                row_id = str(uuid4())
                session.add(FitsHduMetadata(id=row_id, asset_version_id=version_id, **row))
        return parse_error
    except Exception:
        if final_path is not None and final_path.exists():
            final_path.unlink()
        raise
    finally:
        if stage_path is not None and stage_path.exists():
            stage_path.unlink()
        if item_snapshot["root_id"] == "__upload__" and final_path is not None and final_path.exists():
            original.unlink(missing_ok=True)


def _publish_dataset(database: Database, task_data: dict, task_id: str) -> dict | None:
    target_id = task_data.get("target_dataset_id")
    if not target_id:
        return None
    try:
        with database.write_session() as session:
            task = session.get(AssetTask, task_id)
            successes = session.scalars(
                select(AssetTaskItem).where(
                    AssetTaskItem.task_id == task_id,
                    AssetTaskItem.content_status == "available",
                    AssetTaskItem.asset_version_id.is_not(None),
                ).order_by(AssetTaskItem.position)
            ).all()
            if not successes:
                return None
            dataset = session.get(Dataset, target_id)
            if dataset is None:
                source_notes = task.notes
                dataset = Dataset(
                    id=target_id, name=task.dataset_name or "素材集", notes=source_notes,
                    status="active", revision=1, current_version_id=None,
                )
                session.add(dataset)
                session.flush()
                base_members = []
                version_number = 1
            else:
                version_number = (session.scalar(
                    select(func.max(DatasetVersion.version_number)).where(DatasetVersion.dataset_id == target_id)
                ) or 0) + 1
                base_members = session.scalars(
                    select(DatasetMember).where(DatasetMember.dataset_version_id == dataset.current_version_id)
                    .order_by(DatasetMember.position)
                ).all()
                expected = task.dataset_base_revision
                if expected is None or dataset.revision != expected:
                    raise RuntimeError(f"DATASET_REVISION_CONFLICT:{expected}:{dataset.revision}")
            existing_versions = {member.asset_version_id for member in base_members}
            additions = []
            for item in successes:
                if item.asset_version_id not in existing_versions:
                    additions.append((item.asset_version_id, item.source_path))
                    existing_versions.add(item.asset_version_id)
            if not additions and dataset.current_version_id is not None:
                return None
            version_id = str(uuid4())
            version = DatasetVersion(id=version_id, dataset_id=target_id, version_number=version_number)
            session.add(version)
            session.flush()
            for index, member in enumerate(base_members):
                session.add(DatasetMember(
                    id=str(uuid4()), dataset_version_id=version_id, asset_version_id=member.asset_version_id,
                    position=index, relative_path=member.relative_path,
                ))
            for position, (asset_version_id, relative_path) in enumerate(additions, start=len(base_members)):
                session.add(DatasetMember(
                    id=str(uuid4()), dataset_version_id=version_id, asset_version_id=asset_version_id,
                    position=position, relative_path=relative_path,
                ))
            dataset.current_version_id = version_id
            dataset.revision += 1 if dataset.revision > 0 and version_number > 1 else 0
            dataset.updated_at = datetime.now(timezone.utc)
            task.dataset_id = target_id
            task.report = {**(task.report or {}), "dataset_id": target_id, "dataset_version_id": version_id}
            session.flush()
            return {"dataset_id": target_id, "dataset_version_id": version_id}
    except RuntimeError as exc:
        text = str(exc)
        if not text.startswith("DATASET_REVISION_CONFLICT:"):
            raise
        _, expected, observed = text.split(":")
        with database.write_session() as session:
            task = session.get(AssetTask, task_id)
            successful = session.scalars(
                select(AssetTaskItem.asset_version_id).where(
                    AssetTaskItem.task_id == task_id,
                    AssetTaskItem.content_status == "available",
                    AssetTaskItem.asset_version_id.is_not(None),
                ).order_by(AssetTaskItem.position)
            ).all()
            dataset = session.get(Dataset, target_id)
            current_members = set()
            if dataset is not None and dataset.current_version_id is not None:
                current_members = set(session.scalars(
                    select(DatasetMember.asset_version_id).where(
                        DatasetMember.dataset_version_id == dataset.current_version_id
                    )
                ).all())
            pending = [version_id for version_id in successful if version_id not in current_members]
            conflict = {
                "code": "REVISION_CONFLICT", "dataset_id": target_id,
                "expected_revision": int(expected) if expected != "None" else None,
                "observed_revision": int(observed),
                "pending_asset_version_ids": pending,
            }
            task.report = {**(task.report or {}), "dataset_publish_error": conflict}
        return None


def _finish_task(database: Database, task_id: str, was_cancelled: bool) -> None:
    with database.write_session() as session:
        task = session.get(AssetTask, task_id)
        items = session.scalars(select(AssetTaskItem).where(AssetTaskItem.task_id == task_id)).all()
        successes = sum(item.content_status == "available" for item in items)
        errors = any(item.status in {"failed", "completed_with_errors"} or item.metadata_status == "failed" or item.preview_status == "failed" for item in items)
        skipped = sum(item.status == "skipped" for item in items)
        if was_cancelled:
            status = "cancelled"
        elif not successes:
            status = "failed"
        elif errors or (task.report or {}).get("dataset_publish_error"):
            status = "completed_with_errors"
        else:
            status = "completed"
        task.status = status
        task.report = {
            **(task.report or {}),
            "counts": {
                "enumerated": len(items),
                "content_succeeded": successes,
                "failed": sum(item.status == "failed" for item in items),
                "skipped": skipped,
                "processing_issues": sum(
                    item.status == "completed_with_errors" or item.metadata_status == "failed" or item.preview_status == "failed" for item in items
                ),
                "cancelled": sum(item.status == "cancelled" for item in items),
            },
        }
        task.updated_at = datetime.now(timezone.utc)


def process_task(database: Database, settings: Settings, task_id: str) -> None:
    try:
        with database.write_session() as session:
            task = session.get(AssetTask, task_id)
            if task is None or task.status not in {"queued", "running"}:
                return
            task.status = "running"
            task.updated_at = datetime.now(timezone.utc)
            task_data = {
                "id": task.id, "sources": list(task.sources), "storage_mode": task.storage_mode,
                "classification": dict(task.classification), "parameters": dict(task.parameters),
                "notes": task.notes, "dataset_name": task.dataset_name,
                "target_dataset_id": task.target_dataset_id, "dataset_base_revision": task.dataset_base_revision,
                "retry_of_task_id": task.retry_of_task_id,
                "upload_manifest": bool((task.report or {}).get("upload_manifest")),
                "upload_files": (task.report or {}).get("upload_files", []),
                "upload_source_task_id": (task.report or {}).get("upload_source_task_id", task.id),
            }
        last_poll = [0.0]
        cancelled_cache = [False]

        def stopped() -> bool:
            now = time.monotonic()
            if now - last_poll[0] >= 0.15:
                cancelled_cache[0] = _cancelled(database, task_id)
                last_poll[0] = now
            return cancelled_cache[0]

        if not task_data["retry_of_task_id"]:
            _enumerate_task(database, settings, task_id, task_data)
        with database.read_session() as session:
            items = session.scalars(
                select(AssetTaskItem).where(AssetTaskItem.task_id == task_id)
                .order_by(AssetTaskItem.position)
            ).all()
            item_ids = [item.id for item in items if item.status in {"queued", "interrupted", "running"}]
        for item_id in item_ids:
            if stopped():
                with database.write_session() as session:
                    item = session.get(AssetTaskItem, item_id)
                    if item.status != "skipped":
                        item.status = "cancelled"
                        item.updated_at = datetime.now(timezone.utc)
                continue
            with database.write_session() as session:
                item = session.get(AssetTaskItem, item_id)
                if item.status not in {"queued", "interrupted", "running"}:
                    continue
                item.status = "running"
                item.updated_at = datetime.now(timezone.utc)
            try:
                error = _create_asset_content(database, settings, task_data, item_id)
            except IngestionError as exc:
                with database.write_session() as session:
                    item = session.get(AssetTaskItem, item_id)
                    item.status = "cancelled" if exc.code == "CANCELLED" else "failed"
                    item.content_status = "pending" if exc.code == "CANCELLED" else "failed"
                    item.error = None if exc.code == "CANCELLED" else {"code": exc.code, "message": exc.message}
                    item.updated_at = datetime.now(timezone.utc)
                continue
            except Exception:
                logger.exception("asset content failed task_id=%s item_id=%s", task_id, item_id)
                with database.write_session() as session:
                    item = session.get(AssetTaskItem, item_id)
                    item.status = "failed"
                    item.content_status = "failed"
                    item.error = {"code": "CONTENT_READ_FAILED", "message": "文件读取、散列、复制或登记失败。"}
                    item.updated_at = datetime.now(timezone.utc)
                continue
            if error == "CANCELLED":
                with database.write_session() as session:
                    item = session.get(AssetTaskItem, item_id)
                    item.status = "cancelled"
                    item.updated_at = datetime.now(timezone.utc)
                continue
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
                continue
            if item_data["format"] in {"image", "raw", "xisf", "video"}:
                with database.read_session() as session:
                    version = session.get(AssetVersion, item_data["asset_version_id"])
                    source_location, source_mode = version.storage_location, version.storage_mode
                    asset = session.get(Asset, item_data["asset_id"])
                    group_asset = asset
                    group_version = version
                try:
                    if source_mode == "managed":
                        image_path = settings.data_dir / source_location
                    else:
                        _, root_path = find_root(settings, item_data["root_id"])
                        image_path = resolve_relative(root_path, item.source_path)
                    if item_data["format"] == "video":
                        image, display = first_video_frame(image_path, 100)
                    elif item_data["format"] == "raw":
                        image, display = _raw_image(image_path), {"algorithm": PREVIEW_ALGORITHM_VERSION}
                    elif item_data["format"] == "xisf":
                        group_key = _preview_group_key(group_version, group_asset, _xisf_layout(image_path))
                        stretch, reference_id = _task_stretch(database, task_id, group_key)
                        image, display = _xisf_image(image_path, stretch)
                    else:
                        with Image.open(image_path) as source:
                            layout = source.mode
                        group_key = _preview_group_key(group_version, group_asset, layout) if layout in {"I;16", "I;16B", "I;16L", "I", "F"} else None
                        stretch, reference_id = _task_stretch(database, task_id, group_key) if group_key else (None, None)
                        image, stretch_display = _ordinary_image(image_path, stretch)
                        display = {"algorithm": PREVIEW_ALGORITHM_VERSION, **(stretch_display or {})}
                    if item_data["format"] in {"xisf", "image"} and group_key is not None:
                        display.update(stretch_group=group_key, stretch_reference_version_id=reference_id or item_data["asset_version_id"])
                    _save_preview(database, settings, item_data["asset_version_id"], 0, "thumbnail", 100, image, display)
                    if item_data["format"] in {"xisf", "image"} and group_key is not None and reference_id is None:
                        _save_task_stretch(database, task_id, group_key, display, item_data["asset_version_id"])
                    with database.write_session() as session:
                        item = session.get(AssetTaskItem, item_id)
                        item.preview_status, item.status, item.error = "available", "completed", None
                        item.updated_at = datetime.now(timezone.utc)
                except Exception as exc:
                    logger.exception("image preview failed task_id=%s item_id=%s", task_id, item_id)
                    with database.write_session() as session:
                        item = session.get(AssetTaskItem, item_id)
                        item.preview_status, item.status = "failed", "completed_with_errors"
                        label = {"video": "视频首帧", "raw": "RAW", "xisf": "XISF"}.get(item_data["format"], "常规图像")
                        item.error = {"code": "PREVIEW_FAILED", "message": f"{label}预览生成失败：{exc}"}
                        item.updated_at = datetime.now(timezone.utc)
                continue
            if item_data["format"] not in {"fits", "video"}:
                with database.write_session() as session:
                    item = session.get(AssetTaskItem, item_id)
                    item.preview_status, item.status = "unsupported", "completed"
                    item.updated_at = datetime.now(timezone.utc)
                continue
            if item_data["format"] != "fits":
                continue
            with database.read_session() as session:
                hdu = session.scalar(select(FitsHduMetadata).where(
                    FitsHduMetadata.asset_version_id == item_data["asset_version_id"],
                    FitsHduMetadata.is_selected.is_(True),
                ))
                version = session.get(AssetVersion, item_data["asset_version_id"])
                asset = session.get(Asset, item_data["asset_id"])
                hdu_index = hdu.hdu_index if hdu else None
                parameters = dict(asset.parameters or {})
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
                continue
            try:
                if source_mode == "managed":
                    image_path = settings.data_dir / source_location
                else:
                    root_obj, root_path = find_root(settings, root_id)
                    image_path = resolve_relative(root_path, source_path)
                if stopped():
                    raise IngestionError("CANCELLED", "文件处理已取消。")
                with database.read_session() as session:
                    version_for_parse = session.get(AssetVersion, item_data["asset_version_id"])
                    hdu_for_parse = session.scalar(select(FitsHduMetadata).where(
                        FitsHduMetadata.asset_version_id == item_data["asset_version_id"],
                        FitsHduMetadata.is_selected.is_(True),
                    ))
                    current_version = version_for_parse
                group_key = _preview_group_key(current_version, asset, f"{hdu_for_parse.supported_kind}:{hdu_for_parse.bitpix}")
                stretch, reference_id = _task_stretch(database, task_id, group_key)
                preview_state, preview_error, display = _fit_preview_rows(
                    database, settings, current_version.id,
                    [{"hdu_index": hdu_index, "is_selected": True, "supported_kind": hdu_for_parse.supported_kind}],
                    parameters, image_path, stretch=stretch, group_key=group_key, reference_version_id=reference_id,
                )
                if display is not None and reference_id is None:
                    _save_task_stretch(database, task_id, group_key, display, current_version.id)
                with database.write_session() as session:
                    item = session.get(AssetTaskItem, item_id)
                    item.preview_status = preview_state
                    item.metadata_status = "available"
                    item.status = "completed_with_errors" if preview_error else "completed"
                    item.error = {"code": "PREVIEW_FAILED", "message": preview_error} if preview_error else None
                    item.updated_at = datetime.now(timezone.utc)
            except IngestionError as exc:
                if exc.code == "CANCELLED":
                    with database.write_session() as session:
                        item = session.get(AssetTaskItem, item_id)
                        item.status = "cancelled"
                    continue
                with database.write_session() as session:
                    item = session.get(AssetTaskItem, item_id)
                    item.preview_status = "failed"
                    item.status = "completed_with_errors"
                    item.error = {"code": exc.code, "message": exc.message}
            except Exception:
                logger.exception("preview failed task_id=%s item_id=%s", task_id, item_id)
                with database.write_session() as session:
                    item = session.get(AssetTaskItem, item_id)
                    item.preview_status = "failed"
                    item.status = "completed_with_errors"
                    item.error = {"code": "PREVIEW_FAILED", "message": "预览生成失败；已入库内容保留。"}
        was_cancelled = _cancelled(database, task_id)
        if was_cancelled:
            _finish_task(database, task_id, True)
            _publish_dataset(database, task_data, task_id)
            return
        _publish_dataset(database, task_data, task_id)
        _finish_task(database, task_id, False)
    except Exception:
        logger.exception("asset import task failed task_id=%s", task_id)
        with database.write_session() as session:
            task = session.get(AssetTask, task_id)
            if task is not None and task.status not in {"cancelled", "interrupted"}:
                task.status = "completed_with_errors" if session.scalar(
                    select(func.count()).select_from(AssetTaskItem).where(
                        AssetTaskItem.task_id == task_id, AssetTaskItem.content_status == "available"
                    )
                ) else "failed"
                task.error = {"code": "INTERNAL_ERROR", "message": "后台处理失败；已完成的文件结果保留。"}
                task.updated_at = datetime.now(timezone.utc)


def mark_interrupted_tasks(database: Database) -> int:
    count = 0
    with database.write_session() as session:
        tasks = session.scalars(select(AssetTask).where(AssetTask.status.in_({"queued", "running", "cancelling"}))).all()
        for task in tasks:
            task.status = "interrupted"
            task.error = {"code": "SERVICE_INTERRUPTED", "message": "服务中断，等待用户检查后恢复。"}
            task.updated_at = datetime.now(timezone.utc)
            count += 1
        running_items = session.scalars(select(AssetTaskItem).where(AssetTaskItem.status == "running")).all()
        for item in running_items:
            item.status = "interrupted"
            item.updated_at = datetime.now(timezone.utc)
    return count
