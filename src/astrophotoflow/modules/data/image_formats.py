"""Full-resolution grayscale/RGB codecs. Never use display JPEGs as input."""
from pathlib import Path
import numpy as np
from astropy.io import fits
from PIL import Image, ImageOps
import png
import tifffile
from xisf import XISF

from astrophotoflow.core.errors import ApiError
from .fits_preview import _rgb_channel_first

EXTENSIONS = {'fits': '.fits', 'xisf': '.xisf', 'tiff': '.tif', 'png': '.png', 'jpeg': '.jpg'}


def read_raster(path):
    path = Path(path)
    if path.suffix.lower() in {'.tif', '.tiff'}:
        with tifffile.TiffFile(path) as file:
            if len(file.series) != 1:
                raise ApiError(422, 'UNSUPPORTED_IMAGE_LAYOUT', 'Multi-series TIFF is available as an original copy; select an image plane upstream before conversion.')
            series = file.series[0]
            if series.axes in {'YX', 'YXS', 'YXC'}:
                array = series.asarray()
            elif series.axes == 'SYX' and series.shape[0] == 3 and file.pages[0].photometric == 2:
                array = np.moveaxis(series.asarray(), 0, -1)
            else:
                raise ApiError(422, 'UNSUPPORTED_IMAGE_LAYOUT', 'TIFF axes do not describe one grayscale/RGB plane; keep the original complete container.')
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
    if array.ndim not in (2, 3) or array.ndim == 3 and array.shape[-1] != 3 or not all(array.shape):
        raise ApiError(422, 'UNSUPPORTED_IMAGE_LAYOUT', 'Only nonempty grayscale or RGB image planes are supported; channels are never silently dropped.')
    if array.dtype.kind not in 'uif':
        raise ApiError(422, 'UNSUPPORTED_PIXEL_TYPE', 'Only real integer or floating pixels are supported.')
    return array


def read_display_image(path, category, selection, folder, metadata):
    """Use the viewer's full-resolution interpretation (including CFA) before applying its frozen tone recipe."""
    from .media_sources import PixelSource
    pixel_path, pixel_category = path, category
    if category == 'video' and Path(path).suffix.lower() != '.ser':
        if selection.frame_index is None and selection.media_time is None:
            raise ApiError(422, 'SELECTION_REQUIRED', 'Select an explicit video frame.')
        from .media_video import extract_frame
        pixel_path, _, _, _ = extract_frame(path, selection, folder, lambda size: None)
        pixel_category = 'frame'
    source = PixelSource(pixel_path, pixel_category, selection, {'colour_layout': (metadata or {}).get('colour_layout')}, folder, lambda size: None)
    width, height = source.dimensions()
    return valid_image(source.read((0, 0, width, height), 1))


def read_image(path, category, selection, folder):
    header = None
    if category == 'fits':
        with fits.open(path, memmap=False) as hdus:
            images = [index for index, hdu in enumerate(hdus) if isinstance(hdu, (fits.PrimaryHDU, fits.ImageHDU, fits.CompImageHDU)) and hdu.header.get('NAXIS', 0) >= 2]
            if selection.hdu_index is None and len(images) != 1:
                raise ApiError(422, 'SELECTION_REQUIRED', 'Choose an explicit image HDU before conversion.')
            index = selection.hdu_index if selection.hdu_index is not None else images[0]
            if index not in images:
                raise ApiError(422, 'SELECTION_REQUIRED', 'The selected HDU is not an image plane.')
            hdu = hdus[index]
            header = hdu.header.copy()
            array = np.array(hdu.data)
            if array.ndim == 3 and _rgb_channel_first(header):
                array = np.moveaxis(array, 0, -1)
    elif category == 'xisf':
        reader = XISF(str(path))
        if len(reader.get_images_metadata()) != 1:
            raise ApiError(422, 'UNSUPPORTED_CONVERSION', 'Multi-image XISF requires explicit upstream image selection; original copying preserves the entire container.')
        array = reader.read_image(0, data_format='channels_last')
        keywords = reader.get_images_metadata()[0].get('FITSKeywords', {})
        header = fits.Header()
        for key, values in keywords.items():
            if values:
                try: header[key] = (values[0]['value'], values[0].get('comment', ''))
                except (ValueError, TypeError): pass
    elif category in {'image', 'frame'}:
        array = np.load(path, mmap_mode='r', allow_pickle=False) if category == 'frame' else read_raster(path)
    elif category == 'video':
        if selection.frame_index is None and selection.media_time is None:
            raise ApiError(422, 'SELECTION_REQUIRED', 'Choose an explicit video frame before conversion.')
        if Path(path).suffix.lower() == '.ser':
            from .media_sources import PixelSource
            source = PixelSource(path, category, selection, {}, folder, lambda size: None)
            with source.pixels() as pixels: array = np.array(pixels)
        else:
            from .media_video import extract_frame
            frame, _, _, _ = extract_frame(path, selection, folder, lambda size: None)
            array = np.load(frame, mmap_mode='r', allow_pickle=False)
    elif category == 'numpy':
        from .media_sources import select_array
        if Path(path).suffix.lower() == '.npz':
            if selection.array_key is None:
                raise ApiError(422, 'SELECTION_REQUIRED', 'Choose an explicit NumPy array.')
            with np.load(path, allow_pickle=False) as archive: array = select_array(archive[selection.array_key], selection)
        else: array = select_array(np.load(path, mmap_mode='r', allow_pickle=False), selection)
    elif category == 'raw':
        raise ApiError(422, 'UNSUPPORTED_CONVERSION', 'RAW files can be copied in their original format. Decode/demosaic explicitly upstream before converting them; export never silently develops sensor data.')
    else:
        raise ApiError(422, 'UNSUPPORTED_CONVERSION', 'This complete file can be copied in its original format, but cannot be converted to an image.')
    if array.ndim == 3 and array.shape[-1] == 1:
        array = array[..., 0]
    return valid_image(array), header


def convert_pixels(array, settings, target, checkpoint=lambda: None):
    dtype = np.dtype(settings.precision)
    output = np.lib.format.open_memmap(target, mode='w+', dtype=dtype, shape=array.shape)
    rows = max(1, (8 * 1024**2) // max(1, int(np.prod(array.shape[1:])) * 8))
    for start in range(0, len(array), rows):
        checkpoint()
        values = np.asarray(array[start:start + rows])
        finite = np.isfinite(values)
        if settings.conversion in {'normalize', 'display'}:
            if settings.auto_stretch is not None and settings.conversion == 'display':
                from .auto_stretch import stretch_values
                if len(settings.auto_stretch.white_balance) not in {1, 3 if values.ndim == 3 else 1}:
                    raise ApiError(422, 'DISPLAY_RECIPE_MISMATCH', 'The frozen display recipe does not match this member\'s grayscale/RGB channels.')
                values = stretch_values(values, settings.auto_stretch.model_dump())
            else:
                low, high = settings.value_range if settings.conversion == 'normalize' else settings.display_range
                values = np.clip((values.astype(np.float64) - low) / (high - low), 0, 1)
            if not finite.all():
                if settings.conversion != 'display':
                    raise ApiError(422, 'NONFINITE_PIXELS', 'Normalization contains NaN/Inf; use floating output or explicitly choose display rendering.')
                values = np.where(finite, values, 0)
            if dtype.kind in 'ui':
                values = np.rint(values * np.iinfo(dtype).max)
        if dtype.kind in 'ui':
            bounds = np.iinfo(dtype)
            if not np.isfinite(values).all() or values.min() < bounds.min or values.max() > bounds.max:
                raise ApiError(422, 'CONVERSION_REQUIRES_DECISION', 'Pixel values do not fit the selected integer range. Choose floating output or an explicit normalization/display range.')
            if settings.conversion == 'round': values = np.rint(values)
            elif np.any(values != np.rint(values)):
                raise ApiError(422, 'CONVERSION_REQUIRES_DECISION', 'Fractional values require explicit rounding (nearest, ties to even), normalization or display rendering.')
        with np.errstate(over='ignore', invalid='ignore'):
            converted = values.astype(dtype)
        if dtype.kind == 'f' and np.any(np.isfinite(values) & ~np.isfinite(converted)):
            raise ApiError(422, 'CONVERSION_REQUIRES_DECISION', 'Finite values overflow the selected floating precision.')
        output[start:start + rows] = converted
    output.flush()
    return output


def write_image(path, array, header, settings):
    valid_image(array)
    header = header.copy() if header is not None else fits.Header()
    for key in ('BSCALE', 'BZERO', 'CHECKSUM', 'DATASUM'):
        header.remove(key, ignore_missing=True, remove_all=True)
    if settings.conversion in {'normalize', 'display'}:
        header.remove('BUNIT', ignore_missing=True, remove_all=True)
    if array.ndim == 3:
        for key in ('BAYERPAT', 'BAYERPATTERN', 'XBAYROFF', 'YBAYROFF'):
            header.remove(key, ignore_missing=True, remove_all=True)
    header.add_history(f'AstroPhotoFlow export: {settings.format}/{settings.precision}/{settings.conversion}')
    if settings.format == 'fits':
        if array.ndim == 3:
            header['CTYPE3'] = 'RGB'
            array = np.moveaxis(array, -1, 0)
        fits.PrimaryHDU(array, header=header).writeto(path, overwrite=False)
    elif settings.format == 'xisf':
        keywords = {}
        for card in header.cards:
            if card.keyword and card.keyword not in {'SIMPLE', 'BITPIX', 'EXTEND'} and not card.keyword.startswith('NAXIS'):
                keywords.setdefault(card.keyword, []).append({'value': str(card.value), 'comment': card.comment})
        XISF.write(str(path), array[..., None] if array.ndim == 2 else array,
                   image_metadata={'FITSKeywords': keywords}, codec=None)
    elif settings.format == 'tiff':
        tifffile.imwrite(path, array, photometric='rgb' if array.ndim == 3 else 'minisblack',
                         metadata={'apf_export': settings.model_dump(mode='json'), 'fits_header': header.tostring()}, bigtiff=array.nbytes >= 2**32 - 2**25)
    elif settings.format == 'png':
        height, width = array.shape[:2]
        with Path(path).open('xb') as stream:
            writer = png.Writer(width, height, greyscale=array.ndim == 2, bitdepth=array.dtype.itemsize * 8)
            writer.write(stream, (row.reshape(-1).tolist() for row in array))
    else:
        Image.fromarray(np.asarray(array)).save(path, format='JPEG', quality=settings.jpeg_quality)


def verify_image(path, original, settings):
    if settings.format == 'fits':
        with fits.open(path, memmap=False) as hdus:
            restored = hdus[0].data
            if restored.ndim == 3: restored = np.moveaxis(restored, 0, -1)
    elif settings.format == 'xisf':
        restored = XISF(str(path)).read_image(0, data_format='channels_last')
        if restored.ndim == 3 and restored.shape[-1] == 1: restored = restored[..., 0]
    else: restored = read_raster(path)
    expected = np.dtype(settings.precision)
    if restored.shape != original.shape or (restored.dtype.kind, restored.dtype.itemsize) != (expected.kind, expected.itemsize):
        raise ApiError(500, 'EXPORT_VERIFICATION_FAILED', 'Encoded dimensions, channels or precision do not match the request.')
    if settings.format != 'jpeg' and not np.array_equal(restored, original, equal_nan=True):
        raise ApiError(500, 'EXPORT_VERIFICATION_FAILED', 'Encoded pixel values do not match the requested conversion.')
    return {'shape': list(restored.shape), 'precision': settings.precision}
