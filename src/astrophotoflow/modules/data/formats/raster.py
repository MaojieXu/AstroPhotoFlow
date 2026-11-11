from __future__ import annotations
from pathlib import Path
import numpy as np
import png
import tifffile
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.formats.pixels import calculate_stretch, display_pixels, render_stretch, sample_pixels, stretch_bounds
register_heif_opener(thumbnails=False)

def read_raster(path):
    path = Path(path)
    if path.suffix.lower() in {'.tif', '.tiff'}:
        with tifffile.TiffFile(path) as file:
            if len(file.series) != 1:
                raise ApiError(422, 'UNSUPPORTED_IMAGE_LAYOUT', 'Multi-series TIFF is available as an original copy; select an image plane upstream before conversion.', message_key='science_tiff_series_selection_required')
            series = file.series[0]
            if series.axes in {'YX', 'YXS', 'YXC'}:
                array = series.asarray()
            elif series.axes == 'SYX' and series.shape[0] == 3 and (file.pages[0].photometric == 2):
                array = np.moveaxis(series.asarray(), 0, -1)
            else:
                raise ApiError(422, 'UNSUPPORTED_IMAGE_LAYOUT', 'TIFF axes do not describe one grayscale/RGB plane; keep the original complete container.', message_key='science_tiff_axes_invalid')
    elif path.suffix.lower() == '.png':
        width, height, rows, info = png.Reader(filename=str(path)).asDirect()
        dtype = np.uint16 if info['bitdepth'] > 8 else np.uint8
        array = np.empty((height, width * info['planes']), dtype=dtype)
        for index, row in enumerate(rows):
            array[index] = row
        array = array.reshape(height, width, info['planes'])
    else:
        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image)
            array = np.asarray(image if image.mode in {'I', 'F', 'I;16', 'I;16B', 'L', 'RGB'} else image.convert('RGB')).copy()
    if array.ndim == 3 and array.shape[-1] == 1:
        array = array[..., 0]
    return array

def valid_image(array):
    if array.ndim not in (2, 3) or (array.ndim == 3 and array.shape[-1] != 3) or (not all(array.shape)):
        raise ApiError(422, 'UNSUPPORTED_IMAGE_LAYOUT', 'Only nonempty grayscale or RGB image planes are supported; channels are never silently dropped.', message_key='science_image_plane_required')
    if array.dtype.kind not in 'uif':
        raise ApiError(422, 'UNSUPPORTED_PIXEL_TYPE', 'Only real integer or floating pixels are supported.', message_key='science_real_pixels_required')
    return array

def read_raster_preview(path: Path, stretch: tuple[float, float] | None=None, max_edge: int=100, *, auto: bool=False, auto_stretch: dict | None=None) -> tuple[Image.Image, dict | None]:
    if path.suffix.lower() in {'.tif', '.tiff', '.png'}:
        pixels = valid_image(read_raster(path))
        values = sample_pixels(pixels, max_edge * 2)
        if auto:
            recipe = auto_stretch if auto_stretch is not None else calculate_stretch(pixels)
            preview = render_stretch(values, recipe)
            display = {'auto_stretch': recipe, 'statistics': 'stratified-random-1'}
        elif pixels.dtype != np.uint8:
            low, high = stretch if stretch is not None else stretch_bounds(values)
            preview, display = (display_pixels(values, (low, high)), {'stretch_low': low, 'stretch_high': high})
        else:
            preview, display = (Image.fromarray(np.asarray(values, dtype=np.uint8)).convert('RGB'), None)
        preview.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        return (preview, display)
    with Image.open(path) as source:
        source.seek(0)
        image = ImageOps.exif_transpose(source)
        if auto:
            if image.mode not in {'L', 'I;16', 'I;16B', 'I;16L', 'I', 'F'}:
                image = image.convert('RGB')
            pixels = np.asarray(image)
            recipe = auto_stretch if auto_stretch is not None else calculate_stretch(pixels)
            preview = render_stretch(sample_pixels(pixels, max_edge * 2), recipe)
            preview.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
            return (preview, {'auto_stretch': recipe, 'statistics': 'stratified-random-1'})
        if image.mode in {'I;16', 'I;16B', 'I;16L', 'I', 'F'}:
            values = sample_pixels(np.asarray(image), max_edge * 2)
            low, high = stretch if stretch is not None else stretch_bounds(values)
            preview = display_pixels(values, (low, high))
            preview.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
            return (preview, {'stretch_low': low, 'stretch_high': high})
        return (image.convert('RGB').copy(), None)
