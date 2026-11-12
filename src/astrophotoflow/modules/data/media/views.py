from __future__ import annotations
import hashlib
import json
import logging
import math
import mimetypes
import re
import time
from concurrent.futures import CancelledError
from contextlib import ExitStack
from io import BytesIO
from pathlib import Path
from threading import RLock
from uuid import uuid4
from astropy.io import fits
from PIL import Image
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import defer
from astrophotoflow.contracts.media import MediaHdu, MediaSelection, MediaState
from astrophotoflow.contracts.previews import PreviewIssue
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.core.localization import error_message, workspace_locale
from astrophotoflow.modules.data.assets.metadata import asset_parameters
from astrophotoflow.modules.data.assets.models import Asset, FitsHduMetadata
from astrophotoflow.modules.data.assets.storage import asset_path
from astrophotoflow.modules.data.datasets.models import DatasetMember
from astrophotoflow.modules.data.formats.numpy import numpy_arrays
from astrophotoflow.modules.data.formats.ser import ser_info
from astrophotoflow.modules.data.formats.source import PixelSource
from astrophotoflow.modules.data.formats.video import extract_frame, video_info
from astrophotoflow.modules.data.media.cache import MediaCache
from astrophotoflow.modules.data.media.leases import MediaLeases
from astrophotoflow.modules.data.media.models import Preview
from astrophotoflow.modules.data.media.playback import make_proxy
from astrophotoflow.modules.data.media.thumbnail_batches import THUMBNAIL_STANDALONE, group_algorithm
from astrophotoflow.modules.data.media.tiles import TileService
from astrophotoflow.modules.data.trash.models import LibraryEntryRemoval

ALGORITHM = "media-view-4"


class MediaViews:
    def __init__(self, database, settings, executor):
        self.database, self.settings, self.executor = (database, settings, executor)
        self.cache = MediaCache(settings.data_dir)
        self.lock = RLock()
        self.leases = MediaLeases(database, settings, self.cache, self.lock)
        self.tiles = TileService(self.cache, executor)
        self.consumers = {}
        self.interests = {}
        self.preparing = {}
        self.output_jobs = {}
        self.background_preparing = set()
        with database.write_session() as session:
            for row in session.scalars(
                select(Preview).where(Preview.storage_path.endswith("/manifest.json"), Preview.status == "generating")
            ).all():
                row.status, row.error = ("failed", error_message(workspace_locale(self.settings.workspace), "", "media_interrupted"))
        for folder in self.cache.folders():
            for part in folder.glob("*.part*"):
                part.unlink(missing_ok=True)
        self.cache.reconcile()

    def busy_blockers(self) -> list[str]:
        with self.lock:
            preparing = ["完整结果显示准备 " + key for key in self.preparing if key in self.output_jobs]
            using = ["完整结果显示读取 " + key for key in self.leases.active if key in self.output_jobs]
            return preparing + using

    def _source(self, session, asset_id):
        asset = session.get(Asset, asset_id, options=[defer(Asset.capture_snapshot)])
        if asset is None:
            raise not_found()
        if asset.availability != "available":
            raise ApiError(409, "SOURCE_UNAVAILABLE", "原件尚未就绪或已经变化。", message_key="the_original_is_not_ready_or_has_changed")
        members = func.json_each(LibraryEntryRemoval.member_asset_ids).table_valued("value")
        removal = session.scalar(
            select(LibraryEntryRemoval.entry_id)
            .where(
                LibraryEntryRemoval.cleanup_status != "trash",
                or_(
                    and_(LibraryEntryRemoval.entry_type == "asset", LibraryEntryRemoval.entry_id == asset.id),
                    and_(LibraryEntryRemoval.entry_type == "dataset", select(members.c.value).where(members.c.value == asset.id).exists()),
                ),
            )
            .limit(1)
        )
        if removal is not None:
            raise ApiError(
                409,
                "SOURCE_CLEANUP_ACTIVE",
                "原件正在清理，不能准备或读取查看缓存。",
                message_key="the_original_is_being_cleaned_up_viewer_cache_preparation_and_reads_are_blo",
            )
        path = asset_path(self.settings, asset)
        if asset.byte_size is not None and path.stat().st_size != asset.byte_size:
            raise ApiError(
                409,
                "SOURCE_CHANGED",
                "原件大小与固定版本不同，请先检查内容变化。",
                message_key="the_original_size_differs_from_the_fixed_version_check_content_changes_firs",
            )
        return asset, path

    def prepare(self, asset_id, selection):
        prefetch = selection.prefetch
        with self.lock:
            interest = (selection.consumer_id, selection.generation)
            if selection.consumer_id:
                observed = self.consumers.get(selection.consumer_id, (-1, 0))
                if selection.generation < observed[0]:
                    raise ApiError(
                        409, "STALE_VIEW", "已切换到更新的查看请求。", message_key="a_newer_viewer_request_has_replaced_this_request"
                    )
                self.consumers[selection.consumer_id] = (selection.generation, time.monotonic())
                active_consumers = {consumer for interests in self.interests.values() for consumer, _ in interests}
                self.consumers = {
                    consumer: value
                    for consumer, value in self.consumers.items()
                    if consumer in active_consumers or time.monotonic() - value[1] < 600
                }
                self._cancel_unused()
        with self.lock, self.database.read_session() as session:
            asset, path = self._source(session, asset_id)
            selected = session.scalar(
                select(FitsHduMetadata.hdu_index).where(FitsHduMetadata.asset_id == asset_id, FitsHduMetadata.is_selected.is_(True))
            )
            selection = selection.model_copy(deep=True, update={"consumer_id": None, "generation": 0, "prefetch": False})
            if selection.hdu_index is None and selected is not None:
                selection.hdu_index = selected
            category = (asset.scientific_metadata or {}).get("format")
            stamp = path.stat()
            previous = session.scalars(select(Preview).where(Preview.asset_id == asset_id, Preview.size.in_({"viewer", "playback"}))).all()
            if any((row.display_parameters.get("source_stamp") not in (None, [stamp.st_size, stamp.st_mtime_ns]) for row in previous)):
                raise ApiError(
                    409,
                    "SOURCE_CHANGED",
                    "原件自上次查看后已经变化，请先检查内容变化。",
                    message_key="the_original_has_changed_since_it_was_viewed_check_content_changes_first",
                )
            if category not in {"fits", "xisf", "image", "raw", "numpy", "video"}:
                raise ApiError(
                    422,
                    "MEDIA_UNSUPPORTED",
                    "当前素材不是受支持的可查看媒体。",
                    message_key="this_asset_is_not_a_supported_viewable_media_type",
                )
            if category == "video" and selection.media_time is not None and selection.playback_key:
                old = self._row(session, asset_id, selection.playback_key)
                folder = (self.settings.data_dir / old.storage_path).parent
                mapping = json.loads((folder / "frames.json").read_text(encoding="utf-8"))
                match = min(mapping, key=lambda frame: abs(frame["time"] - selection.media_time))
                if abs(match["time"] - selection.media_time) > 0.003:
                    raise ApiError(
                        422,
                        "FRAME_NOT_MATCHED",
                        "暂停帧时间戳没有对应的原始帧。",
                        message_key="no_original_frame_matches_the_paused_frame_timestamp",
                    )
                selection.media_time = None
                selection.frame_index = match["index"]
            playback = category == "video" and selection.media_time is None and (selection.frame_index is None)
            reference_id = asset_id
            if selection.dataset_id:
                group_id = str(selection.dataset_id)
                member = (
                    select(DatasetMember.id)
                    .where(DatasetMember.dataset_id == group_id, DatasetMember.asset_id == asset_id)
                    .correlate(None)
                    .exists()
                )
                reference_id = session.scalar(
                    select(DatasetMember.asset_id)
                    .where(DatasetMember.dataset_id == group_id, member)
                    .order_by(DatasetMember.position)
                    .limit(1)
                )
                if reference_id is None:
                    raise not_found()
            thumbnail = session.scalar(
                select(Preview)
                .where(
                    Preview.asset_id == reference_id,
                    Preview.algorithm_version == (group_algorithm(reference_id) if selection.dataset_id else THUMBNAIL_STANDALONE),
                    Preview.status == "available",
                )
                .order_by(Preview.created_at.desc())
                .limit(1)
            )
            recipe = (
                {"auto_stretch": thumbnail.display_parameters["auto_stretch"]}
                if thumbnail and thumbnail.display_parameters.get("auto_stretch")
                else {}
            )
            identity_selection = selection.model_dump(mode="json", exclude={"consumer_id", "generation"})
            identity = json.dumps(
                [ALGORITHM, asset_id, asset.content_hash, (asset_parameters(asset) or {}).get("cfa_pattern"), identity_selection, recipe],
                sort_keys=True,
            )
            key = hashlib.sha256(identity.encode()).hexdigest()[:40]
            if not prefetch:
                for old_key in self.background_preparing - {key}:
                    self.interests.pop(old_key, None)
                self.background_preparing.discard(key)
                self._cancel_unused()
                if hasattr(self.executor, "prioritize"):
                    self.executor.prioritize({asset_id})
            kind = "playback" if playback else "viewer"
            row = session.scalar(
                select(Preview).where(
                    Preview.asset_id == asset_id, Preview.size == kind, Preview.algorithm_version == ALGORITHM + ":" + key
                )
            )
            folder = self.settings.data_dir / "previews" / asset_id / "media" / key
            if (
                row
                and (not row.error)
                and (row.display_parameters["state"]["status"] == "available")
                and (folder / "manifest.json").is_file()
            ):
                return MediaState.model_validate(row.display_parameters["state"])
            if row and row.status == "generating":
                self.interests.setdefault(key, set()).add(interest)
                return MediaState.model_validate(row.display_parameters["state"])
            state = MediaState(key=key, status="generating", phase="queued", kind="video" if playback else "image", selection=selection)
            if row is None:
                row = Preview(
                    id=str(uuid4()),
                    asset_id=asset_id,
                    hdu_index=selection.hdu_index or 0,
                    size=kind,
                    algorithm_version=ALGORITHM + ":" + key,
                    width=0,
                    height=0,
                    mime_type="application/json",
                    storage_path=(folder / "manifest.json").relative_to(self.settings.data_dir).as_posix(),
                    display_parameters={"state": state.model_dump(mode="json"), "source_stamp": [stamp.st_size, stamp.st_mtime_ns]},
                    status="generating",
                )
            else:
                row.status, row.error = ("generating", None)
                row.display_parameters = {"state": state.model_dump(mode="json"), "source_stamp": [stamp.st_size, stamp.st_mtime_ns]}
            job = {
                "id": row.id,
                "key": key,
                "asset_id": asset_id,
                "path": path,
                "folder": folder,
                "category": category,
                "reference_asset_id": reference_id,
                "selection": selection,
                "recipe": recipe,
                "parameters": {
                    **dict(asset_parameters(asset) or {}),
                    "colour_layout": (asset.scientific_metadata or {}).get("colour_layout"),
                },
                "stamp": (stamp.st_size, stamp.st_mtime_ns),
                "playback": playback,
            }
            self.interests[key] = {interest}
            with self.database.write_session() as write:
                self._source(write, asset_id)
                stored = write.get(Preview, row.id)
                if stored is None:
                    write.add(row)
                else:
                    stored.status, stored.error = ("generating", None)
                    stored.display_parameters = row.display_parameters
        with self.lock:
            try:
                if prefetch and hasattr(self.executor, "submit_background"):
                    self.background_preparing.add(key)
                    future = self.executor.submit_background(asset_id, self._prepare, job, priority=20)
                else:
                    future = self.executor.submit(self._prepare, job)
                self.preparing[key] = future

                def complete(completed):
                    with self.lock:
                        if self.preparing.get(key) is not completed:
                            return
                        if completed.cancelled():
                            self._fail(job, error_message(workspace_locale(self.settings.workspace), "", "media_not_watched"))
                        self.preparing.pop(key, None)
                        self.background_preparing.discard(key)
                        self.interests.pop(key, None)

                future.add_done_callback(complete)
            except RuntimeError:
                self.interests.pop(key, None)
                self._fail(job, error_message(workspace_locale(self.settings.workspace), "", "media_executor_closing"))
        return state

    def _row(self, session, asset_id, key):
        row = session.scalar(
            select(Preview).where(
                Preview.asset_id == asset_id, Preview.algorithm_version == ALGORITHM + ":" + key, Preview.size.in_({"viewer", "playback"})
            )
        )
        if row is None:
            raise not_found()
        return row

    def status(self, asset_id, key):
        with self.database.read_session() as session:
            self._source(session, asset_id)
            row = self._row(session, asset_id, key)
            state = MediaState.model_validate(row.display_parameters["state"])
            if row.error:
                state.status, state.error = ("failed", PreviewIssue(code="MEDIA_FAILED", message=row.error))
                state.phase = None
            return state

    def cancel_consumer(self, consumer_id):
        with self.lock:
            self.consumers[consumer_id] = (2**63 - 1, time.monotonic())
            self._cancel_unused()

    def _wanted(self, key):
        return any(
            (not consumer or self.consumers.get(consumer, (-1, 0))[0] == generation for consumer, generation in self.interests.get(key, ()))
        )

    def _cancel_unused(self):
        for key, future in list(self.preparing.items()):
            if not self._wanted(key):
                future.cancel()

    def _checkpoint(self, key):
        with self.lock:
            if not self._wanted(key):
                raise CancelledError(error_message(workspace_locale(self.settings.workspace), "", "media_not_watched"))

    def _fail(self, job, message, state=None):
        if job.get("output_source"):
            with self.lock:
                state = state or MediaState.model_validate(job["state"])
                state.status, state.phase = ("failed", None)
                state.error = PreviewIssue(code="MEDIA_FAILED", message=message)
                job["state"] = state.model_dump(mode="json")
            return
        with self.database.write_session() as session:
            row = session.get(Preview, job["id"])
            if row:
                row.status, row.error = ("failed", message)
                state = state or MediaState.model_validate(row.display_parameters["state"])
                state.status, state.phase = ("failed", None)
                row.display_parameters = {**row.display_parameters, "state": state.model_dump(mode="json")}

    def _prepare(self, job):
        folder = job["folder"]
        state = None
        try:
            self._checkpoint(job["key"])
            if job.get("output_source"):
                with self.lock:
                    state = MediaState.model_validate(job["state"])
                    state.phase = "preparing"
                    job["state"] = state.model_dump(mode="json")
            else:
                with self.database.write_session() as session:
                    row = session.get(Preview, job["id"])
                    state = MediaState.model_validate(row.display_parameters["state"])
                    state.phase = "preparing"
                    row.display_parameters = {**row.display_parameters, "state": state.model_dump(mode="json")}
            with self.cache.hold(folder):
                folder.mkdir(parents=True, exist_ok=True)
                state = MediaState(key=job["key"], status="available", selection=job["selection"])
                path, category = (job["path"], job["category"])
                if job["selection"].display_range is not None:
                    if job["playback"]:
                        raise ValueError("请先暂停并检查原始帧，再调整该帧的显示阈值。")
                    low, high = job["selection"].display_range
                    job["recipe"] = {"stretch_low": low, "stretch_high": high}
                if category == "fits":
                    from astrophotoflow.modules.data.formats.layout import apply_colour_layout, fits_image_kind

                    with fits.open(path, memmap=False, lazy_load_hdus=True) as file:
                        for index, hdu in enumerate(file):
                            apply_colour_layout(hdu, job["parameters"].get("colour_layout"))
                            state.hdus.append(
                                MediaHdu(
                                    index=index,
                                    name=hdu.header.get("EXTNAME"),
                                    shape=list(getattr(hdu, "shape", None) or []),
                                    kind=fits_image_kind(hdu, job["parameters"].get("cfa_pattern")),
                                )
                            )
                    if job.get("output_source"):
                        selection = job["selection"]
                        state.frame_count = job["parameters"].get("frame_count")
                        if selection.hdu_index is None and selection.frame_index is not None:
                            frames = [hdu.index for hdu in state.hdus if hdu.kind is not None]
                            if selection.frame_index >= len(frames):
                                raise ValueError("The selected FITS frame is unavailable.")
                            selection.hdu_index = frames[selection.frame_index]
                if category == "numpy":
                    state.arrays = numpy_arrays(path)
                    if not state.arrays:
                        raise ValueError("文件中没有可查看的数组。")
                    if job["selection"].array_key is None:
                        if len(state.arrays) > 1:
                            state.needs_selection = True
                        else:
                            job["selection"].array_key = state.arrays[0].key
                    chosen = next((array for array in state.arrays if array.key == job["selection"].array_key), None)
                    if chosen is not None and (not chosen.numeric):
                        raise ValueError("所选数组不是数值图像，不能显示。")
                    if chosen is not None and len(chosen.shape) > 2 and (job["selection"].x_axis is None):
                        state.needs_selection = True
                    if not state.needs_selection and chosen is None:
                        raise ValueError("没有找到所选数组。")
                if job["playback"]:
                    state.kind, state.proxy = ("video", job["selection"].proxy or path.suffix.lower() == ".ser")
                    if state.proxy:
                        if path.suffix.lower() == ".ser" and (not job["recipe"]):
                            source = PixelSource(
                                path,
                                category,
                                MediaSelection(frame_index=0),
                                job["parameters"],
                                folder,
                                self.cache.reserve,
                                record=self.cache.record,
                            )
                            job["recipe"] = {"auto_stretch": source.stretch()}
                        _, state.note = make_proxy(path, folder, self.cache, job["parameters"], job["recipe"])
                    state.mime_type = "video/mp4" if state.proxy else mimetypes.guess_type(path)[0] or "video/mp4"
                    if path.suffix.lower() == ".ser":
                        info = ser_info(path)
                        state.width, state.height, state.frame_count = (info.width, info.height, info.count)
                    else:
                        state.width, state.height, state.duration = video_info(path)
                    state.video_url = "video"
                elif not state.needs_selection:
                    if category == "video" and path.suffix.lower() != ".ser":
                        frame, _, _, timestamp = extract_frame(path, job["selection"], folder, self.cache.reserve)
                        self.cache.record(frame)
                        job["pixel_path"], job["pixel_category"] = (str(frame), "frame")
                        state.media_time = timestamp
                    source = self.tiles.pixel_source(job, lambda: self._checkpoint(job["key"]))
                    state.width, state.height = source.dimensions()
                    edge = job["selection"].preview_max_edge
                    step = max(1, math.ceil(max(state.width, state.height) / (edge or 4096)))
                    if source.cfa in {"RGGB", "BGGR", "GRBG", "GBRG"} and step % 2 == 0:
                        step += 1
                    pixels = source.read((0, 0, state.width, state.height), step)
                    state.channels = ["composite", "red", "green", "blue"] if pixels.ndim == 3 and pixels.shape[-1] == 3 else ["composite"]
                    if path.suffix.lower() == ".ser":
                        state.frame_count = ser_info(path).count
                    balance = job["selection"].display_balance
                    if job["selection"].display_range is None:
                        if balance is not None and pixels.ndim == 3:
                            if job["recipe"].get("direct") or not source.linear:
                                job["recipe"] = {
                                    **job["recipe"],
                                    "display_white_balance": source.stretch()["white_balance"] if balance == "auto" else [1, 1, 1],
                                }
                            else:
                                job["recipe"] = {"auto_stretch": source.stretch(balance_rgb=balance == "auto")}
                        elif (
                            source.linear
                            and pixels.ndim == 3
                            and ("stretch_low" in job["recipe"])
                            and ("auto_stretch" not in job["recipe"])
                        ):
                            job["recipe"] = {}
                    if source.linear and (
                        not ("auto_stretch" in job["recipe"] or "stretch_low" in job["recipe"] or job["recipe"].get("direct"))
                    ):
                        if job.get("output_source"):
                            job["recipe"] = {"auto_stretch": source.stretch()}
                        else:
                            job["recipe"] = {"auto_stretch": self._reference_stretch(job, source)}
                    if source.cfa and source.cfa not in {"MONO", "RGGB", "BGGR", "GRBG", "GBRG"}:
                        state.note = "此CFA排列以原尺寸传感器灰度马赛克查看。"
                    self._checkpoint(job["key"])
                    if edge is None:
                        self.cache.reserve(state.width * state.height * 12)
                        pixels = source.read((0, 0, state.width, state.height))
                    overview = source.render(pixels, job["recipe"])
                    self._checkpoint(job["key"])
                    if edge is not None:
                        overview.thumbnail((edge, edge), Image.Resampling.LANCZOS)
                    buffer = BytesIO()
                    overview.save(buffer, format="JPEG", quality=90)
                    self.cache.write(folder / "overview.jpg", buffer.getvalue())
                    state.max_level = math.ceil(math.log2(max(state.width, state.height)))
                    state.overview_url, state.tile_url = ("overview", "tiles/{level}/{x}/{y}")
                    state.frame_index = job["selection"].frame_index
                state.selection = job["selection"]
                state.display_recipe = dict(job["recipe"])
                if job["recipe"].get("direct") and (not job["playback"]) and (not state.needs_selection):
                    state.display_recipe["display_range"] = [0, source.direct_max]
                self._checkpoint(job["key"])
                stamp = path.stat()
                if (stamp.st_size, stamp.st_mtime_ns) != job["stamp"]:
                    raise ValueError("原件在查看准备期间变化，未发布缓存。")
                job["state"] = state.model_dump(mode="json")
                saved = {
                    key: str(value)
                    if isinstance(value, Path)
                    else value.model_dump(mode="json")
                    if isinstance(value, MediaSelection)
                    else value
                    for key, value in job.items()
                }
                self.cache.write(folder / "manifest.json", json.dumps(saved, ensure_ascii=False).encode())
                if not job.get("output_source"):
                    with self.database.write_session() as session:
                        self._source(session, job["asset_id"])
                        row = session.get(Preview, job["id"])
                        if row is None or row.status != "generating":
                            raise ValueError("查看缓存已失去生成所有权。")
                        row.width, row.height, row.status = (state.width, state.height, "available")
                        row.display_parameters = {
                            **job["recipe"],
                            "source_stamp": list(job["stamp"]),
                            "state": state.model_dump(mode="json"),
                        }
        except Exception as exc:
            logging.getLogger(__name__).exception("Media preparation failed key=%s", job["key"])
            self._fail(
                job,
                error_message(workspace_locale(self.settings.workspace), "", "media_failure_diagnostic", {"diagnostic": str(exc)}),
                state,
            )

    def _reference_stretch(self, job, source):
        reference_id = job["reference_asset_id"]
        if reference_id == job["asset_id"]:
            return source.stretch()
        with self.database.read_session() as session:
            asset, path = self._source(session, reference_id)
            metadata = asset.scientific_metadata or {}
            hdu = session.scalar(
                select(FitsHduMetadata.hdu_index).where(FitsHduMetadata.asset_id == reference_id, FitsHduMetadata.is_selected.is_(True))
            )
            parameters = {**dict((asset.capture_snapshot or {}).get("parameters") or {}), "colour_layout": metadata.get("colour_layout")}
            category = metadata.get("format")
        folder = job["folder"] / ("reference-" + reference_id)
        folder.mkdir(parents=True, exist_ok=True)
        reference = PixelSource(
            path,
            category,
            MediaSelection(hdu_index=hdu),
            parameters,
            folder,
            self.cache.reserve,
            lambda: self._checkpoint(job["key"]),
            self.cache.record,
        )
        reference.dimensions()
        return reference.stretch()

    def acquire(self, asset_id, key):
        with ExitStack() as guard:
            with self.lock, self.database.write_session() as session:
                _, path = self._source(session, asset_id)
                row = self._row(session, asset_id, key)
                folder = (self.settings.data_dir / row.storage_path).parent
                if row.error:
                    raise ApiError(
                        409,
                        "MEDIA_NOT_READY",
                        row.error,
                        message_key="media_reopen_required",
                        fields=[{"path": "diagnostic", "message": row.error}],
                    )
                job, release = self.leases.acquire(path, folder, preview=row)
                guard.callback(release)
            guard.pop_all()
            return (job, release)

    def prepare_output(self, checked, selection, *, direct):
        path = checked.path
        stamp = path.stat()
        if checked.format not in {"fits", "xisf", "image", "raw", "numpy", "video"}:
            raise ApiError(
                422,
                "MEDIA_UNSUPPORTED",
                "该输出不是可查看的科学图像或视频。",
                message_key="this_output_is_not_a_viewable_scientific_image_or_video",
            )
        if selection.hdu_index is None and (checked.format != "fits" or selection.frame_index is None):
            selection = selection.model_copy(update={"hdu_index": (checked.scientific_metadata or {}).get("selected_hdu")})
        if checked.format == "video" and selection.media_time is not None and selection.playback_key:
            playback_key = selection.playback_key
            if not re.fullmatch("[a-f0-9]{40}", playback_key):
                raise not_found()
            previous = self.settings.data_dir / "previews" / "run-outputs" / "media" / playback_key
            job = json.loads((previous / "manifest.json").read_text(encoding="utf-8"))
            if Path(job["path"]).resolve() != path.resolve() or job["stamp"] != [stamp.st_size, stamp.st_mtime_ns]:
                raise ApiError(
                    409,
                    "SOURCE_CHANGED",
                    "视频播放缓存不属于当前完整结果。",
                    message_key="the_video_playback_cache_does_not_belong_to_the_current_complete_result",
                )
            mapping = json.loads((previous / "frames.json").read_text(encoding="utf-8"))
            match = min(mapping, key=lambda frame: abs(frame["time"] - selection.media_time))
            if abs(match["time"] - selection.media_time) > 0.003:
                raise ApiError(
                    422,
                    "FRAME_NOT_MATCHED",
                    "暂停帧时间戳没有对应的原始帧。",
                    message_key="no_original_frame_matches_the_paused_frame_timestamp",
                )
            selection = selection.model_copy(update={"media_time": None, "frame_index": match["index"]})
        interest = (selection.consumer_id, selection.generation)
        identity_selection = selection.model_dump(mode="json", exclude={"consumer_id", "generation"})
        key = hashlib.sha256(
            json.dumps(
                [
                    ALGORITHM,
                    "checked-output",
                    checked.content_hash,
                    str(path),
                    (checked.scientific_metadata or {}).get("colour_layout"),
                    identity_selection,
                    direct,
                ],
                sort_keys=True,
            ).encode()
        ).hexdigest()[:40]
        folder = self.settings.data_dir / "previews" / "run-outputs" / "media" / key
        with self.lock:
            if selection.consumer_id:
                old = self.consumers.get(selection.consumer_id, (-1, 0))
                if selection.generation < old[0]:
                    raise ApiError(
                        409, "STALE_VIEW", "已切换到更新的查看请求。", message_key="a_newer_viewer_request_has_replaced_this_request"
                    )
                self.consumers[selection.consumer_id] = (selection.generation, time.monotonic())
                self._cancel_unused()
            self.interests.setdefault(key, set()).add(interest)
            previous = self.output_jobs.get(key)
            if previous and previous["state"]["status"] == "generating":
                return MediaState.model_validate(previous["state"])
            manifest = folder / "manifest.json"
            if manifest.is_file():
                previous = json.loads(manifest.read_text(encoding="utf-8"))
                if previous["stamp"] != [stamp.st_size, stamp.st_mtime_ns]:
                    raise ApiError(
                        409,
                        "SOURCE_CHANGED",
                        "完整结果在查看准备后发生变化。",
                        message_key="the_complete_result_changed_after_viewer_preparation",
                    )
                self.output_jobs[key] = previous
                return MediaState.model_validate(previous["state"])
            state = MediaState(key=key, status="generating", phase="queued", selection=selection)
            playback = checked.format == "video" and selection.frame_index is None and (selection.media_time is None)
            metadata = checked.scientific_metadata or {}
            job = {
                "key": key,
                "path": path,
                "folder": folder,
                "category": checked.format,
                "selection": selection.model_copy(update={"consumer_id": None, "generation": 0}),
                "recipe": {"direct": True} if direct else {},
                "parameters": {"colour_layout": metadata.get("colour_layout"), "frame_count": metadata.get("frame_count")},
                "stamp": (stamp.st_size, stamp.st_mtime_ns),
                "playback": playback,
                "output_source": True,
                "state": state.model_dump(mode="json"),
            }
            self.output_jobs[key] = job
            future = self.executor.submit(self._prepare, job)
            self.preparing[key] = future

            def complete(completed):
                with self.lock:
                    if completed.cancelled():
                        self._fail(job, error_message(workspace_locale(self.settings.workspace), "", "media_not_watched"))
                    self.preparing.pop(key, None)
                    self.interests.pop(key, None)

            future.add_done_callback(complete)
        return state

    def output_status(self, checked, key):
        with self.lock:
            job = self.output_jobs.get(key)
            if job is None:
                raise ApiError(
                    409, "MEDIA_NOT_READY", "显示缓存已失效，请重新打开查看器。", message_key="the_display_cache_is_stale_reopen_the_viewer"
                )
            stamp = checked.path.stat()
            if Path(job["path"]).resolve() != checked.path.resolve() or tuple(job["stamp"]) != (stamp.st_size, stamp.st_mtime_ns):
                raise ApiError(
                    409,
                    "SOURCE_CHANGED",
                    "显示状态不属于该完整结果。",
                    message_key="the_display_state_does_not_belong_to_this_complete_result",
                )
            return MediaState.model_validate(job["state"])

    def thumbnail_output(self, checked, *, direct):
        metadata = checked.scientific_metadata or {}
        identity = json.dumps(
            [ALGORITHM, "output-thumbnail", checked.content_hash, metadata.get("selected_hdu"), metadata.get("colour_layout"), direct],
            sort_keys=True,
        )
        key = hashlib.sha256(identity.encode()).hexdigest()[:40]
        folder = self.settings.data_dir / "previews" / "run-outputs" / "media" / key
        hold = self.cache.hold(folder)
        hold.__enter__()
        try:
            path = folder / "thumbnail.jpg"
            if not path.is_file():
                from astrophotoflow.modules.data.science.outputs import render_output_preview

                self.cache.reserve(1024 * 1024 * 3)
                folder.mkdir(parents=True, exist_ok=True)
                render_output_preview(checked, path, max_edge=1024, auto_stretch=not direct)
                self.cache.record(path)
            return (path, lambda: hold.__exit__(None, None, None))
        except Exception:
            hold.__exit__(None, None, None)
            raise

    def acquire_output(self, checked, key):
        return self.leases.acquire_output(checked, key)
