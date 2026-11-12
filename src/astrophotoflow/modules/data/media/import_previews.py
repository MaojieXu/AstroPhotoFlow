from __future__ import annotations
import logging
import os
import tempfile
from pathlib import Path
from uuid import uuid4
from PIL import Image
from sqlalchemy import select
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.localization import error_message, workspace_locale
from astrophotoflow.modules.data.assets.metadata import asset_parameters
from astrophotoflow.modules.data.assets.models import Asset, FitsHduMetadata
from astrophotoflow.modules.data.files import find_root, resolve_relative
from astrophotoflow.modules.data.formats.fits import PREVIEW_ALGORITHM_VERSION, create_preview, inspect_fits
from astrophotoflow.modules.data.formats.raster import read_raster_preview
from astrophotoflow.modules.data.formats.raw import read_raw_preview
from astrophotoflow.modules.data.formats.video import first_video_frame
from astrophotoflow.modules.data.formats.xisf import read_xisf_preview
from astrophotoflow.modules.data.imports.models import AssetTask, AssetTaskItem
from astrophotoflow.modules.data.media.models import Preview
from astrophotoflow.modules.data.media.recipes import backfill_context, describe_recipe

logger = logging.getLogger(__name__)


def fit_preview_rows(
    database: Database,
    settings: Settings,
    asset_id: str,
    hdu_rows: list[dict],
    parameters: dict,
    path: Path,
    missing_only: bool = False,
    context: dict | None = None,
) -> tuple[str, str | None, dict | None]:
    with database.read_session() as session:
        asset = session.get(Asset, asset_id)
        parameters = {**parameters, "colour_layout": (asset.scientific_metadata or {}).get("colour_layout")}
    selected = next((row for row in hdu_rows if row["is_selected"]), None)
    if selected is None:
        return ("unsupported", None, None)
    if selected["supported_kind"] in {"xtrans", "quad_bayer"}:
        return (
            "unsupported",
            error_message(
                workspace_locale(settings.workspace), "", "import_cfa_preview_unsupported", {"layout": selected["supported_kind"]}
            ),
            None,
        )
    failed = None
    display = None
    for size, edge in (("thumbnail", 100),):
        try:
            if missing_only:
                with database.read_session() as session:
                    existing = session.scalar(
                        select(Preview.id).where(
                            Preview.asset_id == asset_id,
                            Preview.hdu_index == selected["hdu_index"],
                            Preview.size == size,
                            Preview.algorithm_version == PREVIEW_ALGORITHM_VERSION,
                            Preview.status == "available",
                        )
                    )
                if existing:
                    continue
            image, display = create_preview(
                path,
                selected["hdu_index"],
                selected["supported_kind"],
                parameters,
                edge,
                auto=context["auto"] if context else False,
                auto_stretch=context["auto_stretch"] if context else None,
            )
            if context:
                display = describe_recipe(context, display)
            preview_id = str(uuid4())
            relative = Path("previews") / asset_id / f"{PREVIEW_ALGORITHM_VERSION}-{selected['hdu_index']}-thumbnail.jpg"
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
                preview = session.scalar(
                    select(Preview).where(
                        Preview.asset_id == asset_id,
                        Preview.hdu_index == selected["hdu_index"],
                        Preview.size == size,
                        Preview.algorithm_version == PREVIEW_ALGORITHM_VERSION,
                    )
                )
                if preview is None:
                    preview = Preview(
                        id=preview_id,
                        asset_id=asset_id,
                        hdu_index=selected["hdu_index"],
                        size=size,
                        width=image.width,
                        height=image.height,
                        storage_path=relative.as_posix(),
                        mime_type="image/jpeg",
                        display_parameters=display,
                        algorithm_version=PREVIEW_ALGORITHM_VERSION,
                        status="available",
                        error=None,
                    )
                    session.add(preview)
                else:
                    preview.width, preview.height = (image.width, image.height)
                    preview.storage_path, preview.mime_type = (relative.as_posix(), "image/jpeg")
                    preview.display_parameters, preview.status, preview.error = (display, "available", None)
        except Exception:
            logger.exception("Import metadata parsing failed")
            logger.exception("preview failed asset_id=%s size=%s", asset_id, size)
            failed = error_message(workspace_locale(settings.workspace), "", "import_hdu_preview_failed")
            with database.write_session() as session:
                preview = session.scalar(
                    select(Preview).where(
                        Preview.asset_id == asset_id,
                        Preview.hdu_index == selected["hdu_index"],
                        Preview.size == size,
                        Preview.algorithm_version == PREVIEW_ALGORITHM_VERSION,
                    )
                )
                if preview is None:
                    preview = Preview(
                        id=str(uuid4()),
                        asset_id=asset_id,
                        hdu_index=selected["hdu_index"],
                        size=size,
                        width=0,
                        height=0,
                        storage_path="",
                        mime_type="image/jpeg",
                        display_parameters={"algorithm": PREVIEW_ALGORITHM_VERSION},
                        algorithm_version=PREVIEW_ALGORITHM_VERSION,
                        status="failed",
                        error=failed,
                    )
                    session.add(preview)
                else:
                    preview.width, preview.height = (0, 0)
                    preview.storage_path, preview.status, preview.error = ("", "failed", failed)
                    preview.display_parameters = {"algorithm": PREVIEW_ALGORITHM_VERSION}
    return ("failed" if failed else "available", failed, display if not failed else None)


def save_preview(
    database: Database,
    settings: Settings,
    asset_id: str,
    hdu_index: int,
    size: str,
    edge: int,
    image: Image.Image,
    display_parameters: dict | None = None,
) -> None:
    image.thumbnail((edge, edge), Image.Resampling.LANCZOS)
    preview_id = str(uuid4())
    relative = Path("previews") / asset_id / f"{PREVIEW_ALGORITHM_VERSION}-{hdu_index}-{size}.jpg"
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
        preview = session.scalar(
            select(Preview).where(
                Preview.asset_id == asset_id,
                Preview.hdu_index == hdu_index,
                Preview.size == size,
                Preview.algorithm_version == PREVIEW_ALGORITHM_VERSION,
            )
        )
        if preview is None:
            preview = Preview(
                id=preview_id,
                asset_id=asset_id,
                hdu_index=hdu_index,
                size=size,
                width=image.width,
                height=image.height,
                storage_path=relative.as_posix(),
                mime_type="image/jpeg",
                display_parameters=display_parameters or {"algorithm": PREVIEW_ALGORITHM_VERSION},
                algorithm_version=PREVIEW_ALGORITHM_VERSION,
                status="available",
                error=None,
            )
            session.add(preview)
        else:
            preview.width, preview.height = (image.width, image.height)
            preview.storage_path, preview.mime_type = (relative.as_posix(), "image/jpeg")
            preview.display_parameters = display_parameters or {"algorithm": PREVIEW_ALGORITHM_VERSION}
            preview.status, preview.error = ("available", None)


def backfill_missing_previews(database: Database, settings: Settings) -> dict[str, int]:
    with database.read_session() as session:
        assets = (
            session.scalars(
                select(Asset)
                .outerjoin(AssetTaskItem, AssetTaskItem.asset_id == Asset.id)
                .outerjoin(AssetTask, AssetTask.id == AssetTaskItem.task_id)
                .where(Asset.scope == "shared", Asset.availability == "available")
                .order_by(AssetTask.created_at, AssetTask.id, AssetTaskItem.position, Asset.created_at, Asset.id)
            )
            .unique()
            .all()
        )
        rows = [(row.id, row.storage_mode, row.storage_location, row.scientific_metadata or {}) for row in assets]
    generated = failed = 0
    for asset_id, mode, location, metadata in rows:
        if metadata.get("format") not in {"image", "raw", "xisf", "fits", "video"}:
            continue
        with database.read_session() as session:
            selected = session.scalar(
                select(FitsHduMetadata).where(FitsHduMetadata.asset_id == asset_id, FitsHduMetadata.is_selected.is_(True))
            )
            available = set(
                session.scalars(
                    select(Preview.size).where(
                        Preview.asset_id == asset_id,
                        Preview.hdu_index == (selected.hdu_index if selected else 0),
                        Preview.algorithm_version == PREVIEW_ALGORITHM_VERSION,
                        Preview.status == "available",
                    )
                ).all()
            )
        if "thumbnail" in available:
            continue
        try:
            context = backfill_context(database, asset_id)
            if mode == "managed":
                path = settings.data_dir / location
            else:
                _, root_id, relative = location.split("/", 2)
                _, root = find_root(settings, root_id)
                path = resolve_relative(root, relative)
            if metadata.get("format") in {"raw", "xisf"}:
                if metadata["format"] == "raw":
                    image, display = (read_raw_preview(path), {"algorithm": PREVIEW_ALGORITHM_VERSION})
                else:
                    image, display = read_xisf_preview(path, auto=context["auto"], auto_stretch=context["auto_stretch"])
                    display = describe_recipe(context, display)
                save_preview(database, settings, asset_id, 0, "thumbnail", 100, image, display)
            elif metadata.get("format") == "fits":
                if selected is None:
                    with database.read_session() as session:
                        asset = session.get(Asset, asset_id)
                        parameters = dict(asset_parameters(asset) or {})
                    inspected = inspect_fits(path, parameters.get("cfa_pattern"), colour_layout=metadata.get("colour_layout"))
                    selected_data = next((row for row in inspected["hdus"] if row["is_selected"]), None)
                    if selected_data is None:
                        raise ValueError("FITS 没有已选中的图像 HDU。")
                    with database.write_session() as session:
                        selected = session.execute(
                            select(FitsHduMetadata).where(
                                FitsHduMetadata.asset_id == asset_id, FitsHduMetadata.hdu_index == selected_data["hdu_index"]
                            )
                        ).scalar_one()
                        for key, value in selected_data.items():
                            setattr(selected, key, value)
                if selected.supported_kind in {"xtrans", "quad_bayer"}:
                    continue
                with database.read_session() as session:
                    asset = session.get(Asset, asset_id)
                    hdu_rows = [{"hdu_index": selected.hdu_index, "is_selected": True, "supported_kind": selected.supported_kind}]
                    parameters = dict(asset_parameters(asset) or {})
                _, error, _ = fit_preview_rows(database, settings, asset_id, hdu_rows, parameters, path, missing_only=True, context=context)
                if error:
                    raise ValueError(error)
            elif metadata.get("format") == "video":
                image, display = first_video_frame(path, 100)
                save_preview(database, settings, asset_id, 0, "thumbnail", 100, image, display)
            else:
                image, stretch_display = read_raster_preview(path, auto=context["auto"], auto_stretch=context["auto_stretch"])
                if stretch_display is not None:
                    stretch_display = describe_recipe(context, stretch_display)
                save_preview(database, settings, asset_id, 0, "thumbnail", 100, image, stretch_display)
            generated += 1
        except Exception:
            logger.exception("Import metadata parsing failed")
            logger.exception("preview backfill failed asset_id=%s", asset_id)
            failed += 1
    return {"generated": generated, "failed": failed}
