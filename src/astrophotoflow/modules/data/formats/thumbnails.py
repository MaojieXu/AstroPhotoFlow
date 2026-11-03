"""Small, automatically stretched image derivatives for the material library."""

from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from astrophotoflow.modules.data.formats.fits import read_preview_pixels, read_stretch_pixels
from astrophotoflow.modules.data.formats.pixels import calculate_stretch, render_stretch, sample_pixels
from astrophotoflow.modules.data.formats.raster import read_raster, valid_image
from astrophotoflow.modules.data.formats.raw import read_raw_preview
from astrophotoflow.modules.data.formats.xisf import read_xisf_pixels

THUMBNAIL_EDGE = 100
THUMBNAIL_ALGORITHM = "library-auto-mtf-1"


def _raster_pixels(path: Path) -> np.ndarray:
    if path.suffix.lower() in {".tif", ".tiff", ".png"}:
        return valid_image(read_raster(path))
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source)
        if image.mode not in {"L", "I;16", "I;16B", "I;16L", "I", "F"}:
            image = image.convert("RGB")
        return np.array(image)


def _samples(path: Path, category: str, hdu_index: int, kind: str | None,
             parameters: dict, *, statistics: bool) -> tuple[np.ndarray, np.ndarray | None]:
    if category == "fits":
        if kind not in {"mono", "bayer", "rgb"}:
            raise ValueError(f"Unsupported FITS preview layout: {kind!r}")
        pixels, _ = read_preview_pixels(path, hdu_index, kind, parameters, THUMBNAIL_EDGE * 2)
        sample = read_stretch_pixels(path, hdu_index, kind, parameters) if statistics else None
        return pixels, sample
    if category == "xisf":
        pixels = read_xisf_pixels(path)
    elif category == "image":
        pixels = _raster_pixels(path)
    elif category == "raw":
        pixels = np.asarray(read_raw_preview(path, THUMBNAIL_EDGE * 2))
    else:
        raise ValueError(f"Unsupported image format: {category!r}")
    return sample_pixels(pixels, THUMBNAIL_EDGE * 2), pixels if statistics else None


def render_thumbnail(path: Path, category: str, hdu_index: int, kind: str | None,
                     parameters: dict, *, recipe: dict | None = None) -> tuple[Image.Image, dict]:
    """Render one fixed image with its own or an explicitly supplied stretch."""
    pixels, sample = _samples(path, category, hdu_index, kind, parameters, statistics=recipe is None)
    stretch = calculate_stretch(sample) if recipe is None else recipe
    channels = 1 if pixels.ndim == 2 else pixels.shape[-1] if pixels.ndim == 3 else 0
    if channels not in {1, 3} or len(stretch.get("white_balance", [])) != channels:
        raise ValueError("Image channel layout is incompatible with the reference stretch")
    image = render_stretch(pixels, stretch)
    image.thumbnail((THUMBNAIL_EDGE, THUMBNAIL_EDGE), Image.Resampling.LANCZOS)
    return image, stretch
