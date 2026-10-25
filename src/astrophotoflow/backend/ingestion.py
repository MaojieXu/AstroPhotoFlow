from __future__ import annotations
import json
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, wait
from copy import deepcopy
import logging
import os
import tempfile
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
from .fits_preview import PARSER_VERSION, PREVIEW_ALGORITHM_VERSION, _display, _parsed_parameters, create_preview, inspect_fits, stretch_bounds
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
        level = {"masterframe": "master", "subframe": "individual"}.get(classification.get("frame_class"))
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


def _current_asset_parameters(request_values: dict, file_values: dict, defaults: dict | None = None) -> tuple[dict, dict]:
    values, sources = {}, {}
    for key in PARAMETER_KEYS:
        for candidate, source in ((request_values, "manual"), (file_values, "file"), (defaults or {}, "preset")):
            if candidate.get(key) is not None:
                values[key], sources[key] = candidate[key], source
                break
        else:
            values[key] = "standard" if key == "parameter_mode" else None
            sources[key] = "unknown"
    return values, sources


def _current_classification(request_values: dict, file_values: dict, defaults: dict) -> tuple[dict, dict]:
    if request_values:
        return ({key: request_values.get(key) for key in ("frame_class", "frame_type")},
                {"classification.frame_class": "manual", "classification.frame_type": "manual"})
    values, sources = {}, {}
    for key in ("frame_class", "frame_type"):
        observed, preset = file_values.get(key), defaults.get(key)
        values[key] = observed if observed is not None else preset
        sources[f"classification.{key}"] = "file" if observed is not None else "preset" if preset is not None else "unknown"
    if values["frame_class"] == "video":
        values["frame_type"] = None
    return values, sources


@contextmanager
def import_workers(settings: Settings):
    # One pair per service; direct maintenance/test callers own their pair.
    with ThreadPoolExecutor(max_workers=settings.file_workers, thread_name_prefix="asset-file") as files, \
            ThreadPoolExecutor(max_workers=settings.preview_workers, thread_name_prefix="asset-preview") as previews:
        yield files, previews


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
    relative = Path("previews") / version_id / f"{PREVIEW_ALGORITHM_VERSION}-{hdu_index}-{size}.jpg"
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


def _inspect_xisf(path: Path) -> dict:
    from xisf import XISF

    keywords = XISF(str(path)).get_images_metadata()[0].get("FITSKeywords", {})
    header = {keyword: entries[0]["value"] for keyword, entries in keywords.items() if entries}
    return {**_parsed_parameters(header), "xisf_fits_keywords": deepcopy(keywords)}


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
        task_ids = session.scalars(select(AssetTaskItem.task_id).join(AssetTask, AssetTask.id == AssetTaskItem.task_id)
            .where(AssetTaskItem.asset_version_id == version_id).order_by(AssetTask.created_at, AssetTask.id)).all()
        group_key = _preview_group_key(version, asset, layout)
    for task_id in task_ids:
        stretch, reference_id = _task_stretch(database, task_id, group_key)
        if stretch is not None:
            return task_id, group_key, stretch, reference_id
    return (task_ids[0] if task_ids else None), group_key, None, None


def _raw_image(path: Path, max_edge: int = 100) -> Image.Image:
    import rawpy

    with rawpy.imread(str(path)) as raw:
        source_edge = max(raw.sizes.width, raw.sizes.height)
        threshold = min(max_edge, source_edge)
        try:
            thumbnail = raw.extract_thumb()
            if thumbnail.format == rawpy.ThumbFormat.JPEG:
                with Image.open(BytesIO(thumbnail.data)) as image:
                    if max(image.size) >= threshold:
                        return ImageOps.exif_transpose(image).convert("RGB").copy()
            elif thumbnail.format == rawpy.ThumbFormat.BITMAP:
                image = Image.fromarray(thumbnail.data)
                if max(image.size) >= threshold:
                    return image.convert("RGB").copy()
        except (rawpy.LibRawError, OSError, ValueError):
            pass
        return Image.fromarray(raw.postprocess(half_size=source_edge // 2 >= max_edge, output_bps=8, output_color=rawpy.ColorSpace.sRGB)).convert("RGB")


def backfill_missing_previews(database: Database, settings: Settings) -> dict[str, int]:
    with database.read_session() as session:
        versions = session.scalars(select(AssetVersion).join(Asset, Asset.id == AssetVersion.asset_id)
            .where(Asset.scope == "shared", AssetVersion.availability == "available")).all()
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
                    with database.read_session() as session:
                        version = session.get(AssetVersion, version_id)
                        asset = session.get(Asset, version.asset_id)
                        parameters = dict(asset.parameters or {})
                    inspected = inspect_fits(path, parameters.get("cfa_pattern"))
                    selected_data = next((row for row in inspected["hdus"] if row["is_selected"]), None)
                    if selected_data is None:
                        raise ValueError("FITS 没有已选中的图像 HDU。")
                    with database.write_session() as session:
                        selected = session.execute(select(FitsHduMetadata).where(
                            FitsHduMetadata.asset_version_id == version_id,
                            FitsHduMetadata.hdu_index == selected_data["hdu_index"],
                        )).scalar_one()
                        for key, value in selected_data.items():
                            setattr(selected, key, value)
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
        category = (version.scientific_metadata or {}).get("format")
        current_parameters, value_sources = dict(asset.parameters or {}), dict(asset.value_sources or {})
    if storage_mode == "managed":
        path = settings.data_dir / storage_location
    try:
        if storage_mode != "managed":
            _, root = find_root(settings, root_id)
            path = resolve_relative(root, source_path)
        if category == "xisf":
            hdu_rows, parsed = [], _inspect_xisf(path)
        else:
            result = inspect_fits(path, current_parameters.get("cfa_pattern"))
            hdu_rows, parsed = result["hdus"], result["parsed_parameters"]
        error = None
    except Exception:
        hdu_rows, parsed = [], {}
        error = f"{category.upper()} 元数据解析失败；原始文件已完成内容入库。"
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
        classification = dict(asset.classification or {})
        for key, value in (parsed.get("classification") or {}).items():
            if value is not None and sources.get(f"classification.{key}") != "manual":
                classification[key] = value
                sources[f"classification.{key}"] = "file"
        asset.classification = classification
        asset.role = _role(classification)[0]
        asset.parameters, asset.value_sources = parameters, sources
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
            preview.status = "pending"
        item.error = {"code": f"{category.upper()}_PARSE_FAILED", "message": error} if error else None
        item.updated_at = datetime.now(timezone.utc)
    return error


def _register_asset(database: Database, settings: Settings, task_data: dict, item_id: str) -> None:
    with database.read_session() as session:
        item = session.get(AssetTaskItem, item_id)
        if item.asset_version_id is not None:
            return
        root_id, source_path = item.root_id, item.source_path
    if root_id == "__upload__":
        upload = next(file for file in task_data["upload_files"] if file["stored_name"] == source_path)
        asset_name = upload["name"]
        original = settings.data_dir / "upload-staging" / task_data["upload_source_task_id"] / source_path
        location = ""
    else:
        root_spec, root = find_root(settings, root_id)
        original = resolve_relative(root, source_path)
        asset_name = Path(source_path).name
        location = f"roots/{root_spec.id}/{source_path}"
    if not original.is_file():
        raise IngestionError("SOURCE_UNAVAILABLE", "所选来源不是可读文件。")
    category = format_for_path(original)
    if category not in SUPPORTED_EXTENSIONS.values():
        raise IngestionError("UNSUPPORTED_FORMAT", "该文件格式不在本阶段入库清单中。")
    parsed, hdu_rows, parse_error = {}, [], None
    defaults = task_data.get("import_defaults_snapshot") or {}
    if category in {"fits", "xisf"}:
        try:
            if category == "xisf":
                parsed = _inspect_xisf(original)
            else:
                inspected = inspect_fits(original, task_data["parameters"].get("cfa_pattern"))
                parsed, hdu_rows = inspected["parsed_parameters"], inspected["hdus"]
        except Exception:
            parse_error = f"{category.upper()} 元数据解析失败；原始文件仍将继续内容入库。"
    parameters, value_sources = _current_asset_parameters(task_data["parameters"], parsed, defaults.get("parameters"))
    if category == "fits" and not parse_error and parameters.get("cfa_pattern") and not parsed.get("cfa_pattern") and not task_data["parameters"].get("cfa_pattern"):
        hdu_rows = inspect_fits(original, parameters["cfa_pattern"])["hdus"]
    classification, classification_sources = _current_classification(
        task_data["classification"], parsed.get("classification") or {}, defaults.get("classification") or {})
    value_sources.update(classification_sources)
    role, calibration_level = _role(classification)
    version_id, asset_id = str(uuid4()), str(uuid4())
    if task_data["storage_mode"] == "managed":
        suffix = "".join(original.suffixes[-2:]) if original.name.lower().endswith((".fits.fz", ".fit.fz")) else original.suffix
        location = (Path("objects") / version_id / f"source{suffix.lower()}").as_posix()
    metadata_status = "failed" if parse_error else "available" if category in {"fits", "xisf"} else "unsupported"
    with database.write_session() as session:
        item = session.get(AssetTaskItem, item_id)
        asset = Asset(id=asset_id, name=Path(asset_name).stem or asset_name, scope="shared", owner_project_id=None,
                      role=role, current_version_id=None, classification=classification, parameters=parameters,
                      value_sources=value_sources, notes=task_data["notes"] if task_data["target_dataset_id"] is None else None,
                      status="active", revision=1)
        session.add(asset)
        session.flush()
        session.add(AssetVersion(
            id=version_id, asset_id=asset_id, version_number=1, storage_mode=task_data["storage_mode"],
            storage_location=location, byte_size=None, content_hash=None, availability="unknown",
            camera_id=parameters.get("camera_id"), optical_system_id=parameters.get("optical_system_id"),
            filter_id=parameters.get("filter_id"), capture_profile_id=None, frame_type=classification.get("frame_type"),
            calibration_level=calibration_level,
            capture_snapshot={**{key: parameters.get(key) for key in PARAMETER_KEYS}, "import_provenance": {
                "value_sources": deepcopy(value_sources), "observed_parameters": deepcopy(parsed),
                "defaults_snapshot": deepcopy(defaults),
            }},
            scientific_metadata={"format": category, "metadata_status": metadata_status,
                                 "parse_error": parse_error, "observed_parameters": parsed},
        ))
        session.flush()
        asset.current_version_id = version_id
        item.asset_id, item.asset_version_id = asset_id, version_id
        item.metadata_status, item.status = metadata_status, "running"
        item.error = {"code": f"{category.upper()}_PARSE_FAILED", "message": parse_error} if parse_error else None
        item.updated_at = datetime.now(timezone.utc)
        for row in hdu_rows:
            session.add(FitsHduMetadata(id=str(uuid4()), asset_version_id=version_id, **row))


def _create_asset_content(database: Database, settings: Settings, task_data: dict, item_id: str) -> str | None:
    # Retain this entry point for recovery and direct maintenance callers.
    _register_asset(database, settings, task_data, item_id)
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
    if refresh:
        return _refresh_fits_metadata(database, settings, item_id, asset_id, version_id)
    if _cancelled(database, task_data["id"]):
        return "CANCELLED"
    final = settings.data_dir / location if mode == "managed" else None
    # Only complete files reach the allocated object path. A crash after rename
    # can leave the database pending; resume hashes that object without recopying.
    if final is not None and final.is_file():
        original = final
    elif root_id == "__upload__":
        original = settings.data_dir / "upload-staging" / task_data["upload_source_task_id"] / source_path
    else:
        _, root = find_root(settings, root_id)
        original = resolve_relative(root, source_path)
    stage = None
    if final is not None and original != final and root_id != "__upload__":
        stage = settings.data_dir / "staging" / task_data["id"] / f"{item_id}.part"
        stage.parent.mkdir(parents=True, exist_ok=True)
        stage.unlink(missing_ok=True)
    try:
        content_hash, byte_size = _read_hash_and_copy(original, stage, lambda: _cancelled(database, task_data["id"]))
        if _cancelled(database, task_data["id"]):
            return "CANCELLED"
        if final is not None and original != final:
            final.parent.mkdir(parents=True, exist_ok=True)
            os.replace(stage if stage is not None else original, final)
        with database.write_session() as session:
            item = session.get(AssetTaskItem, item_id)
            version = session.get(AssetVersion, item.asset_version_id)
            version.content_hash, version.byte_size, version.availability = content_hash, byte_size, "available"
            item.content_status = "available"
            item.updated_at = datetime.now(timezone.utc)
        return None
    finally:
        if stage is not None:
            stage.unlink(missing_ok=True)


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
            existing_versions = {member.asset_version_id for member in base_members}
            additions = []
            for item in successes:
                if item.asset_version_id not in existing_versions:
                    additions.append((item.asset_version_id, item.source_path))
                    existing_versions.add(item.asset_version_id)
            if not additions and dataset.current_version_id is not None:
                return None
            if dataset.current_version_id is not None:
                expected = task.dataset_base_revision
                if expected is None or dataset.revision != expected:
                    raise RuntimeError(f"DATASET_REVISION_CONFLICT:{expected}:{dataset.revision}")
            version_id = str(uuid4())
            previous_version = session.get(DatasetVersion, dataset.current_version_id) if dataset.current_version_id else None
            version = DatasetVersion(id=version_id, dataset_id=target_id, version_number=version_number,
                                     calibration_defaults=dict(previous_version.calibration_defaults) if previous_version else {})
            session.add(version)
            session.flush()
            for index, member in enumerate(base_members):
                session.add(DatasetMember(
                    id=str(uuid4()), dataset_version_id=version_id, asset_version_id=member.asset_version_id,
                    position=index, relative_path=member.relative_path,
                    calibration_overrides=dict(member.calibration_overrides),
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
        if task.status == "interrupted":
            return
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


def _process_preview(database: Database, settings: Settings, task_data: dict, item_id: str) -> None:
    task_id = task_data["id"]
    if _cancelled(database, task_id):
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
                item.preview_status = "available"
                item.status = "completed_with_errors" if item.metadata_status == "failed" else "completed"
                if item.metadata_status != "failed":
                    item.error = None
                item.updated_at = datetime.now(timezone.utc)
        except Exception as exc:
            logger.exception("image preview failed task_id=%s item_id=%s", task_id, item_id)
            with database.write_session() as session:
                item = session.get(AssetTaskItem, item_id)
                item.preview_status, item.status = "failed", "completed_with_errors"
                label = {"video": "视频首帧", "raw": "RAW", "xisf": "XISF"}.get(item_data["format"], "常规图像")
                item.error = {"code": "PREVIEW_FAILED", "message": f"{label}预览生成失败：{exc}"}
                item.updated_at = datetime.now(timezone.utc)
        return
    if item_data["format"] not in {"fits", "video"}:
        with database.write_session() as session:
            item = session.get(AssetTaskItem, item_id)
            item.preview_status, item.status = "unsupported", "completed"
            item.updated_at = datetime.now(timezone.utc)
        return
    if item_data["format"] != "fits":
        return
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
        return
    try:
        if source_mode == "managed":
            image_path = settings.data_dir / source_location
        else:
            root_obj, root_path = find_root(settings, root_id)
            image_path = resolve_relative(root_path, source_path)
        if _cancelled(database, task_id):
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
            return
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

def _content_item(database: Database, settings: Settings, task_data: dict, item_id: str) -> None:
    try:
        with database.write_session() as session:
            item = session.get(AssetTaskItem, item_id)
            item.status = "running"
            item.updated_at = datetime.now(timezone.utc)
        error = _create_asset_content(database, settings, task_data, item_id)
        if error == "CANCELLED":
            with database.write_session() as session:
                session.get(AssetTaskItem, item_id).status = "cancelled"
    except Exception as exc:
        logger.exception("asset content failed task_id=%s item_id=%s", task_data["id"], item_id)
        code = exc.code if isinstance(exc, IngestionError) else "CONTENT_READ_FAILED"
        message = exc.message if isinstance(exc, IngestionError) else "文件读取、散列或复制失败；已登记资料保留。"
        with database.write_session() as session:
            item = session.get(AssetTaskItem, item_id)
            item.status = "cancelled" if code == "CANCELLED" else "failed"
            item.content_status = "pending" if code == "CANCELLED" else "failed"
            item.error = None if code == "CANCELLED" else {"code": code, "message": message}
            item.updated_at = datetime.now(timezone.utc)


def _registration_progress(database: Database, task_id: str, total: int, registered: int, completed: bool = False) -> None:
    with database.write_session() as session:
        task = session.get(AssetTask, task_id)
        task.report = {**(task.report or {}), "registration": {
            "total": total,
            "registered": registered,
            "completed": completed,
        }}
        task.updated_at = datetime.now(timezone.utc)


def _preview_group(database: Database, settings: Settings, task_data: dict, item_ids: list[str]) -> None:
    # A group is a single executor job: reference selection always follows position.
    for item_id in item_ids:
        _process_preview(database, settings, task_data, item_id)


def process_task(database: Database, settings: Settings, task_id: str, workers=None) -> None:
    if workers is None:
        with import_workers(settings) as owned_workers:
            return process_task(database, settings, task_id, owned_workers)
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
                "import_defaults_snapshot": deepcopy(task.import_defaults_snapshot),
                "notes": task.notes, "dataset_name": task.dataset_name,
                "target_dataset_id": task.target_dataset_id, "dataset_base_revision": task.dataset_base_revision,
                "retry_of_task_id": task.retry_of_task_id,
                "upload_manifest": bool((task.report or {}).get("upload_manifest")),
                "upload_files": (task.report or {}).get("upload_files", []),
                "upload_source_task_id": (task.report or {}).get("upload_source_task_id", task.id),
            }
        if not task_data["retry_of_task_id"]:
            _enumerate_task(database, settings, task_id, task_data)
        with database.read_session() as session:
            items = session.scalars(select(AssetTaskItem).where(AssetTaskItem.task_id == task_id)
                                    .order_by(AssetTaskItem.position)).all()
            item_ids = [item.id for item in items if item.status in {"queued", "interrupted", "running"}]
            counted = {item.id for item in items if item.asset_id is not None or item.status in {"failed", "skipped"}}
        _registration_progress(database, task_id, len(items), len(counted))
        registered_ids = []
        for item_id in item_ids:
            if _cancelled(database, task_id):
                with database.write_session() as session:
                    session.get(AssetTaskItem, item_id).status = "cancelled"
                continue
            try:
                _register_asset(database, settings, task_data, item_id)
                registered_ids.append(item_id)
            except Exception as exc:
                logger.exception("asset registration failed task_id=%s item_id=%s", task_id, item_id)
                with database.write_session() as session:
                    item = session.get(AssetTaskItem, item_id)
                    item.status, item.content_status = "failed", "failed"
                    item.metadata_status, item.preview_status = "unsupported", "unsupported"
                    item.error = {"code": exc.code if isinstance(exc, IngestionError) else "REGISTRATION_FAILED",
                                  "message": exc.message if isinstance(exc, IngestionError) else "文件资料登记失败。"}
            counted.add(item_id)
            _registration_progress(database, task_id, len(items), len(counted))
        _publish_dataset(database, task_data, task_id)
        _registration_progress(database, task_id, len(items), len(counted), not _cancelled(database, task_id))
        file_workers, preview_workers = workers
        futures = [file_workers.submit(_content_item, database, settings, task_data, item_id) for item_id in registered_ids]
        wait(futures)
        for future in futures:
            future.result()
        groups = {}
        with database.read_session() as session:
            for item_id in registered_ids:
                item = session.get(AssetTaskItem, item_id)
                if item.content_status != "available" or item.status == "cancelled":
                    continue
                version = session.get(AssetVersion, item.asset_version_id)
                asset = session.get(Asset, item.asset_id)
                category = (version.scientific_metadata or {}).get("format")
                # FITS headers already supply the full homogeneous grouping key.
                # Other formats run in their fixed order within one format job.
                hdu = session.scalar(select(FitsHduMetadata).where(FitsHduMetadata.asset_version_id == version.id,
                                                                 FitsHduMetadata.is_selected.is_(True)))
                key = _preview_group_key(version, asset, f"{hdu.supported_kind}:{hdu.bitpix}") if hdu else category
                groups.setdefault(key, []).append(item_id)
        futures = [preview_workers.submit(_preview_group, database, settings, task_data, group) for group in groups.values()]
        wait(futures)
        for future in futures:
            future.result()
        _finish_task(database, task_id, _cancelled(database, task_id))
    except Exception:
        logger.exception("asset import task failed task_id=%s", task_id)
        with database.write_session() as session:
            task = session.get(AssetTask, task_id)
            if task is not None and task.status not in {"cancelled", "interrupted"}:
                task.status = "completed_with_errors" if session.scalar(select(func.count()).select_from(AssetTaskItem)
                    .where(AssetTaskItem.task_id == task_id, AssetTaskItem.content_status == "available")) else "failed"
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
