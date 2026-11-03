import hashlib
import json
from contextlib import AbstractContextManager
from pathlib import Path
from uuid import uuid4

import numpy as np
from astropy.io import fits
from sqlalchemy import select

from astrophotoflow.contracts.inputs import CanvasInspectRequest
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.assets.canvas import inspect_canvas_data
from astrophotoflow.modules.data.assets.models import AssetVersion
from astrophotoflow.modules.data.assets.storage import asset_path
from astrophotoflow.modules.data.media.models import Preview
from astrophotoflow.modules.data.media.references import library_preview_version

from .rendering import read_fits_sample


class BundleSample:
    def __init__(self, database: Database, row_id: str, folder: Path, path: Path, guard: AbstractContextManager):
        self.database, self.row_id, self.folder, self.path, self.guard = database, row_id, folder, path, guard

    def close(self, error: BaseException | None = None) -> None:
        try:
            with self.database.write_session() as session:
                row = session.get(Preview, self.row_id)
                if row is not None:
                    row.status, row.error = ("failed", str(error)) if error is not None else ("available", None)
        finally:
            self.guard.__exit__(None, None, None)


def prepare_bundle_sample(database, settings, cache, body, check_cancel, decoder_key='', colour_layout=None) -> BundleSample:
    item = inspect_canvas_data(database, CanvasInspectRequest(reference=body.reference, member_index=body.member_index))
    with database.write_session() as session:
        version = session.get(AssetVersion, library_preview_version(session, str(item.asset_id), str(item.asset_version_id)))
        path = asset_path(settings, version)
        stamp = path.stat()
        if version.availability != "available" or version.byte_size != stamp.st_size:
            raise ApiError(409, "SOURCE_UNAVAILABLE", "原件尚未就绪或已经变化。", message_key='the_original_is_not_ready_or_has_changed')
        category = (version.scientific_metadata or {}).get("format")
        if category not in {"fits", "xisf", "image", "raw"}:
            raise ApiError(422, "UNSUPPORTED_SELECTION", "实时显示样本需要固定静态图像；视频和数值数组不能作为该预览输入。", message_key='live_display_samples_require_a_fixed_still_image_videos_and_numeric_arrays_')
        if body.reference.kind == "asset_version":
            selection = body.reference.selection
        else:
            selection = body.reference.members[body.member_index].selection
        hdu = selection.hdu_index or 0
        if hdu != 0 or selection.kind != "whole_file":
            raise ApiError(422, "UNSUPPORTED_SELECTION", "该实时样本预览使用默认图像HDU，不支持任意HDU选择。", message_key='this_live_sample_preview_uses_the_default_image_hdu_arbitrary_hdu_selection')
        identity = json.dumps([str(item.asset_version_id), version.content_hash, stamp.st_size, stamp.st_mtime_ns, str(body.consumer_id), hdu, decoder_key, body.preview_max_edge])
        key = hashlib.sha256(identity.encode()).hexdigest()[:40]
        algorithm = "bundle-sample-1:" + key
        folder = settings.data_dir / "previews" / str(item.asset_version_id) / "media" / key
        row = session.scalar(select(Preview).where(Preview.asset_version_id == str(item.asset_version_id),
            Preview.hdu_index == hdu, Preview.size == "bundle-sample", Preview.algorithm_version == algorithm))
        if row is None:
            row = Preview(id=str(uuid4()), asset_version_id=str(item.asset_version_id), hdu_index=hdu,
                size="bundle-sample", algorithm_version=algorithm, width=0, height=0, mime_type="application/json",
                storage_path=(folder / "manifest.json").relative_to(settings.data_dir).as_posix(),
                display_parameters={"source_stamp": [stamp.st_size, stamp.st_mtime_ns]}, status="generating")
            session.add(row)
        else:
            row.status, row.error = "generating", None
        row_id = row.id
    guard = cache.hold(folder)
    guard.__enter__()
    sample = BundleSample(database, row_id, folder, folder / "sample.fit", guard)
    try:
        manifest_path = folder / "manifest.json"
        if manifest_path.is_file():
            cached = (folder / json.loads(manifest_path.read_text(encoding='utf-8'))['input']).resolve()
            if not cached.is_relative_to(folder.resolve()):
                raise ValueError('Cached sample escapes preview directory.')
            sample.path = cached
        check_cancel()
        cache.reserve(64 * 1024**2)
        if not sample.path.is_file():
            folder.mkdir(parents=True, exist_ok=True)
            if category != "fits":
                # The Bundle decodes the original and prepares a reusable sample.
                sample.path = path
                (folder / "manifest.json").write_text(json.dumps({"input": "sample.fit", "output": "result.png"}), encoding="utf-8")
                return sample
            pixels = read_fits_sample(path, hdu, body.preview_max_edge, check_cancel, colour_layout=colour_layout)
            header = fits.Header()
            if pixels.ndim == 3:
                pixels = np.moveaxis(pixels, -1, 0)
                header["CTYPE3"] = "RGB"
            temporary = folder / (str(uuid4()) + ".part")
            try:
                fits.writeto(temporary, pixels, header, overwrite=False)
                check_cancel()
                after = path.stat()
                if (stamp.st_size, stamp.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ApiError(409, "SOURCE_CHANGED", "准备线性预览时原件发生变化。", message_key='the_original_changed_while_preparing_the_linear_preview')
                temporary.replace(sample.path)
                cache.record(sample.path)
            finally:
                temporary.unlink(missing_ok=True)
        cache.write(folder / "manifest.json", json.dumps({"input": sample.path.name, "output": "result.png"}).encode())
        return sample
    except BaseException as exc:
        sample.close(exc)
        raise
