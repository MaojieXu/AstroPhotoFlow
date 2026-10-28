"""Lazy display JPEG generation on the service's existing preview executor."""
from __future__ import annotations
from astrophotoflow.contracts.previews import DisplayPreviewState, PreviewIssue

import logging
import os
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, Response
import numpy as np
from PIL import Image, ImageOps
from sqlalchemy import select

from astrophotoflow.core import http as deps
from astrophotoflow.contracts.previews import AutoStretch
from astrophotoflow.modules.data.auto_stretch import calculate_stretch, render_stretch
from astrophotoflow.modules.data.common import _asset_version_scope
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.modules.data.files import find_root, resolve_relative
from astrophotoflow.modules.data.fits_preview import PREVIEW_ALGORITHM_VERSION, create_preview, read_preview_pixels
from astrophotoflow.modules.data.ingestion import _ordinary_image, _raw_image, _xisf_image, _xisf_pixels
from astrophotoflow.modules.data.models import AssetVersion, FitsHduMetadata, LibraryEntryRemoval, Preview, ProjectAssetReference
from astrophotoflow.contracts.common import StrictModel
from astrophotoflow.modules.data.video_preview import first_video_frame

logger = logging.getLogger("astrophotoflow.service.previews")
router = APIRouter(prefix="/api/v1", responses=deps.ERROR_RESPONSES)
DISPLAY_EDGE = 1080






def owned_preview_locations(preview, settings) -> list[str]:
    if not preview.storage_path:
        return []
    locations = [preview.storage_path]
    temporary = preview.storage_path + ".tmp"
    if preview.size == "display" and (settings.data_dir / temporary).is_file():
        locations.append(temporary)
    return locations


def assert_no_preview_jobs(session, version_ids) -> None:
    if session.scalar(select(Preview.id).where(
        Preview.asset_version_id.in_(version_ids), Preview.status == "generating",
    ).limit(1)):
        raise ApiError(409, "PREVIEW_ACTIVE", "大图预览仍在生成，请完成后重新预览清理范围。")


def _issue(status, code, message):
    return {"status": status, "error": {"code": code, "message": message}}


class DisplayPreviews:
    def __init__(self, database, settings, executor):
        self.database, self.settings, self.executor = database, settings, executor
        with database.write_session() as session:
            for row in session.scalars(select(Preview).where(Preview.size == "display", Preview.status == "generating")).all():
                row.status, row.error = "failed", "服务中断，大图预览尚未完成，请重试。"

    def _resolve(self, session, version_id, *, refresh=False):
        version = session.get(AssetVersion, version_id)
        if version is None:
            raise not_found()
        category = (version.scientific_metadata or {}).get("format")
        hdu = session.scalar(select(FitsHduMetadata).where(
            FitsHduMetadata.asset_version_id == version_id, FitsHduMetadata.is_selected.is_(True)))
        index = hdu.hdu_index if hdu else 0
        key = (Preview.asset_version_id == version_id, Preview.hdu_index == index,
               Preview.algorithm_version == PREVIEW_ALGORITHM_VERSION)
        display = session.scalar(select(Preview).where(*key, Preview.size == "display"))
        if display is not None:
            if not refresh and display.status == "available" and (self.settings.data_dir / display.storage_path).is_file():
                return display, None, {"status": "available", "width": display.width, "height": display.height, "error": None}
            if display.status == "generating":
                return display, None, {"status": "generating", "error": None}
        if category not in {"fits", "xisf", "image", "raw", "video"} or category == "fits" and (hdu is None or hdu.supported_kind in {"xtrans", "quad_bayer"}):
            return display, None, _issue("unsupported", "PREVIEW_UNSUPPORTED", "此图像布局暂不支持大图预览。")
        if version.availability != "available":
            return display, None, _issue("not_ready", "SOURCE_NOT_READY", "原件托管或散列尚未完成，请稍后重试。")
        if category in {"fits", "xisf"} and (version.scientific_metadata or {}).get("metadata_status") == "failed":
            return display, None, _issue("not_ready", "METADATA_NOT_READY", "文件元数据尚未解析完成，请重试导入后再生成大图。")
        # Removed originals may be in a confirmed cleanup transaction. The same
        # BEGIN IMMEDIATE lock serializes job ownership with permanent deletion.
        removals = session.scalars(select(LibraryEntryRemoval)).all()
        if any(row.cleanup_status != "trash" and (
               row.entry_type == "asset" and row.entry_id == version.asset_id or
               row.entry_type == "dataset" and version.asset_id in (row.member_asset_ids or [])) for row in removals):
            return display, None, _issue("not_ready", "SOURCE_CLEANUP_ACTIVE", "原件正在清理，暂不能生成大图。")
        thumbnail = session.scalar(select(Preview).where(*key, Preview.size == "thumbnail", Preview.status == "available"))
        if thumbnail is None:
            return display, None, _issue("not_ready", "RECIPE_NOT_READY", "缩略图及其显示参数尚未就绪，请稍后重试。")
        recipe = dict(thumbnail.display_parameters or {})
        if category in {"fits", "xisf"} and not {"stretch_low", "stretch_high"} <= recipe.keys():
            return display, None, _issue("not_ready", "STRETCH_NOT_READY", "固定拉伸参数尚未就绪，请稍后重试。")
        if version.storage_mode == "managed":
            path = self.settings.data_dir / version.storage_location
        else:
            _, root_id, relative = version.storage_location.split("/", 2)
            _, root = find_root(self.settings, root_id)
            path = resolve_relative(root, relative)
        job = {"version_id": version_id, "hdu_index": index, "kind": hdu.supported_kind if hdu else None,
               "category": category, "path": path, "recipe": recipe,
               "parameters": dict(version.capture_snapshot or {})}
        if display is not None:
            return display, job, _issue("failed", "PREVIEW_FAILED", display.error or "大图缓存不可用，请重试。")
        return None, job, _issue("not_ready", "DISPLAY_NOT_GENERATED", "点击生成大图预览。")

    def status(self, version_id):
        with self.database.read_session() as session:
            row, _, state = self._resolve(session, version_id)
            stretch = (row.display_parameters or {}).get("auto_stretch") if row and state["status"] == "available" else None
        return {"asset_version_id": UUID(version_id), "size": "display", **state,
                "stretch": AutoStretch(**stretch) if stretch is not None else None}

    def schedule(self, version_id, *, auto=False):
        with self.database.write_session() as session:
            row, job, state = self._resolve(session, version_id)
            if auto and state["status"] == "available" and "auto_stretch" not in (row.display_parameters or {}):
                row, job, state = self._resolve(session, version_id, refresh=True)
            if job is None:
                return {"asset_version_id": UUID(version_id), "size": "display", **state,
                        "stretch": (row.display_parameters or {}).get("auto_stretch")
                        if row and state["status"] == "available" else None}
            if auto and "auto_stretch" not in job["recipe"]:
                job["auto"] = True
                job["update_thumbnail"] = True
            if row is None:
                row = Preview(id=str(uuid4()), asset_version_id=version_id, hdu_index=job["hdu_index"], size="display",
                              algorithm_version=PREVIEW_ALGORITHM_VERSION, width=0, height=0, storage_path="",
                              mime_type="image/jpeg", display_parameters=job["recipe"], status="generating", error=None)
                session.add(row)
            row.status, row.error = "generating", None
            if not row.storage_path:
                row.storage_path = (Path("previews") / version_id / f"{PREVIEW_ALGORITHM_VERSION}-{job['hdu_index']}-display.jpg").as_posix()
            preview_id = row.id
        try:
            self.executor.submit(self._generate, preview_id, job)
        except Exception:
            logger.exception("display preview could not be queued version_id=%s", version_id)
            self._fail(preview_id, "无法排队生成大图，请重试。")
        return self.status(version_id)

    def _fail(self, preview_id, message):
        with self.database.write_session() as session:
            row = session.get(Preview, preview_id)
            if row is not None:
                row.status, row.error = "failed", message

    def _pixels(self, job):
        path, category = job["path"], job["category"]
        if category == "fits":
            parameters = {**job["parameters"], "cfa_pattern": job["recipe"].get("cfa_pattern") or job["parameters"].get("cfa_pattern")}
            pixels, _ = read_preview_pixels(path, job["hdu_index"], job["kind"], parameters, DISPLAY_EDGE)
        elif category == "xisf":
            pixels = _xisf_pixels(path)
        elif category == "raw":
            pixels = np.asarray(_raw_image(path, DISPLAY_EDGE))
        elif category == "video":
            pixels = np.asarray(first_video_frame(path, DISPLAY_EDGE)[0])
        else:
            with Image.open(path) as source:
                image = ImageOps.exif_transpose(source)
                if image.mode not in {"L", "I;16", "I;16B", "I;16L", "I", "F"}:
                    image = image.convert("RGB")
                pixels = np.array(image)
        stride = max(1, (max(pixels.shape[:2]) + DISPLAY_EDGE - 1) // DISPLAY_EDGE)
        return pixels[::stride, ::stride]

    def _render(self, job):
        recipe = dict(job["recipe"])
        if job.get("auto") or "auto_stretch" in recipe:
            pixels = self._pixels(job)
            parameters = calculate_stretch(pixels) if job.get("auto") else recipe["auto_stretch"]
            image = render_stretch(pixels, parameters)
            image.thumbnail((DISPLAY_EDGE, DISPLAY_EDGE), Image.Resampling.LANCZOS)
            return image, {**recipe, "auto_stretch": parameters}
        stretch = (recipe["stretch_low"], recipe["stretch_high"]) if "stretch_low" in recipe else None
        path, category = job["path"], job["category"]
        if category == "fits":
            parameters = {**job["parameters"], "cfa_pattern": recipe.get("cfa_pattern") or job["parameters"].get("cfa_pattern")}
            image, computed = create_preview(path, job["hdu_index"], job["kind"], parameters, DISPLAY_EDGE, stretch)
            recipe.update(computed)
        elif category == "xisf":
            image, _ = _xisf_image(path, stretch)
        elif category == "raw":
            image = _raw_image(path, DISPLAY_EDGE)
        elif category == "video":
            if path.suffix.lower() == ".ser" and stretch is None:
                _, original = first_video_frame(path, 100)
                stretch = original["stretch_low"], original["stretch_high"]
                recipe.update(original)
            image, _ = first_video_frame(path, DISPLAY_EDGE, stretch)
        else:
            image, _ = _ordinary_image(path, stretch)
        image.thumbnail((DISPLAY_EDGE, DISPLAY_EDGE), Image.Resampling.LANCZOS)
        return image.convert("RGB"), recipe

    def _generate(self, preview_id, job):
        created, replaced = [], []
        try:
            image, recipe = self._render(job)
            # The DB write lock covers ownership verification, file publication
            # and row availability, so cleanup cannot unlink/delete between them.
            with self.database.write_session() as session:
                row = session.get(Preview, preview_id)
                version = session.get(AssetVersion, job["version_id"])
                if row is None or version is None or row.status != "generating":
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
                row.display_parameters, row.status, row.error = recipe, "available", None
                if job.get("update_thumbnail"):
                    thumbnail = session.scalar(select(Preview).where(
                        Preview.asset_version_id == job["version_id"], Preview.hdu_index == job["hdu_index"],
                        Preview.algorithm_version == PREVIEW_ALGORITHM_VERSION, Preview.size == "thumbnail"))
                    small = image.copy()
                    small.thumbnail((100, 100), Image.Resampling.LANCZOS)
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
                    thumbnail.width, thumbnail.height = small.size
                    thumbnail.storage_path = small_relative.as_posix()
                    thumbnail.display_parameters = recipe
        except Exception as exc:
            for path in created:
                path.unlink(missing_ok=True)
            logger.exception("display preview failed version_id=%s", job["version_id"])
            self._fail(preview_id, f"大图预览生成失败：{exc}")
            return
        for path in replaced:
            path.unlink(missing_ok=True)


def _library_version(session, asset_id, version_id):
    asset, version = _asset_version_scope(session, None, version_id)
    if asset.id != str(asset_id):
        raise not_found()
    return version.id


def _project_version(session, project_id, reference_id):
    reference = session.get(ProjectAssetReference, str(reference_id))
    if reference is None or reference.project_id != str(project_id):
        raise not_found()
    _asset_version_scope(session, project_id, UUID(reference.asset_version_id))
    return reference.asset_version_id


@router.post("/library/assets/{asset_id}/versions/{version_id}/previews/display", response_model=DisplayPreviewState,
             responses={202: {"model": DisplayPreviewState}}, dependencies=[Depends(deps.authenticate)])
def request_display(asset_id: UUID, version_id: UUID, request: Request, response: Response, admission: deps.TaskAdmission, session: deps.ReadSession):
    state = request.app.state.display_previews.schedule(_library_version(session, asset_id, version_id))
    response.status_code = 202 if state["status"] == "generating" else 200
    return state


@router.get("/library/assets/{asset_id}/versions/{version_id}/previews/display/status", response_model=DisplayPreviewState,
            dependencies=[Depends(deps.authenticate)])
def display_status(asset_id: UUID, version_id: UUID, request: Request, session: deps.ReadSession):
    return request.app.state.display_previews.status(_library_version(session, asset_id, version_id))


@router.post("/library/assets/{asset_id}/versions/{version_id}/previews/display/auto-stretch", response_model=DisplayPreviewState,
            responses={202: {"model": DisplayPreviewState}}, dependencies=[Depends(deps.authenticate)])
def auto_stretch(asset_id: UUID, version_id: UUID, request: Request, response: Response, admission: deps.TaskAdmission, session: deps.ReadSession):
    state = request.app.state.display_previews.schedule(_library_version(session, asset_id, version_id), auto=True)
    response.status_code = 202 if state["status"] == "generating" else 200
    return state


@router.post("/projects/{project_id}/asset-references/{reference_id}/previews/display", response_model=DisplayPreviewState,
             responses={202: {"model": DisplayPreviewState}}, dependencies=[Depends(deps.authenticate)])
def request_project_display(project_id: UUID, reference_id: UUID, request: Request, response: Response, admission: deps.TaskAdmission, session: deps.ReadSession):
    state = request.app.state.display_previews.schedule(_project_version(session, project_id, reference_id))
    response.status_code = 202 if state["status"] == "generating" else 200
    return state


@router.get("/projects/{project_id}/asset-references/{reference_id}/previews/display/status", response_model=DisplayPreviewState,
            dependencies=[Depends(deps.authenticate)])
def project_display_status(project_id: UUID, reference_id: UUID, request: Request, session: deps.ReadSession):
    return request.app.state.display_previews.status(_project_version(session, project_id, reference_id))


@router.post("/projects/{project_id}/asset-references/{reference_id}/previews/display/auto-stretch", response_model=DisplayPreviewState,
            responses={202: {"model": DisplayPreviewState}}, dependencies=[Depends(deps.authenticate)])
def project_auto_stretch(project_id: UUID, reference_id: UUID, request: Request, response: Response, admission: deps.TaskAdmission, session: deps.ReadSession):
    state = request.app.state.display_previews.schedule(_project_version(session, project_id, reference_id), auto=True)
    response.status_code = 202 if state["status"] == "generating" else 200
    return state
