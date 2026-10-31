from __future__ import annotations
from astrophotoflow.core.localization import error_message, workspace_locale

from concurrent.futures import CancelledError, Future
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from threading import Event, RLock
from uuid import UUID, uuid4
import asyncio
import hashlib
import json
import math
import mimetypes
import re
import time

import numpy as np
from astropy.io import fits
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import FileResponse
from PIL import Image
from sqlalchemy import select

from astrophotoflow.contracts.media import MediaHdu, MediaSelection, MediaState
from astrophotoflow.contracts.previews import PreviewIssue
from astrophotoflow.core import http as deps
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.modules.data.media_cache import MediaCache
from astrophotoflow.modules.data.media_sources import PixelSource, numpy_arrays, ser_info
from astrophotoflow.modules.data.media_video import extract_frame, make_proxy, video_info
from astrophotoflow.modules.data.models import Asset, AssetTaskItem, AssetVersion, FitsHduMetadata, LibraryEntryRemoval, Preview
from astrophotoflow.modules.data.preview_recipes import backfill_context, describe_recipe, preview_context
from astrophotoflow.modules.data.previews import _library_version, _project_version
from astrophotoflow.modules.data.science_inputs import _asset_path


router = APIRouter(prefix="/api/v1", responses=deps.ERROR_RESPONSES, dependencies=[Depends(deps.authenticate)])
ALGORITHM = "media-view-2"


class LeasedFileResponse(FileResponse):
    def __init__(self, path, release, **kwargs):
        super().__init__(path, **kwargs)
        self.release = release

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            self.release()


class MediaViews:
    def __init__(self, database, settings, executor):
        self.database, self.settings, self.executor = database, settings, executor
        self.cache = MediaCache(settings.data_dir)
        self.lock = RLock()
        self.pending = {}
        self.using = {}
        self.consumers = {}
        self.interests = {}
        self.preparing = {}
        self.output_jobs = {}
        with database.write_session() as session:
            for row in session.scalars(select(Preview).where(Preview.size.in_({"viewer", "playback", "siril-live"}), Preview.status == "generating")).all():
                row.status, row.error = "failed", error_message(workspace_locale(self.settings.workspace), '', 'media_interrupted')
        for folder in self.cache.folders():
            for part in folder.glob("*.part*"):
                part.unlink(missing_ok=True)

    def _source(self, session, version_id):
        version = session.get(AssetVersion, version_id)
        if version is None:
            raise not_found()
        if version.availability != "available":
            raise ApiError(409, "SOURCE_UNAVAILABLE", "原件尚未就绪或已经变化。", message_key='the_original_is_not_ready_or_has_changed')
        removals = session.scalars(select(LibraryEntryRemoval)).all()
        if any(row.cleanup_status != "trash" and (row.entry_type == "asset" and row.entry_id == version.asset_id or
            row.entry_type == "dataset" and version.asset_id in (row.member_asset_ids or [])) for row in removals):
            raise ApiError(409, "SOURCE_CLEANUP_ACTIVE", "原件正在清理，不能准备或读取查看缓存。", message_key='the_original_is_being_cleaned_up_viewer_cache_preparation_and_reads_are_blo')
        path = _asset_path(self.settings, version)
        if version.byte_size is not None and path.stat().st_size != version.byte_size:
            raise ApiError(409, "SOURCE_CHANGED", "原件大小与固定版本不同，请先检查内容变化。", message_key='the_original_size_differs_from_the_fixed_version_check_content_changes_firs')
        return version, session.get(Asset, version.asset_id), path

    def prepare(self, version_id, selection):
        with self.lock:
            interest = (selection.consumer_id, selection.generation)
            if selection.consumer_id:
                observed = self.consumers.get(selection.consumer_id, (-1, 0))
                if selection.generation < observed[0]:
                    raise ApiError(409, "STALE_VIEW", "已切换到更新的查看请求。", message_key='a_newer_viewer_request_has_replaced_this_request')
                self.consumers[selection.consumer_id] = (selection.generation, time.monotonic())
                active_consumers = {consumer for interests in self.interests.values() for consumer, _ in interests}
                self.consumers = {consumer: value for consumer, value in self.consumers.items()
                                  if consumer in active_consumers or time.monotonic() - value[1] < 600}
                self._cancel_unused()
        with self.lock, self.database.write_session() as session:
            version, asset, path = self._source(session, version_id)
            selected = session.scalar(select(FitsHduMetadata).where(FitsHduMetadata.asset_version_id == version_id, FitsHduMetadata.is_selected.is_(True)))
            selection = selection.model_copy(deep=True, update={"consumer_id": None, "generation": 0})
            if selection.hdu_index is None and selected:
                selection.hdu_index = selected.hdu_index
            category = (version.scientific_metadata or {}).get("format")
            stamp = path.stat()
            previous = session.scalars(select(Preview).where(Preview.asset_version_id == version_id, Preview.size.in_({"viewer", "playback"}))).all()
            if any(row.display_parameters.get("source_stamp") not in (None, [stamp.st_size, stamp.st_mtime_ns]) for row in previous):
                raise ApiError(409, "SOURCE_CHANGED", "原件自上次查看后已经变化，请先检查内容变化。", message_key='the_original_has_changed_since_it_was_viewed_check_content_changes_first')
            if category not in {"fits", "xisf", "image", "raw", "numpy", "video"}:
                raise ApiError(422, "MEDIA_UNSUPPORTED", "当前素材不是受支持的可查看媒体。", message_key='this_asset_is_not_a_supported_viewable_media_type')
            if category == "video" and selection.media_time is not None and selection.playback_key:
                old = self._row(session, version_id, selection.playback_key)
                folder = (self.settings.data_dir / old.storage_path).parent
                mapping = json.loads((folder / "frames.json").read_text(encoding="utf-8"))
                match = min(mapping, key=lambda frame: abs(frame["time"] - selection.media_time))
                if abs(match["time"] - selection.media_time) > 0.003:
                    raise ApiError(422, "FRAME_NOT_MATCHED", "暂停帧时间戳没有对应的原始帧。", message_key='no_original_frame_matches_the_paused_frame_timestamp')
                selection.media_time = None
                selection.frame_index = match["index"]
            playback = category == "video" and selection.media_time is None and selection.frame_index is None
            thumbnail = session.scalar(select(Preview).where(Preview.asset_version_id == version_id, Preview.hdu_index == (selection.hdu_index or 0),
                Preview.size == "thumbnail", Preview.status == "available").order_by(Preview.created_at.desc()).limit(1))
            recipe = dict(thumbnail.display_parameters or {}) if thumbnail else {}
            identity_selection = selection.model_dump(mode="json", exclude={"consumer_id", "generation"})
            identity = json.dumps([ALGORITHM, version_id, version.content_hash, (asset.parameters or {}).get("cfa_pattern"), identity_selection, recipe], sort_keys=True)
            key = hashlib.sha256(identity.encode()).hexdigest()[:40]
            kind = "playback" if playback else "viewer"
            row = session.scalar(select(Preview).where(Preview.asset_version_id == version_id, Preview.size == kind, Preview.algorithm_version == ALGORITHM + ":" + key))
            folder = self.settings.data_dir / "previews" / version_id / "media" / key
            if row and not row.error and row.display_parameters["state"]["status"] == "available" and (folder / "manifest.json").is_file():
                return MediaState.model_validate(row.display_parameters["state"])
            if row and row.status == "generating":
                self.interests.setdefault(key, set()).add(interest)
                return MediaState.model_validate(row.display_parameters["state"])
            state = MediaState(key=key, status="generating", phase="queued", kind="video" if playback else "image", selection=selection)
            if row is None:
                row = Preview(id=str(uuid4()), asset_version_id=version_id, hdu_index=selection.hdu_index or 0, size=kind,
                    algorithm_version=ALGORITHM + ":" + key, width=0, height=0, mime_type="application/json",
                    storage_path=(folder / "manifest.json").relative_to(self.settings.data_dir).as_posix(),
                    display_parameters={"state": state.model_dump(mode="json"), "source_stamp": [stamp.st_size, stamp.st_mtime_ns]}, status="generating")
                session.add(row)
            else:
                row.status, row.error = "generating", None
                row.display_parameters = {"state": state.model_dump(mode="json"), "source_stamp": [stamp.st_size, stamp.st_mtime_ns]}
            job = dict(id=row.id, key=key, version_id=version_id, path=path, folder=folder, category=category,
                selection=selection, recipe=recipe, parameters={**dict(asset.parameters or {}),
                'colour_layout': (version.scientific_metadata or {}).get('colour_layout')}, stamp=(stamp.st_size, stamp.st_mtime_ns), playback=playback)
            self.interests[key] = {interest}
        with self.lock:
            try:
                future = self.executor.submit(self._prepare, job)
                self.preparing[key] = future
                def complete(completed):
                    with self.lock:
                        if self.preparing.get(key) is not completed:
                            return
                        if completed.cancelled():
                            self._fail(job, error_message(workspace_locale(self.settings.workspace), '', 'media_not_watched'))
                        self.preparing.pop(key, None)
                        self.interests.pop(key, None)
                future.add_done_callback(complete)
            except RuntimeError:
                self.interests.pop(key, None)
                self._fail(job, error_message(workspace_locale(self.settings.workspace), '', 'media_executor_closing'))
        return state

    def _row(self, session, version_id, key):
        row = session.scalar(select(Preview).where(Preview.asset_version_id == version_id, Preview.algorithm_version == ALGORITHM + ":" + key,
            Preview.size.in_({"viewer", "playback"})))
        if row is None:
            raise not_found()
        return row

    def status(self, version_id, key):
        with self.database.read_session() as session:
            self._source(session, version_id)
            row = self._row(session, version_id, key)
            state = MediaState.model_validate(row.display_parameters["state"])
            if row.error:
                state.status, state.error = "failed", PreviewIssue(code="MEDIA_FAILED", message=row.error)
                state.phase = None
            return state

    def cancel_consumer(self, consumer_id):
        with self.lock:
            self.consumers[consumer_id] = (2**63 - 1, time.monotonic())
            self._cancel_unused()

    def _wanted(self, key):
        return any(not consumer or self.consumers.get(consumer, (-1, 0))[0] == generation
                   for consumer, generation in self.interests.get(key, ()))

    def _cancel_unused(self):
        for key, future in list(self.preparing.items()):
            if not self._wanted(key):
                future.cancel()

    def _checkpoint(self, key):
        with self.lock:
            if not self._wanted(key):
                raise CancelledError(error_message(workspace_locale(self.settings.workspace), '', 'media_not_watched'))

    def _fail(self, job, message, state=None):
        if job.get('output_source'):
            with self.lock:
                state = state or MediaState.model_validate(job['state'])
                state.status, state.phase = 'failed', None
                state.error = PreviewIssue(code='MEDIA_FAILED', message=message)
                job['state'] = state.model_dump(mode='json')
            return
        with self.database.write_session() as session:
            row = session.get(Preview, job["id"])
            if row:
                row.status, row.error = "failed", message
                state = state or MediaState.model_validate(row.display_parameters["state"])
                state.status, state.phase = "failed", None
                row.display_parameters = {**row.display_parameters, "state": state.model_dump(mode="json")}

    def _prepare(self, job):
        folder = job["folder"]
        state = None
        try:
            self._checkpoint(job["key"])
            if job.get('output_source'):
                with self.lock:
                    state = MediaState.model_validate(job['state'])
                    state.phase = 'preparing'
                    job['state'] = state.model_dump(mode='json')
            else:
                with self.database.write_session() as session:
                    row = session.get(Preview, job["id"])
                    state = MediaState.model_validate(row.display_parameters["state"])
                    state.phase = "preparing"
                    row.display_parameters = {**row.display_parameters, "state": state.model_dump(mode="json")}
            with self.cache.hold(folder):
                folder.mkdir(parents=True, exist_ok=True)
                state = MediaState(key=job["key"], status="available", selection=job["selection"])
                path, category = job["path"], job["category"]
                if job['selection'].display_range is not None:
                    if job['playback']:
                        raise ValueError('请先暂停并检查原始帧，再调整该帧的显示阈值。')
                    low, high = job['selection'].display_range
                    job['recipe'] = {'stretch_low': low, 'stretch_high': high}
                if category == 'fits':
                    from astrophotoflow.modules.data.fits_preview import _image_kind, apply_colour_layout
                    with fits.open(path, memmap=False, lazy_load_hdus=True) as file:
                        for index, hdu in enumerate(file):
                            apply_colour_layout(hdu, job['parameters'].get('colour_layout'))
                            state.hdus.append(MediaHdu(index=index, name=hdu.header.get('EXTNAME'), shape=list(getattr(hdu, 'shape', None) or []),
                                                       kind=_image_kind(hdu, job['parameters'].get('cfa_pattern'))))
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
                    if chosen is not None and not chosen.numeric:
                        raise ValueError("所选数组不是数值图像，不能显示。")
                    if chosen is not None and len(chosen.shape) > 2 and job["selection"].x_axis is None:
                        state.needs_selection = True
                    if not state.needs_selection and chosen is None:
                        raise ValueError("没有找到所选数组。")
                if job["playback"]:
                    state.kind, state.proxy = "video", job["selection"].proxy or path.suffix.lower() == ".ser"
                    if state.proxy:
                        if path.suffix.lower() == ".ser" and not job["recipe"]:
                            source = PixelSource(path, category, MediaSelection(frame_index=0), job["parameters"], folder, self.cache.reserve)
                            job["recipe"] = {"auto_stretch": source.stretch()}
                        _, state.note = make_proxy(path, folder, self.cache, job["parameters"], job["recipe"])
                    state.mime_type = "video/mp4" if state.proxy else mimetypes.guess_type(path)[0] or "video/mp4"
                    if path.suffix.lower() == ".ser":
                        info = ser_info(path)
                        state.width, state.height, state.frame_count = info["width"], info["height"], info["count"]
                    else:
                        state.width, state.height, state.duration = video_info(path)
                    state.video_url = "video"
                elif not state.needs_selection:
                    if category == "video" and path.suffix.lower() != ".ser":
                        frame, _, _, timestamp = extract_frame(path, job["selection"], folder, self.cache.reserve)
                        job["pixel_path"], job["pixel_category"] = str(frame), "frame"
                        state.media_time = timestamp
                    source = self._pixels(job, lambda: self._checkpoint(job["key"]))
                    state.width, state.height = source.dimensions()
                    if source.linear and not ("auto_stretch" in job["recipe"] or "stretch_low" in job["recipe"] or job['recipe'].get('direct')):
                        if job.get('output_source'):
                            job['recipe'] = {'auto_stretch': source.stretch()}
                        else:
                            context = backfill_context(self.database, job["version_id"])
                            job["recipe"] = describe_recipe(context, {"auto_stretch": context["auto_stretch"] or self._stretch(job, source, context)})
                    if source.cfa and source.cfa not in {"MONO", "RGGB", "BGGR", "GRBG", "GBRG"}:
                        state.note = "此CFA排列以原尺寸传感器灰度马赛克查看。"
                    step = max(1, math.ceil(max(state.width, state.height) / 4096))
                    if source.cfa and step % 2 == 0:
                        step += 1
                    self._checkpoint(job["key"])
                    overview = source.render(source.read((0, 0, state.width, state.height), step), job["recipe"])
                    self._checkpoint(job["key"])
                    overview.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
                    buffer = BytesIO()
                    overview.save(buffer, format="JPEG", quality=90)
                    self.cache.write(folder / "overview.jpg", buffer.getvalue())
                    state.max_level = math.ceil(math.log2(max(state.width, state.height)))
                    state.overview_url, state.tile_url = "overview", "tiles/{level}/{x}/{y}"
                    state.frame_index = job["selection"].frame_index
                state.selection = job["selection"]
                self._checkpoint(job["key"])
                stamp = path.stat()
                if (stamp.st_size, stamp.st_mtime_ns) != job["stamp"]:
                    raise ValueError("原件在查看准备期间变化，未发布缓存。")
                job["state"] = state.model_dump(mode="json")
                saved = {key: str(value) if isinstance(value, Path) else value.model_dump(mode="json") if isinstance(value, MediaSelection) else value for key, value in job.items()}
                self.cache.write(folder / "manifest.json", json.dumps(saved, ensure_ascii=False).encode())
                if not job.get('output_source'):
                    with self.database.write_session() as session:
                        self._source(session, job["version_id"])
                        row = session.get(Preview, job["id"])
                        if row is None or row.status != "generating":
                            raise ValueError("查看缓存已失去生成所有权。")
                        row.width, row.height, row.status = state.width, state.height, "available"
                        row.display_parameters = {**job["recipe"], "source_stamp": list(job["stamp"]), "state": state.model_dump(mode="json")}
        except Exception as exc:
            self._fail(job, error_message(workspace_locale(self.settings.workspace), '', 'media_failure_diagnostic', {'diagnostic': str(exc)}), state)

    def _stretch(self, job, source, context):
        if not context.get("group_key"):
            return source.stretch()
        with self.database.read_session() as session:
            ids = session.scalars(select(AssetTaskItem.asset_version_id).where(AssetTaskItem.task_id == context["task_id"],
                AssetTaskItem.asset_version_id.is_not(None)).order_by(AssetTaskItem.position)).all()
        for version_id in ids:
            candidate = preview_context(self.database, context["task_id"], version_id)
            if candidate["group_key"] != context["group_key"]:
                continue
            with self.database.read_session() as session:
                version = session.get(AssetVersion, version_id)
                if version.availability != "available":
                    continue
                parameters = {**dict(session.get(Asset, version.asset_id).parameters or {}),
                              'colour_layout': (version.scientific_metadata or {}).get('colour_layout')}
                hdu = session.scalar(select(FitsHduMetadata).where(FitsHduMetadata.asset_version_id == version_id, FitsHduMetadata.is_selected.is_(True)))
                path = _asset_path(self.settings, version)
                category = (version.scientific_metadata or {}).get("format")
            if version_id == job["version_id"]:
                measured = source.stretch()
            elif category == "fits":
                from astrophotoflow.modules.data.auto_stretch import calculate_stretch
                from astrophotoflow.modules.data.fits_preview import read_stretch_pixels
                try:
                    measured = calculate_stretch(read_stretch_pixels(path, hdu.hdu_index, hdu.supported_kind, parameters, lambda: self._checkpoint(job["key"])))
                except ValueError:
                    continue
            else:
                from astrophotoflow.modules.data.auto_stretch import calculate_stretch
                from astrophotoflow.modules.data.ingestion import _xisf_pixels
                try:
                    measured = calculate_stretch(_xisf_pixels(path))
                except ValueError:
                    continue
            context["reference_version_id"] = version_id
            return measured
        raise ValueError("同Object分组中尚无可测量的就绪帧，请稍后重试。")

    def _pixels(self, job, check_cancel=None):
        return PixelSource(Path(job.get("pixel_path", job["path"])), job.get("pixel_category", job["category"]),
            job["selection"], job["parameters"], job["folder"], self.cache.reserve, check_cancel)

    def acquire(self, version_id, key):
        with self.lock, self.database.write_session() as session:
            _, _, path = self._source(session, version_id)
            row = self._row(session, version_id, key)
            folder = (self.settings.data_dir / row.storage_path).parent
            if row.error or not (folder / "manifest.json").is_file():
                raise ApiError(409, "MEDIA_NOT_READY", row.error or "缓存已被回收，请重新打开查看器。", message_key='media_reopen_required', fields=[{'path': 'diagnostic', 'message': row.error or "缓存已被回收，请重新打开查看器。"}])
            job = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
            stat = path.stat()
            if [stat.st_size, stat.st_mtime_ns] != job["stamp"]:
                raise ApiError(409, "SOURCE_CHANGED", "原件已经变化，请重新检查素材内容。", message_key='the_original_has_changed_check_the_asset_content_again')
            job["path"], job["folder"], job["selection"] = path, folder, MediaSelection.model_validate(job["selection"])
            self.using[key] = self.using.get(key, 0) + 1
            row.status = "generating"
            hold = self.cache.hold(folder)
            hold.__enter__()
            folder.touch()
            return job, lambda: self.release(job, hold)

    def release(self, job, hold):
        with self.lock:
            hold.__exit__(None, None, None)
            self.using[job["key"]] -= 1
            if not self.using[job["key"]]:
                del self.using[job["key"]]
                if not job.get('output_source'):
                    with self.database.write_session() as session:
                        row = session.get(Preview, job["id"])
                        if row and row.status == "generating":
                            row.status = "available"

    def prepare_output(self, checked, selection, *, direct):
        path = checked.path
        stamp = path.stat()
        if checked.format not in {'fits', 'xisf', 'image', 'raw', 'numpy', 'video'}:
            raise ApiError(422, 'MEDIA_UNSUPPORTED', '该输出不是可查看的科学图像或视频。', message_key='this_output_is_not_a_viewable_scientific_image_or_video')
        if selection.hdu_index is None:
            selection = selection.model_copy(update={'hdu_index': (checked.scientific_metadata or {}).get('selected_hdu')})
        if checked.format == 'video' and selection.media_time is not None and selection.playback_key:
            playback_key = selection.playback_key
            if not re.fullmatch('[a-f0-9]{40}', playback_key):
                raise not_found()
            previous = self.settings.data_dir / 'previews' / 'run-outputs' / 'media' / playback_key
            job = json.loads((previous / 'manifest.json').read_text(encoding='utf-8'))
            if Path(job['path']).resolve() != path.resolve() or job['stamp'] != [stamp.st_size, stamp.st_mtime_ns]:
                raise ApiError(409, 'SOURCE_CHANGED', '视频播放缓存不属于当前完整结果。', message_key='the_video_playback_cache_does_not_belong_to_the_current_complete_result')
            mapping = json.loads((previous / 'frames.json').read_text(encoding='utf-8'))
            match = min(mapping, key=lambda frame: abs(frame['time'] - selection.media_time))
            if abs(match['time'] - selection.media_time) > 0.003:
                raise ApiError(422, 'FRAME_NOT_MATCHED', '暂停帧时间戳没有对应的原始帧。', message_key='no_original_frame_matches_the_paused_frame_timestamp')
            selection = selection.model_copy(update={'media_time': None, 'frame_index': match['index']})
        interest = selection.consumer_id, selection.generation
        identity_selection = selection.model_dump(mode='json', exclude={'consumer_id', 'generation'})
        key = hashlib.sha256(json.dumps([ALGORITHM, 'checked-output', checked.content_hash, str(path),
                                        (checked.scientific_metadata or {}).get('colour_layout'), identity_selection, direct], sort_keys=True).encode()).hexdigest()[:40]
        folder = self.settings.data_dir / 'previews' / 'run-outputs' / 'media' / key
        with self.lock:
            if selection.consumer_id:
                old = self.consumers.get(selection.consumer_id, (-1, 0))
                if selection.generation < old[0]:
                    raise ApiError(409, 'STALE_VIEW', '已切换到更新的查看请求。', message_key='a_newer_viewer_request_has_replaced_this_request')
                self.consumers[selection.consumer_id] = selection.generation, time.monotonic()
                self._cancel_unused()
            self.interests.setdefault(key, set()).add(interest)
            previous = self.output_jobs.get(key)
            if previous and previous['state']['status'] == 'generating':
                return MediaState.model_validate(previous['state'])
            manifest = folder / 'manifest.json'
            if manifest.is_file():
                previous = json.loads(manifest.read_text(encoding='utf-8'))
                if previous['stamp'] != [stamp.st_size, stamp.st_mtime_ns]:
                    raise ApiError(409, 'SOURCE_CHANGED', '完整结果在查看准备后发生变化。', message_key='the_complete_result_changed_after_viewer_preparation')
                self.output_jobs[key] = previous
                return MediaState.model_validate(previous['state'])
            state = MediaState(key=key, status='generating', phase='queued', selection=selection)
            playback = checked.format == 'video' and selection.frame_index is None and selection.media_time is None
            job = dict(key=key, path=path, folder=folder, category=checked.format, selection=selection.model_copy(update={'consumer_id': None, 'generation': 0}),
                       recipe={'direct': True} if direct else {}, parameters={'colour_layout': (checked.scientific_metadata or {}).get('colour_layout')}, stamp=(stamp.st_size, stamp.st_mtime_ns),
                       playback=playback, output_source=True, state=state.model_dump(mode='json'))
            self.output_jobs[key] = job
            future = self.executor.submit(self._prepare, job)
            self.preparing[key] = future
            def complete(completed):
                with self.lock:
                    if completed.cancelled():
                        self._fail(job, error_message(workspace_locale(self.settings.workspace), '', 'media_not_watched'))
                    self.preparing.pop(key, None)
                    self.interests.pop(key, None)
            future.add_done_callback(complete)
        return state

    def output_status(self, checked, key):
        with self.lock:
            job = self.output_jobs.get(key)
            if job is None:
                raise ApiError(409, 'MEDIA_NOT_READY', '显示缓存已失效，请重新打开查看器。', message_key='the_display_cache_is_stale_reopen_the_viewer')
            stamp = checked.path.stat()
            if Path(job['path']).resolve() != checked.path.resolve() or tuple(job['stamp']) != (stamp.st_size, stamp.st_mtime_ns):
                raise ApiError(409, 'SOURCE_CHANGED', '显示状态不属于该完整结果。', message_key='the_display_state_does_not_belong_to_this_complete_result')
            return MediaState.model_validate(job['state'])

    def thumbnail_output(self, checked, *, direct):
        metadata = checked.scientific_metadata or {}
        identity = json.dumps([ALGORITHM, 'output-thumbnail', checked.content_hash, metadata.get('selected_hdu'), metadata.get('colour_layout'), direct], sort_keys=True)
        key = hashlib.sha256(identity.encode()).hexdigest()[:40]
        folder = self.settings.data_dir / 'previews' / 'run-outputs' / 'media' / key
        hold = self.cache.hold(folder)
        hold.__enter__()
        try:
            path = folder / 'thumbnail.jpg'
            if not path.is_file():
                from astrophotoflow.modules.data.science_inputs import render_output_preview
                self.cache.reserve(1024 * 1024 * 3)
                folder.mkdir(parents=True, exist_ok=True)
                render_output_preview(checked, path, max_edge=1024, auto_stretch=not direct)
            return path, lambda: hold.__exit__(None, None, None)
        except Exception:
            hold.__exit__(None, None, None)
            raise

    def acquire_output(self, checked, key):
        if not re.fullmatch('[a-f0-9]{40}', key):
            raise not_found()
        folder = self.settings.data_dir / 'previews' / 'run-outputs' / 'media' / key
        with self.lock:
            manifest = folder / 'manifest.json'
            if not manifest.is_file():
                raise ApiError(409, 'MEDIA_NOT_READY', '显示缓存已被回收，请重新打开查看器。', message_key='the_display_cache_has_been_removed_reopen_the_viewer')
            job = json.loads(manifest.read_text(encoding='utf-8'))
            stamp = checked.path.stat()
            if Path(job['path']).resolve() != checked.path.resolve() or job['stamp'] != [stamp.st_size, stamp.st_mtime_ns]:
                raise ApiError(409, 'SOURCE_CHANGED', '显示缓存与当前完整结果不匹配。', message_key='the_display_cache_does_not_match_the_current_complete_result')
            job['path'], job['folder'], job['selection'] = checked.path, folder, MediaSelection.model_validate(job['selection'])
            self.using[key] = self.using.get(key, 0) + 1
            hold = self.cache.hold(folder)
            hold.__enter__()
            folder.touch()
            return job, lambda: self.release(job, hold)

    def tile(self, job, level, x, y):
        future = self.tile_future(job, level, x, y)
        return future.result()

    def tile_future(self, job, level, x, y, *, tracked=False):
        state = job["state"]
        if state["kind"] != "image":
            raise ApiError(422, "MEDIA_NOT_IMAGE", "请先暂停视频并准备原件帧。", message_key='pause_the_video_and_prepare_the_original_frame_first')
        factor = 2 ** (state["max_level"] - level) if 0 <= level <= state["max_level"] else 0
        if not factor or x < 0 or y < 0 or x * 512 * factor >= state["width"] or y * 512 * factor >= state["height"]:
            raise ApiError(422, "INVALID_TILE", "瓦片坐标超出图像范围。", message_key='tile_coordinates_are_outside_the_image_bounds')
        token = (job["key"], level, x, y)
        cached = self.cache.get(token)
        if cached is not None:
            result = Future()
            result.set_result(cached)
            return result
        target = job["folder"] / f"tile-{level}-{x}-{y}.png"
        if target.is_file():
            value = target.read_bytes()
            self.cache.put(token, value)
            result = Future()
            result.set_result(value)
            return result
        else:
            with self.lock:
                work = self.pending.get(token)
                if work is None:
                    stop = Event()
                    future = self.executor.submit(self._tile, job, level, x, y, target, stop)
                    work = dict(future=future, stop=stop, readers=int(tracked), retained=not tracked)
                    self.pending[token] = work
                    def complete(completed):
                        with self.lock:
                            self.pending.pop(token, None)
                        if not completed.cancelled() and completed.exception() is None:
                            self.cache.put(token, completed.result())
                    future.add_done_callback(complete)
                else:
                    work["readers"] += int(tracked)
                    work["retained"] |= not tracked
            return work["future"]

    def release_tile(self, job, level, x, y, future):
        with self.lock:
            work = self.pending.get((job["key"], level, x, y))
            if work is not None and work["future"] is future:
                work["readers"] -= 1
                if not work["readers"] and not work["retained"]:
                    work["stop"].set()
                    work["future"].cancel()

    def _tile(self, job, level, x, y, target, stop):
        def check_cancel():
            if stop.is_set():
                raise CancelledError("瓦片请求已取消。")
        check_cancel()
        state = job["state"]
        factor = 2 ** (state["max_level"] - level)
        width, height = math.ceil(state["width"] / factor), math.ceil(state["height"] / factor)
        left, top = x * 512, y * 512
        right, bottom = min(left + 512, width), min(top + 512, height)
        source = self._pixels(job, check_cancel)
        source.dimensions()
        step = max(1, factor // 2)
        if source.category == "fits" or source.path.suffix.lower() == ".ser":
            if step % 2 == 0 and source.cfa in {"RGGB", "BGGR", "GRBG", "GBRG"}:
                step -= 1
        sx, sy = max(0, (left - 3) * factor) // step * step, max(0, (top - 3) * factor) // step * step
        ex, ey = min(state["width"], (right + 3) * factor), min(state["height"], (bottom + 3) * factor)
        image = source.render(source.read((sx, sy, ex, ey), step), job["recipe"])
        box = ((left * factor - sx) / step, (top * factor - sy) / step,
            min(image.width, (right * factor - sx) / step), min(image.height, (bottom * factor - sy) / step))
        image = image.resize((right - left, bottom - top), Image.Resampling.LANCZOS if factor > 1 else Image.Resampling.NEAREST, box=box)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        value = buffer.getvalue()
        check_cancel()
        self.cache.write(target, value)
        return value


def _version(request, session, asset_id=None, version_id=None, project_id=None, reference_id=None):
    return _project_version(session, project_id, reference_id) if "/projects/" in request.url.path else _library_version(session, asset_id, version_id)


def _base(request):
    return str(request.url.path).split("/viewer")[0] + "/viewer"


def _urls(state, base):
    state = state.model_copy(deep=True)
    for field in ("overview_url", "tile_url", "video_url"):
        if value := getattr(state, field):
            setattr(state, field, f"/astrophotoflow{base}/{state.key}/{value}")
    return state


@router.delete("/library/assets/{asset_id}/versions/{version_id}/previews/viewer/consumer/{consumer_id}", status_code=204)
@router.delete("/projects/{project_id}/asset-references/{reference_id}/previews/viewer/consumer/{consumer_id}", status_code=204)
def cancel_media_consumer(consumer_id: UUID, request: Request, session: deps.ReadSession, asset_id: UUID | None = None,
                          version_id: UUID | None = None, project_id: UUID | None = None, reference_id: UUID | None = None):
    _version(request, session, asset_id, version_id, project_id, reference_id)
    request.app.state.media_views.cancel_consumer(str(consumer_id))
    return Response(status_code=204)


@router.post("/library/assets/{asset_id}/versions/{version_id}/previews/viewer", response_model=MediaState)
@router.post("/projects/{project_id}/asset-references/{reference_id}/previews/viewer", response_model=MediaState)
def prepare_media(body: MediaSelection, request: Request, response: Response, admission: deps.TaskAdmission, session: deps.ReadSession,
                  asset_id: UUID | None = None, version_id: UUID | None = None, project_id: UUID | None = None, reference_id: UUID | None = None):
    state = request.app.state.media_views.prepare(_version(request, session, asset_id, version_id, project_id, reference_id), body)
    response.status_code = 202 if state.status == "generating" else 200
    return _urls(state, _base(request))


@router.get("/library/assets/{asset_id}/versions/{version_id}/previews/viewer/{key}/status", response_model=MediaState)
@router.get("/projects/{project_id}/asset-references/{reference_id}/previews/viewer/{key}/status", response_model=MediaState)
def media_status(key: str, request: Request, session: deps.ReadSession, asset_id: UUID | None = None,
                 version_id: UUID | None = None, project_id: UUID | None = None, reference_id: UUID | None = None):
    return _urls(request.app.state.media_views.status(_version(request, session, asset_id, version_id, project_id, reference_id), key), _base(request))


@router.get("/library/assets/{asset_id}/versions/{version_id}/previews/viewer/{key}/tiles/{level}/{x}/{y}")
@router.get("/projects/{project_id}/asset-references/{reference_id}/previews/viewer/{key}/tiles/{level}/{x}/{y}")
async def media_tile(key: str, level: int, x: int, y: int, request: Request, admission: deps.TaskAdmission, session: deps.ReadSession,
               asset_id: UUID | None = None, version_id: UUID | None = None, project_id: UUID | None = None, reference_id: UUID | None = None):
    if await request.is_disconnected():
        raise asyncio.CancelledError()
    service = request.app.state.media_views
    job, release = service.acquire(_version(request, session, asset_id, version_id, project_id, reference_id), key)
    future = None
    try:
        future = service.tile_future(job, level, x, y, tracked=True)
        pending = asyncio.wrap_future(future)
        while not pending.done():
            await asyncio.wait({pending}, timeout=0.1)
            if await request.is_disconnected():
                raise asyncio.CancelledError()
        return Response(pending.result(), media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})
    finally:
        if future is not None:
            service.release_tile(job, level, x, y, future)
        if future is not None and not future.done():
            future.add_done_callback(lambda _: release())
        else:
            release()


@router.get("/library/assets/{asset_id}/versions/{version_id}/previews/viewer/{key}/{file}")
@router.get("/projects/{project_id}/asset-references/{reference_id}/previews/viewer/{key}/{file}")
def media_file(key: str, file: str, request: Request, admission: deps.TaskAdmission, session: deps.ReadSession,
               asset_id: UUID | None = None, version_id: UUID | None = None, project_id: UUID | None = None, reference_id: UUID | None = None):
    if file not in {"overview", "video"}:
        raise not_found()
    job, release = request.app.state.media_views.acquire(_version(request, session, asset_id, version_id, project_id, reference_id), key)
    try:
        if file == "video" and job["state"]["kind"] != "video":
            raise not_found()
        path = job["folder"] / "overview.jpg" if file == "overview" else job["folder"] / "playback.mp4" if job["state"]["proxy"] else job["path"]
        if not path.is_file():
            raise not_found()
        return LeasedFileResponse(path, release, media_type="image/jpeg" if file == "overview" else job["state"]["mime_type"])
    except Exception:
        release()
        raise
