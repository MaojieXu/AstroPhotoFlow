from __future__ import annotations
import struct
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from PIL import Image
from astrophotoflow.modules.data.formats.layout import bayer_demosaic
from astrophotoflow.modules.data.formats.pixels import display_pixels, stretch_bounds
SER_HEADER_SIZE = 178
SER_BAYER = {8: 'RGGB', 9: 'GRBG', 10: 'GBRG', 11: 'BGGR'}

@dataclass(frozen=True, slots=True)
class SerInfo:
    color: int
    width: int
    height: int
    channels: int
    dtype: np.dtype
    count: int
    pixel_depth: int
    frame_bytes: int
    times: np.ndarray | None

def ser_info(path: Path) -> SerInfo:
    with path.open('rb') as stream:
        header = stream.read(SER_HEADER_SIZE)
    if len(header) != SER_HEADER_SIZE or header[:14] != b'LUCAM-RECORDER':
        raise ValueError('SER文件头无效。')
    _, color, endian, width, height, bits, count = struct.unpack('<7I', header[14:42])
    if not width or not height or (not count) or (not 1 <= bits <= 16) or (color not in {0, 100, 101, *SER_BAYER}):
        raise ValueError('SER尺寸、位深或颜色排列不受支持。')
    channels = 3 if color in (100, 101) else 1
    dtype = np.dtype('u1' if bits <= 8 else '<u2' if endian else '>u2')
    frame_bytes = width * height * channels * dtype.itemsize
    end = SER_HEADER_SIZE + frame_bytes * count
    if path.stat().st_size < end:
        raise ValueError('SER包含不完整帧。')
    times = None
    if path.stat().st_size >= end + count * 8:
        stamps = np.memmap(path, dtype='<u8', mode='r', offset=end, shape=(count,))
        if count > 1 and stamps[-1] > stamps[0] and np.all(stamps[1:] > stamps[:-1]):
            times = np.asarray((stamps - stamps[0]) / 10000000, dtype=np.float64)
    return SerInfo(color=color, width=width, height=height, channels=channels, dtype=dtype, count=count, pixel_depth=bits, frame_bytes=frame_bytes, times=times)

def read_ser_preview(path: Path, max_edge: int, stretch: tuple[float, float] | None=None) -> tuple[Image.Image, dict]:
    with path.open('rb') as stream:
        header = stream.read(SER_HEADER_SIZE)
    if len(header) != SER_HEADER_SIZE or header[:14] != b'LUCAM-RECORDER':
        raise ValueError('SER 文件头无效。')
    _, color_id, little_endian, width, height, bit_depth, frame_count = struct.unpack('<7I', header[14:42])
    if width < 1 or height < 1 or frame_count < 1 or (bit_depth < 1) or (bit_depth > 16):
        raise ValueError('SER 文件尺寸、位深或帧数无效。')
    if color_id not in {0, 100, 101, *SER_BAYER}:
        raise ValueError(f'SER ColorID {color_id} 暂不支持预览。')
    planes = 3 if color_id in {100, 101} else 1
    bytes_per_channel = 1 if bit_depth <= 8 else 2
    frame_bytes = width * height * planes * bytes_per_channel
    if path.stat().st_size < SER_HEADER_SIZE + frame_bytes:
        raise ValueError('SER 文件不包含完整的第一帧。')
    if bytes_per_channel == 1:
        dtype = np.dtype('u1')
    else:
        dtype = np.dtype('<u2' if little_endian else '>u2')
    shape = (height, width, planes) if planes == 3 else (height, width)
    frame = np.memmap(path, dtype=dtype, mode='r', offset=SER_HEADER_SIZE, shape=shape)
    stride = max(1, (max(width, height) + max_edge - 1) // max_edge)
    if color_id in SER_BAYER and stride % 2 == 0:
        stride += 1
    if color_id in {100, 101}:
        sample = np.asarray(frame[::stride, ::stride, :], dtype=np.float32)
        if color_id == 101:
            sample = sample[:, :, ::-1]
        pattern = None
    else:
        sample = np.asarray(frame[::stride, ::stride], dtype=np.float32)
        pattern = SER_BAYER.get(color_id)
        if pattern:
            sample = bayer_demosaic(sample, pattern, 0, 0, stride)
    low, high = stretch if stretch is not None else stretch_bounds(sample)
    image = display_pixels(sample, (low, high))
    image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    return (image, {'video_frame_index': 0, 'ser_color_id': color_id, 'cfa_pattern': pattern, 'algorithm': 'ser-first-frame-1', 'stretch_low': low, 'stretch_high': high})
