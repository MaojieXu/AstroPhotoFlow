from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import numpy as np
from PIL import Image
from xisf import XISF
from astrophotoflow.modules.data.formats.fits import parsed_parameters
from astrophotoflow.modules.data.formats.pixels import calculate_stretch, display_pixels, render_stretch, sample_pixels, stretch_bounds

def read_xisf_pixels(path: Path) -> np.ndarray:
    reader = XISF(str(path))
    metadata = reader.get_images_metadata()[0]
    color_space = str(metadata.get('colorSpace', '')).casefold()
    channels = metadata['geometry'][2]
    array = reader.read_image(0, data_format='channels_last')
    if color_space == 'gray' and channels == 1:
        if array.ndim == 3 and array.shape[-1] == 1:
            array = array[..., 0]
        if array.ndim != 2:
            raise ValueError('XISF 灰度图像数据形状无效。')
    elif color_space == 'rgb' and channels == 3:
        if array.ndim != 3 or array.shape[-1] != 3:
            raise ValueError('XISF RGB 图像必须包含三个通道。')
    else:
        raise ValueError(f"不支持 XISF 色彩布局：{metadata.get('colorSpace', 'unknown')}")
    return array

def read_xisf_preview(path: Path, stretch: tuple[float, float] | None=None, max_edge: int=100, *, auto: bool=False, auto_stretch: dict | None=None) -> tuple[Image.Image, dict]:
    pixels = read_xisf_pixels(path)
    array = sample_pixels(pixels, max_edge * 2)
    if auto:
        recipe = auto_stretch if auto_stretch is not None else calculate_stretch(pixels)
        image = render_stretch(array, recipe)
        image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        return (image, {'auto_stretch': recipe, 'statistics': 'stratified-random-1'})
    low, high = stretch if stretch is not None else stretch_bounds(array)
    image = display_pixels(array, (low, high))
    image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    return (image, {'stretch_low': low, 'stretch_high': high})

def inspect_xisf(path: Path) -> dict:
    metadata = XISF(str(path)).get_images_metadata()[0]
    keywords = metadata.get('FITSKeywords', {})
    header = {keyword: entries[0]['value'] for keyword, entries in keywords.items() if entries}
    return {**parsed_parameters(header), 'xisf_fits_keywords': deepcopy(keywords), 'preview_layout': [metadata.get('colorSpace'), metadata.get('sampleFormat'), metadata['geometry'][2]]}
