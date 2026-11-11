"""Schedule and generate display derivatives without HTTP dependencies."""

from __future__ import annotations
import logging
import os
from pathlib import Path
from uuid import UUID, uuid4
import numpy as np
from PIL import Image, ImageOps
from sqlalchemy import select
from astrophotoflow.contracts.previews import AutoStretch
from astrophotoflow.core.errors import not_found
from astrophotoflow.core.localization import error_message, workspace_locale
from astrophotoflow.modules.data.assets.metadata import asset_parameters
from astrophotoflow.modules.data.assets.models import Asset, FitsHduMetadata
from astrophotoflow.modules.data.files import find_root, resolve_relative
from astrophotoflow.modules.data.formats.fits import PREVIEW_ALGORITHM_VERSION, create_preview, read_preview_pixels, read_stretch_pixels
from astrophotoflow.modules.data.formats.pixels import calculate_stretch, render_stretch, sample_statistics
from astrophotoflow.modules.data.formats.raster import read_raster_preview
from astrophotoflow.modules.data.formats.raw import read_raw_preview
from astrophotoflow.modules.data.formats.video import first_video_frame
from astrophotoflow.modules.data.formats.xisf import read_xisf_pixels, read_xisf_preview
from astrophotoflow.modules.data.media.models import Preview
from astrophotoflow.modules.data.media.recipes import backfill_context, describe_recipe, save_group_recipe
from astrophotoflow.modules.data.trash.models import LibraryEntryRemoval

logger = logging.getLogger("astrophotoflow.service.previews")
DISPLAY_EDGE = 1080


def _issue(settings, status, code, message_key):
    return {"status": status, "error": {"code": code, "message": error_message(workspace_locale(settings.workspace), code, message_key)}}


class DisplayPreviews:
    def __init__(self, database, settings, executor, *, recover=True):
        self.database, self.settings, self.executor = (database, settings, executor)
        if not recover:
            return
        with database.write_session() as session:
            for row in session.scalars(select(Preview).where(Preview.size == "display", Preview.status == "generating")).all():
                row.status, row.error = ("failed", error_message(workspace_locale(self.settings.workspace), "", "preview_interrupted"))

    def _resolve(self, session, asset_id, *, refresh=False):
        asset = session.get(Asset, asset_id)
        if asset is None:
            raise not_found()
        category = (asset.scientific_metadata or {}).get("format")
        hdu = session.scalar(select(FitsHduMetadata).where(FitsHduMetadata.asset_id == asset_id, FitsHduMetadata.is_selected.is_(True)))
        index = hdu.hdu_index if hdu else 0
        key = (Preview.asset_id == asset_id, Preview.hdu_index == index, Preview.algorithm_version == PREVIEW_ALGORITHM_VERSION)
        display = session.scalar(select(Preview).where(*key, Preview.size == "display"))
        thumbnail = session.scalar(select(Preview).where(*key, Preview.size == "thumbnail", Preview.status == "available"))
        if display is not None:
            if (
                not refresh
                and display.status == "available"
                and (thumbnail is not None)
                and (self.settings.data_dir / display.storage_path).is_file()
            ):
                return (display, None, {"status": "available", "width": display.width, "height": display.height, "error": None})
            if display.status == "generating":
                return (display, None, {"status": "generating", "error": None})
        if category not in {"fits", "xisf", "image", "raw", "video"} or (
            category == "fits" and (hdu is None or hdu.supported_kind in {"xtrans", "quad_bayer"})
        ):
            return (display, None, _issue(self.settings, "unsupported", "PREVIEW_UNSUPPORTED", "preview_layout_unsupported"))
        if asset.availability != "available":
            return (display, None, _issue(self.settings, "not_ready", "SOURCE_NOT_READY", "preview_original_not_ready"))
        if category in {"fits", "xisf"} and (asset.scientific_metadata or {}).get("metadata_status") == "failed":
            return (display, None, _issue(self.settings, "not_ready", "METADATA_NOT_READY", "preview_metadata_not_ready"))
        removals = session.scalars(select(LibraryEntryRemoval)).all()
        if any(
            (
                row.cleanup_status != "trash"
                and (
                    row.entry_type == "asset"
                    and row.entry_id == asset.id
                    or (row.entry_type == "dataset" and asset.id in (row.member_asset_ids or []))
                )
                for row in removals
            )
        ):
            return (display, None, _issue(self.settings, "not_ready", "SOURCE_CLEANUP_ACTIVE", "preview_cleanup_active"))
        recipe = dict(thumbnail.display_parameters or {}) if thumbnail else dict(display.display_parameters or {}) if display else {}
        context = backfill_context(self.database, asset_id) if thumbnail is None else None
        if context and context["auto_stretch"] is not None:
            recipe = describe_recipe(context, {"auto_stretch": context["auto_stretch"]})
        if asset.storage_mode == "managed":
            path = self.settings.data_dir / asset.storage_location
        else:
            _, root_id, relative = asset.storage_location.split("/", 2)
            _, root = find_root(self.settings, root_id)
            path = resolve_relative(root, relative)
        job = {
            "asset_id": asset_id,
            "hdu_index": index,
            "kind": hdu.supported_kind if hdu else None,
            "category": category,
            "path": path,
            "recipe": recipe,
            "update_thumbnail": thumbnail is None,
            "context": context,
            "auto": bool(context and context["auto"] and ("auto_stretch" not in recipe)),
            "parameters": {**dict(asset_parameters(asset) or {}), "colour_layout": (asset.scientific_metadata or {}).get("colour_layout")},
        }
        if display is not None:
            return (
                display,
                job,
                {"status": "failed", "error": {"code": "PREVIEW_FAILED", "message": display.error}}
                if display.error
                else _issue(self.settings, "failed", "PREVIEW_FAILED", "preview_cache_unavailable"),
            )
        return (None, job, _issue(self.settings, "not_ready", "DISPLAY_NOT_GENERATED", "preview_not_generated"))

    def status(self, asset_id):
        with self.database.read_session() as session:
            row, _, state = self._resolve(session, asset_id)
            stretch = (row.display_parameters or {}).get("auto_stretch") if row and state["status"] == "available" else None
        return {"asset_id": UUID(asset_id), "size": "display", **state, "stretch": AutoStretch(**stretch) if stretch is not None else None}

    def schedule(self, asset_id, *, auto=False):
        self.executor.prioritize({asset_id})
        with self.database.write_session() as session:
            row, job, state = self._resolve(session, asset_id)
            if auto and state["status"] == "available" and ("auto_stretch" not in (row.display_parameters or {})):
                row, job, state = self._resolve(session, asset_id, refresh=True)
            if job is None:
                return {
                    "asset_id": UUID(asset_id),
                    "size": "display",
                    **state,
                    "stretch": (row.display_parameters or {}).get("auto_stretch") if row and state["status"] == "available" else None,
                }
            if auto and "auto_stretch" not in job["recipe"]:
                job["auto"] = True
                job["update_thumbnail"] = True
            if row is None:
                row = Preview(
                    id=str(uuid4()),
                    asset_id=asset_id,
                    hdu_index=job["hdu_index"],
                    size="display",
                    algorithm_version=PREVIEW_ALGORITHM_VERSION,
                    width=0,
                    height=0,
                    storage_path="",
                    mime_type="image/jpeg",
                    display_parameters=job["recipe"],
                    status="generating",
                    error=None,
                )
                session.add(row)
            row.status, row.error = ("generating", None)
            if not row.storage_path:
                row.storage_path = (Path("previews") / asset_id / f"{PREVIEW_ALGORITHM_VERSION}-{job['hdu_index']}-display.jpg").as_posix()
            preview_id = row.id
        try:
            self.executor.submit(self._generate, preview_id, job)
        except Exception:
            logger.exception("display preview could not be queued asset_id=%s", asset_id)
            self._fail(preview_id, error_message(workspace_locale(self.settings.workspace), "", "preview_queue_failed"))
        return self.status(asset_id)

    def _fail(self, preview_id, message):
        with self.database.write_session() as session:
            row = session.get(Preview, preview_id)
            if row is not None:
                row.status, row.error = ("failed", message)

    def _pixels(self, job):
        path, category = (job["path"], job["category"])
        if category == "fits":
            parameters = {**job["parameters"], "cfa_pattern": job["recipe"].get("cfa_pattern") or job["parameters"].get("cfa_pattern")}
            pixels, _ = read_preview_pixels(path, job["hdu_index"], job["kind"], parameters, DISPLAY_EDGE)
            if job.get("auto"):
                job["statistics_pixels"] = read_stretch_pixels(path, job["hdu_index"], job["kind"], parameters)
        elif category == "xisf":
            pixels = read_xisf_pixels(path)
        elif category == "raw":
            pixels = np.asarray(read_raw_preview(path, DISPLAY_EDGE))
        elif category == "video":
            pixels = np.asarray(first_video_frame(path, DISPLAY_EDGE)[0])
        else:
            with Image.open(path) as source:
                image = ImageOps.exif_transpose(source)
                if image.mode not in {"L", "I;16", "I;16B", "I;16L", "I", "F"}:
                    image = image.convert("RGB")
                pixels = np.array(image)
        if job.get("auto") and category != "fits":
            job["statistics_pixels"] = sample_statistics(pixels)
        stride = max(1, (max(pixels.shape[:2]) + DISPLAY_EDGE - 1) // DISPLAY_EDGE)
        return pixels[::stride, ::stride]

    def _render(self, job):
        recipe = dict(job["recipe"])
        if job.get("auto") or "auto_stretch" in recipe:
            pixels = self._pixels(job)
            parameters = calculate_stretch(job["statistics_pixels"]) if job.get("auto") else recipe["auto_stretch"]
            image = render_stretch(pixels, parameters)
            image.thumbnail((DISPLAY_EDGE, DISPLAY_EDGE), Image.Resampling.LANCZOS)
            return (image, {**recipe, "auto_stretch": parameters, **({"statistics": "stratified-random-1"} if job.get("auto") else {})})
        stretch = (recipe["stretch_low"], recipe["stretch_high"]) if "stretch_low" in recipe else None
        path, category = (job["path"], job["category"])
        if category == "fits":
            parameters = {**job["parameters"], "cfa_pattern": recipe.get("cfa_pattern") or job["parameters"].get("cfa_pattern")}
            image, computed = create_preview(path, job["hdu_index"], job["kind"], parameters, DISPLAY_EDGE, stretch)
            recipe.update(computed)
        elif category == "xisf":
            image, computed = read_xisf_preview(path, stretch, DISPLAY_EDGE)
            recipe.update(computed or {})
        elif category == "raw":
            image = read_raw_preview(path, DISPLAY_EDGE)
        elif category == "video":
            if path.suffix.lower() == ".ser" and stretch is None:
                _, original = first_video_frame(path, 100)
                stretch = (original["stretch_low"], original["stretch_high"])
                recipe.update(original)
            image, _ = first_video_frame(path, DISPLAY_EDGE, stretch)
        else:
            image, computed = read_raster_preview(path, stretch, DISPLAY_EDGE)
            recipe.update(computed or {})
        image.thumbnail((DISPLAY_EDGE, DISPLAY_EDGE), Image.Resampling.LANCZOS)
        return (image.convert("RGB"), recipe)

    def _generate(self, preview_id, job):
        created, replaced = ([], [])
        try:
            image, recipe = self._render(job)
            if job.get("context"):
                recipe = describe_recipe(job["context"], recipe)
            with self.database.write_session() as session:
                row = session.get(Preview, preview_id)
                asset = session.get(Asset, job["asset_id"])
                if row is None or asset is None or row.status != "generating":
                    return
                relative = Path(row.storage_path)
                if job.get("update_thumbnail"):
                    relative = relative.with_name(f"{PREVIEW_ALGORITHM_VERSION}-{job['hdu_index']}-display-{uuid4()}.jpg")
                    replaced.append(self.settings.data_dir / row.storage_path)
                    created.append(self.settings.data_dir / relative)
                final = self.settings.data_dir / relative
                final.parent.mkdir(parents=True, exist_ok=True)
                temporary = Path(str(final) + ".tmp")
                try:
                    image.convert("RGB").save(temporary, format="JPEG", quality=85, optimize=False)
                    os.replace(temporary, final)
                finally:
                    Path(temporary).unlink(missing_ok=True)
                row.storage_path = relative.as_posix()
                row.width, row.height = image.size
                row.display_parameters, row.status, row.error = (recipe, "available", None)
                if job.get("update_thumbnail"):
                    thumbnail = session.scalar(
                        select(Preview).where(
                            Preview.asset_id == job["asset_id"],
                            Preview.hdu_index == job["hdu_index"],
                            Preview.algorithm_version == PREVIEW_ALGORITHM_VERSION,
                            Preview.size == "thumbnail",
                        )
                    )
                    small = image.copy()
                    small.thumbnail((100, 100), Image.Resampling.LANCZOS)
                    if thumbnail is not None and thumbnail.storage_path:
                        replaced.append(self.settings.data_dir / thumbnail.storage_path)
                    small_relative = relative.with_name(relative.name.replace("-display-", "-thumbnail-"))
                    target = self.settings.data_dir / small_relative
                    created.append(target)
                    temporary = Path(str(target) + ".tmp")
                    try:
                        small.save(temporary, format="JPEG", quality=80, optimize=False)
                        os.replace(temporary, target)
                    finally:
                        temporary.unlink(missing_ok=True)
                    if thumbnail is None:
                        thumbnail = Preview(
                            id=str(uuid4()),
                            asset_id=job["asset_id"],
                            hdu_index=job["hdu_index"],
                            algorithm_version=PREVIEW_ALGORITHM_VERSION,
                            size="thumbnail",
                            width=0,
                            height=0,
                            storage_path="",
                            mime_type="image/jpeg",
                            display_parameters={},
                            status="available",
                            error=None,
                        )
                        session.add(thumbnail)
                    thumbnail.width, thumbnail.height = small.size
                    thumbnail.storage_path = small_relative.as_posix()
                    thumbnail.display_parameters, thumbnail.status, thumbnail.error = (recipe, "available", None)
        except Exception as exc:
            for path in created:
                path.unlink(missing_ok=True)
            logger.exception("display preview failed asset_id=%s", job["asset_id"])
            self._fail(
                preview_id,
                error_message(workspace_locale(self.settings.workspace), "", "preview_generation_diagnostic", {"diagnostic": str(exc)}),
            )
            return
        if (job.get("context") or {}).get("save_group"):
            save_group_recipe(self.database, job["context"], recipe)
        for path in replaced:
            path.unlink(missing_ok=True)
