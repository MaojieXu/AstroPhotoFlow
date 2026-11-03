"""Recoverable background generation of fixed-context library thumbnails."""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from threading import Event, Lock, Thread
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import or_, select

from astrophotoflow.contracts.thumbnails import ThumbnailBatchCreate
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion, FitsHduMetadata
from astrophotoflow.modules.data.assets.visibility import standalone_asset_ids, visible_dataset, visible_members
from astrophotoflow.modules.data.datasets.models import Dataset
from astrophotoflow.modules.data.files import find_root, resolve_relative
from astrophotoflow.modules.data.formats.thumbnails import render_thumbnail
from astrophotoflow.modules.data.imports.models import AssetTask, AssetTaskItem
from astrophotoflow.modules.data.media.models import Preview, ThumbnailBatch
from astrophotoflow.modules.data.media.thumbnail_batches import (
    THUMBNAIL_FORMATS,
    THUMBNAIL_GROUP_PREFIX,
    THUMBNAIL_STANDALONE,
    create_thumbnail_batch,
    group_algorithm,
    retry_thumbnail_items,
    thumbnail_batch_status,
)
from astrophotoflow.modules.data.science.files import read_hash_and_copy
from astrophotoflow.modules.data.trash.models import LibraryEntryRemoval

logger = logging.getLogger(__name__)


class UnsupportedThumbnail(ValueError):
    pass


class ThumbnailService:
    def __init__(self, database, settings, executor):
        self.database, self.settings, self.executor = database, settings, executor
        self._wake = Event()
        self._stop = Event()
        self._lock = Lock()
        self._admission = Lock()
        self._paused = False
        self._in_flight = set()
        self._priority = set()
        self._thread = None
        self._reconcile_cursor = ''

    def start(self):
        with self.database.write_session() as session:
            for row in session.scalars(select(Preview).where(
                or_(Preview.algorithm_version == THUMBNAIL_STANDALONE,
                    Preview.algorithm_version.startswith(THUMBNAIL_GROUP_PREFIX)),
                Preview.status == "generating")).all():
                row.status, row.error = "queued", None
        self._thread = Thread(target=self._run, name="library-thumbnails", daemon=True)
        self._thread.start()

    def close(self):
        with self._admission:
            self._paused = True
            self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join()

    def submit(self, body):
        identity = create_thumbnail_batch(self.database, body)
        self._wake.set()
        return self.status(identity)

    def status(self, batch_id, limit=50, offset=0):
        return thumbnail_batch_status(self.database, str(batch_id), limit, offset)

    def retry(self, batch_id, item_ids):
        retry_thumbnail_items(self.database, str(batch_id), [str(value) for value in item_ids])
        self._wake.set()
        return self.status(batch_id)

    def prioritize(self, version_ids):
        with self._lock:
            self._priority.update(map(str, version_ids))
        self.executor.prioritize(set(map(str, version_ids)))
        self._wake.set()

    def pause(self):
        with self._admission:
            self._paused = True

    def resume(self):
        with self._admission:
            self._paused = False
        self._wake.set()

    def ensure_dataset(self, dataset_id, version_id):
        target = {"kind": "dataset", "dataset_id": str(dataset_id), "dataset_version_id": str(version_id)}
        self._ensure_auto(target)
        self._wake.set()

    def _ensure_auto(self, target):
        identity = uuid5(NAMESPACE_URL, "astrophotoflow:thumbnail:v1:" + ":".join(target.values()))
        with self._admission:
            if self._paused:
                return
            with self.database.read_session() as session:
                if session.get(ThumbnailBatch, str(identity)) is not None:
                    return
            body = ThumbnailBatchCreate.model_validate({"request_id": str(identity), "target": target}, strict=False)
            create_thumbnail_batch(self.database, body)

    def _auto_batches(self):
        with self.database.read_session() as session:
            groups = session.execute(select(Dataset.id, Dataset.current_version_id).where(
                visible_dataset(), Dataset.current_version_id.is_not(None),
                ~select(AssetTask.id).where(AssetTask.target_dataset_id == Dataset.id,
                    AssetTask.status.in_(("queued", "running", "cancelling"))).exists())).all()
            members = visible_members()
            standalone = standalone_asset_ids(members)
            assets = session.execute(select(Asset.id, Asset.current_version_id).join(
                AssetVersion, AssetVersion.id == Asset.current_version_id).where(
                Asset.id.in_(standalone), AssetVersion.availability == "available",
                AssetVersion.scientific_metadata["format"].as_string().in_(THUMBNAIL_FORMATS),
                ~select(AssetTaskItem.id).join(AssetTask, AssetTask.id == AssetTaskItem.task_id).where(
                    AssetTaskItem.asset_version_id == AssetVersion.id,
                    AssetTask.status.in_(("queued", "running", "cancelling"))).exists())).all()
        targets = ([{"kind": "dataset", "dataset_id": group, "dataset_version_id": version}
                    for group, version in groups] +
                   [{"kind": "asset", "asset_id": asset, "asset_version_id": version}
                    for asset, version in assets])
        for target in targets:
            if self._stop.is_set():
                return
            try:
                self._ensure_auto(target)
            except Exception:
                logger.exception("Could not queue automatic thumbnails for %s", target)

    def _reconcile_cache(self):
        with self._admission:
            if self._paused:
                return
            with self.database.read_session() as session:
                candidates = session.execute(select(Preview.id, Preview.storage_path).where(
                    Preview.status == "available",
                    or_(Preview.algorithm_version == THUMBNAIL_STANDALONE,
                        Preview.algorithm_version.startswith(THUMBNAIL_GROUP_PREFIX)),
                    Preview.id > self._reconcile_cursor,
                ).order_by(Preview.id).limit(100)).all()
            self._reconcile_cursor = candidates[-1][0] if len(candidates) == 100 else ''
            root = self.settings.data_dir.resolve()
            missing = []
            for identity, storage_path in candidates:
                try:
                    relative = Path(storage_path)
                    path = (root / relative).resolve()
                    usable = (bool(storage_path) and not relative.is_absolute()
                              and ".." not in relative.parts and path.is_relative_to(root)
                              and path.is_file())
                except (OSError, ValueError, RuntimeError):
                    usable = False
                if not usable:
                    missing.append((identity, storage_path))
            if missing:
                with self.database.write_session() as session:
                    for identity, storage_path in missing:
                        preview = session.get(Preview, identity)
                        if preview is not None and preview.status == "available" and preview.storage_path == storage_path:
                            preview.status, preview.error = "queued", None

    def _run(self):
        next_scan = 0.0
        while not self._stop.is_set():
            try:
                with self._admission:
                    paused = self._paused
                if not paused and time.monotonic() >= next_scan:
                    self._reconcile_cache()
                    self._auto_batches()
                    next_scan = time.monotonic() + 30
                with self._admission:
                    if not self._paused:
                        self._dispatch()
            except Exception:
                logger.exception("Thumbnail queue reconciliation failed")
            self._wake.wait(3)
            self._wake.clear()

    def _dispatch(self):
        with self._lock:
            available_slots = max(0, max(2, self.settings.preview_workers * 2) - len(self._in_flight))
            in_flight = set(self._in_flight)
            priority = set(self._priority)
        if not available_slots:
            return
        with self.database.read_session() as session:
            candidates = session.execute(select(Preview.id, Preview.asset_version_id,
                Preview.algorithm_version, Preview.display_parameters).where(
                Preview.status == "queued", or_(Preview.algorithm_version == THUMBNAIL_STANDALONE,
                    Preview.algorithm_version.startswith(THUMBNAIL_GROUP_PREFIX)))
                .order_by(Preview.created_at, Preview.id)).all()
            references = {parameters.get("reference_version_id") for _, _, _, parameters in candidates
                          if parameters and parameters.get("reference_version_id")}
            reference_rows = session.scalars(select(Preview).where(
                Preview.asset_version_id.in_(references), Preview.size == "group_thumbnail",
                Preview.algorithm_version.startswith(THUMBNAIL_GROUP_PREFIX))).all() if references else []
            reference_by_id = {row.asset_version_id: row for row in reference_rows
                               if row.algorithm_version == group_algorithm(row.asset_version_id)}
            ready = []
            failed = []
            for preview_id, version_id, algorithm, parameters in candidates:
                if preview_id in in_flight:
                    continue
                ref = (parameters or {}).get("reference_version_id")
                if ref and ref != version_id:
                    reference = reference_by_id.get(ref)
                    if reference is None or reference.status in {"failed", "unsupported"}:
                        failed.append(preview_id)
                        continue
                    if reference.status != "available":
                        continue
                ready.append((preview_id, version_id))
        if failed:
            with self.database.write_session() as session:
                for identity in failed:
                    row = session.get(Preview, identity)
                    if row and row.status == "queued":
                        row.status, row.error = "failed", "First group member has no usable stretch."
        ready.sort(key=lambda item: item[1] not in priority)
        for preview_id, version_id in ready[:available_slots]:
            with self._lock:
                if preview_id in self._in_flight:
                    continue
                self._in_flight.add(preview_id)
                self._priority.discard(version_id)
            try:
                future = self.executor.submit_background(version_id, self._generate, preview_id)
                future.add_done_callback(lambda _future, identity=preview_id: self._finished(identity))
            except Exception:
                self._finished(preview_id)
                raise

    def _finished(self, preview_id):
        with self._lock:
            self._in_flight.discard(preview_id)
        self._wake.set()

    def _read_context(self, session, preview):
        version = session.get(AssetVersion, preview.asset_version_id)
        asset = session.get(Asset, version.asset_id) if version else None
        if version is None or asset is None or version.availability != "available":
            raise ValueError("Original image is not available.")
        if session.get(LibraryEntryRemoval, ("asset", asset.id)) is not None:
            raise ValueError("Original image is in the trash.")
        metadata = version.scientific_metadata or {}
        category = metadata.get("format")
        if category not in THUMBNAIL_FORMATS:
            raise UnsupportedThumbnail(f"Unsupported image format: {category!r}")
        hdu = session.scalar(select(FitsHduMetadata).where(
            FitsHduMetadata.asset_version_id == version.id,
            FitsHduMetadata.hdu_index == preview.hdu_index))
        if category == "fits" and (hdu is None or hdu.supported_kind not in {"mono", "bayer", "rgb"}):
            raise UnsupportedThumbnail("FITS image layout is not supported for thumbnails.")
        snapshot = version.capture_snapshot or {}
        parameters = {**dict(snapshot.get("parameters") or {}), "colour_layout": metadata.get("colour_layout")}
        if version.storage_mode == "managed":
            path = self.settings.data_dir / version.storage_location
        else:
            _, root_id, relative = version.storage_location.split("/", 2)
            _, root = find_root(self.settings, root_id)
            path = resolve_relative(root, relative)
        reference_id = (preview.display_parameters or {}).get("reference_version_id")
        layout = {"category": category, "kind": hdu.supported_kind if hdu else None,
                  "unit": hdu.bunit if hdu else None}
        recipe = ((preview.display_parameters or {}).get("auto_stretch")
                  if reference_id == version.id else None)
        if reference_id and reference_id != version.id:
            reference = session.scalar(select(Preview).where(
                Preview.asset_version_id == reference_id, Preview.size == "group_thumbnail",
                Preview.algorithm_version == group_algorithm(reference_id), Preview.status == "available"))
            if reference is None:
                raise ValueError("First group member has no usable stretch.")
            recipe = (reference.display_parameters or {}).get("auto_stretch")
            if recipe is None:
                raise ValueError("First group member has no usable stretch.")
            reference_layout = (reference.display_parameters or {}).get("layout") or {}
            if (reference_layout.get("category"), reference_layout.get("kind")) != (layout["category"], layout["kind"]):
                raise ValueError("Image layout is incompatible with the first group member.")
            if reference_layout.get("unit") and layout["unit"] and reference_layout["unit"] != layout["unit"]:
                raise ValueError("Image units are incompatible with the first group member.")
        return path, category, hdu.supported_kind if hdu else None, parameters, recipe, reference_id, layout, version.byte_size, version.content_hash

    def _generate(self, preview_id):
        temporary = None
        try:
            with self._admission:
                if self._paused:
                    return
                with self.database.write_session() as session:
                    preview = session.get(Preview, preview_id)
                    if preview is None or preview.status != "queued":
                        return
                    preview.status, preview.error = "generating", None
            with self.database.read_session() as session:
                preview = session.get(Preview, preview_id)
                if preview is None or preview.status != "generating":
                    return
                path, category, kind, parameters, recipe, reference_id, layout, expected_size, expected_hash = self._read_context(session, preview)
                hdu_index, version_id = preview.hdu_index, preview.asset_version_id
            before = path.stat()
            if expected_size is not None and before.st_size != expected_size:
                raise ValueError("Original image size differs from the fixed version.")
            if expected_hash:
                observed_hash, observed_size = read_hash_and_copy(path, None, self._stop.is_set)
                after_hash = path.stat()
                if observed_hash != expected_hash:
                    raise ValueError("Original image content differs from the fixed version.")
                if observed_size != before.st_size or (before.st_size, before.st_mtime_ns) != (after_hash.st_size, after_hash.st_mtime_ns):
                    raise ValueError("Original image changed while verifying the fixed version.")
            if self._stop.is_set():
                raise RuntimeError('Thumbnail service stopped.')
            image, stretch = render_thumbnail(path, category, hdu_index, kind, parameters, recipe=recipe)
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ValueError("Original image changed while preparing the thumbnail.")
            relative = Path("previews") / version_id / f"library-thumb-{preview_id}.jpg"
            final = self.settings.data_dir / relative
            final.parent.mkdir(parents=True, exist_ok=True)
            temporary = final.with_suffix(".tmp")
            image.save(temporary, format="JPEG", quality=80, optimize=False)
            with self._admission:
                if self._stop.is_set():
                    raise RuntimeError('Thumbnail service stopped.')
                with self.database.write_session() as session:
                    preview = session.get(Preview, preview_id)
                    if preview is None or preview.status != "generating":
                        return
                    os.replace(temporary, final)
                    preview.storage_path = relative.as_posix()
                    preview.width, preview.height = image.size
                    preview.display_parameters = {"reference_version_id": reference_id, "auto_stretch": stretch, "layout": layout}
                    preview.status, preview.error = "available", None
        except Exception as exc:
            if not self._stop.is_set():
                logger.exception("Library thumbnail failed preview_id=%s", preview_id)
            with self.database.write_session() as session:
                preview = session.get(Preview, preview_id)
                if preview is not None and preview.status == "generating":
                    preview.status = "queued" if self._stop.is_set() else "unsupported" if isinstance(exc, UnsupportedThumbnail) else "failed"
                    preview.error = None if self._stop.is_set() else str(exc)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
