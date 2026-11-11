import math
from pathlib import Path
import numpy as np
from PIL import Image
from astrophotoflow.contracts.media import MediaSelection
from astrophotoflow.modules.data.formats.source import PixelSource


def read_fits_sample(path: Path, hdu_index: int, max_edge: int | None, checkpoint=lambda: None, *, colour_layout=None):
    source = PixelSource(
        path, "fits", MediaSelection(hdu_index=hdu_index), {"colour_layout": colour_layout}, path.parent, lambda _size: None, checkpoint
    )
    with source.pixels() as hdu:
        if colour_layout == "planar" and len(hdu.shape) == 3 and (hdu.shape[0] == 3):
            hdu.header["CTYPE3"] = "RGB"
            height, width = hdu.shape[1:]
        else:
            width, height = source.dimensions()
        step = max(1, math.ceil(max(width, height) / max_edge)) if max_edge else 1
        pixels = source.read_fits_region(hdu, (0, 0, width, height), step)
    return pixels


def direct_fits_image(
    path: Path, hdu_index: int | None, max_edge: int | None, *, colour_layout="planar", display_balance=None
) -> Image.Image:
    if hdu_index is None:
        from astrophotoflow.modules.data.formats.fits import inspect_fits

        hdu_index = inspect_fits(path, colour_layout=colour_layout)["selected_hdu"]
        if hdu_index is None:
            raise ValueError("输出没有可显示的图像HDU。")
    pixels = read_fits_sample(path, hdu_index, max_edge, colour_layout=colour_layout)
    if np.issubdtype(pixels.dtype, np.integer):
        values = pixels.astype(np.float32) / np.iinfo(pixels.dtype).max
    else:
        values = np.asarray(pixels, dtype=np.float32)
    values = np.nan_to_num(values, nan=0, posinf=1, neginf=0)
    if display_balance == "auto" and values.ndim == 3:
        from astrophotoflow.modules.data.formats.pixels import calculate_stretch

        values = values * np.asarray(calculate_stretch(values)["white_balance"])
    return Image.fromarray((np.clip(values, 0, 1) * 255).astype(np.uint8)).convert("RGB")
