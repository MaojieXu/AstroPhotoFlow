import hashlib
import json
import math
from pathlib import Path
from uuid import uuid4

import numpy as np
from astropy.io import fits
from PIL import Image
from sqlalchemy import select

from astrophotoflow.contracts.inputs import CanvasInspectRequest
from astrophotoflow.contracts.media import MediaSelection
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.canvas import inspect_canvas_data
from astrophotoflow.modules.data.media_sources import PixelSource
from astrophotoflow.modules.data.models import Preview, AssetVersion
from astrophotoflow.modules.data.previews import _library_version
from astrophotoflow.modules.data.science_inputs import _asset_path


def fits_sample(path: Path, hdu_index: int, max_edge: int, checkpoint=lambda: None, *, siril_output=False, colour_layout=None):
    source = PixelSource(path, "fits", MediaSelection(hdu_index=hdu_index), {'colour_layout': colour_layout}, path.parent,
                         lambda _size: None, checkpoint)
    with source.pixels() as hdu:
        if siril_output and len(hdu.shape) == 3 and hdu.shape[0] == 3:
            # Siril writes planar RGB without necessarily adding CTYPE3.
            # This modifies only the in-memory header, never the original file.
            hdu.header["CTYPE3"] = "RGB"
            height, width = hdu.shape[1:]
        else:
            width, height = source.dimensions()
        step = max(1, math.ceil(max(width, height) / max_edge))
        pixels = source._fits_region(hdu, (0, 0, width, height), step)
    return pixels


def direct_fits_image(path: Path, hdu_index: int | None, max_edge: int, *, colour_layout='planar') -> Image.Image:
    if hdu_index is None:
        from astrophotoflow.modules.data.fits_preview import inspect_fits
        hdu_index = inspect_fits(path, colour_layout=colour_layout)['selected_hdu']
        if hdu_index is None:
            raise ValueError('输出没有可显示的图像HDU。')
    pixels = fits_sample(path, hdu_index, max_edge, siril_output=colour_layout == 'planar', colour_layout=colour_layout)
    if np.issubdtype(pixels.dtype, np.integer):
        values = pixels.astype(np.float32) / np.iinfo(pixels.dtype).max
    else:
        values = np.asarray(pixels, dtype=np.float32)
    values = np.nan_to_num(values, nan=0, posinf=1, neginf=0)
    return Image.fromarray((np.clip(values, 0, 1) * 255).astype(np.uint8)).convert("RGB")


class SirilSample:
    def __init__(self, database, row_id, folder, path, guard):
        self.database, self.row_id, self.folder, self.path, self.guard = database, row_id, folder, path, guard

    def close(self, error=None):
        try:
            with self.database.write_session() as session:
                row = session.get(Preview, self.row_id)
                if row is not None:
                    row.status, row.error = ("failed", str(error)) if error is not None else ("available", None)
        finally:
            self.guard.__exit__(None, None, None)


def prepare_siril_sample(database, settings, cache, body, check_cancel, decoder_key='', colour_layout=None) -> SirilSample:
    item = inspect_canvas_data(database, CanvasInspectRequest(reference=body.reference, member_index=body.member_index))
    with database.write_session() as session:
        version = session.get(AssetVersion, _library_version(session, str(item.asset_id), str(item.asset_version_id)))
        path = _asset_path(settings, version)
        stamp = path.stat()
        if version.availability != "available" or version.byte_size != stamp.st_size:
            raise ApiError(409, "SOURCE_UNAVAILABLE", "原件尚未就绪或已经变化。")
        category = (version.scientific_metadata or {}).get("format")
        if category not in {"fits", "xisf", "image", "raw"}:
            raise ApiError(422, "UNSUPPORTED_SELECTION", "实时显示样本需要固定静态图像；视频和数值数组不能作为该预览输入。")
        if body.reference.kind == "asset_version":
            selection = body.reference.selection
        else:
            selection = body.reference.members[body.member_index].selection
        hdu = selection.hdu_index or 0
        if hdu != 0 or selection.kind != "whole_file":
            raise ApiError(422, "UNSUPPORTED_SELECTION", "该实时样本预览使用默认图像HDU，不支持任意HDU选择。")
        identity = json.dumps([str(item.asset_version_id), version.content_hash, stamp.st_size, stamp.st_mtime_ns, str(body.consumer_id), hdu, decoder_key])
        key = hashlib.sha256(identity.encode()).hexdigest()[:40]
        algorithm = "siril-live-1:" + key
        folder = settings.data_dir / "previews" / str(item.asset_version_id) / "media" / key
        row = session.scalar(select(Preview).where(Preview.asset_version_id == str(item.asset_version_id),
            Preview.hdu_index == hdu, Preview.size == "siril-live", Preview.algorithm_version == algorithm))
        if row is None:
            row = Preview(id=str(uuid4()), asset_version_id=str(item.asset_version_id), hdu_index=hdu,
                size="siril-live", algorithm_version=algorithm, width=0, height=0, mime_type="application/json",
                storage_path=(folder / "manifest.json").relative_to(settings.data_dir).as_posix(),
                display_parameters={"source_stamp": [stamp.st_size, stamp.st_mtime_ns]}, status="generating")
            session.add(row)
        else:
            row.status, row.error = "generating", None
        row_id = row.id
    guard = cache.hold(folder)
    guard.__enter__()
    sample = SirilSample(database, row_id, folder, folder / "linear.fit", guard)
    try:
        check_cancel()
        cache.reserve(64 * 1024**2)
        if not sample.path.is_file():
            folder.mkdir(parents=True, exist_ok=True)
            if category != "fits":
                # Siril decodes the original and prepares a reusable sample.
                sample.path = path
                (folder / "manifest.json").write_text(json.dumps({"input": "linear.fit", "output": "result.png"}), encoding="utf-8")
                return sample
            pixels = fits_sample(path, hdu, 1024, check_cancel, colour_layout=colour_layout)
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
                    raise ApiError(409, "SOURCE_CHANGED", "准备线性预览时原件发生变化。")
                temporary.replace(sample.path)
            finally:
                temporary.unlink(missing_ok=True)
        (folder / "manifest.json").write_text(json.dumps({"input": "linear.fit", "output": "result.png"}), encoding="utf-8")
        return sample
    except BaseException as exc:
        sample.close(exc)
        raise
