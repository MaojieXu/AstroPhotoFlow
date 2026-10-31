from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import zipfile

from astropy.io import fits
import numpy as np
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener
import rawpy
from xisf import XISF

from astrophotoflow.contracts.media import MediaArray, MediaSelection
from astrophotoflow.modules.data.auto_stretch import calculate_stretch, render_stretch
from astrophotoflow.modules.data.fits_preview import _bayer_demosaic, _rgb_channel_first, read_stretch_pixels
from astrophotoflow.modules.data.video_preview import SER_HEADER_SIZE, SER_BAYER
import struct

register_heif_opener(thumbnails=False)

FITS_STRIP_BYTES = 8 * 1024**2


def array_header(stream):
    version = np.lib.format.read_magic(stream)
    if version == (1, 0):
        return np.lib.format.read_array_header_1_0(stream)
    return np.lib.format.read_array_header_2_0(stream)


def numpy_arrays(path: Path) -> list[MediaArray]:
    def describe(stream, key):
        shape, _, dtype = array_header(stream)
        return MediaArray(key=key, shape=list(shape), dtype=str(dtype), numeric=dtype.kind in "buif")
    if path.suffix.lower() == ".npz":
        with zipfile.ZipFile(path) as archive:
            return [describe(archive.open(name), name[:-4]) for name in archive.namelist() if name.endswith(".npy")]
    with path.open("rb") as stream:
        return [describe(stream, "array")]


def select_array(array, selection: MediaSelection):
    if array.dtype.kind not in "buif":
        raise ValueError("所选数组不是可显示的实数／布尔图像。")
    if array.ndim < 2:
        raise ValueError("所选数组没有二维图像平面。")
    if selection.x_axis is None and selection.y_axis is None:
        if array.ndim == 2:
            axes = (1, 0, None)
        elif array.ndim == 3 and array.shape[-1] in (1, 3, 4):
            axes = (1, 0, 2)
        else:
            raise ValueError("请选择水平轴、垂直轴和其他维度的切片。")
    else:
        axes = (selection.x_axis, selection.y_axis, selection.channel_axis)
    x, y, channel = axes
    if x is None or y is None or max(axis for axis in axes if axis is not None) >= array.ndim:
        raise ValueError("显示轴超出所选数组维度。")
    if channel is not None and array.shape[channel] not in (1, 3, 4):
        raise ValueError("通道轴必须包含1、3或4个通道。")
    if any(int(axis) >= array.ndim or int(axis) in axes for axis in selection.slices):
        raise ValueError("切片轴必须是有效的非显示维度。")
    retained = [axis for axis in range(array.ndim) if axis in axes]
    index = []
    for axis, size in enumerate(array.shape):
        value = selection.slices.get(str(axis), 0)
        if axis in axes:
            index.append(slice(None))
        elif value >= size:
            raise ValueError("切片索引超出数组范围。")
        else:
            index.append(value)
    result = array[tuple(index)]
    result = np.transpose(result, [retained.index(axis) for axis in (y, x, channel) if axis is not None])
    if channel is not None:
        result = result[..., 0] if result.shape[-1] == 1 else result[..., :3]
    return result


def ser_info(path):
    with path.open("rb") as stream:
        header = stream.read(SER_HEADER_SIZE)
    if len(header) != SER_HEADER_SIZE or header[:14] != b"LUCAM-RECORDER":
        raise ValueError("SER文件头无效。")
    _, color, endian, width, height, bits, count = struct.unpack("<7I", header[14:42])
    if not width or not height or not count or not 1 <= bits <= 16 or color not in {0, 100, 101, *SER_BAYER}:
        raise ValueError("SER尺寸、位深或颜色排列不受支持。")
    channels = 3 if color in (100, 101) else 1
    dtype = np.dtype("u1" if bits <= 8 else "<u2" if endian else ">u2")
    frame_bytes = width * height * channels * dtype.itemsize
    end = SER_HEADER_SIZE + frame_bytes * count
    if path.stat().st_size < end:
        raise ValueError("SER包含不完整帧。")
    times = None
    if path.stat().st_size >= end + count * 8:
        stamps = np.memmap(path, dtype="<u8", mode="r", offset=end, shape=(count,))
        if count > 1 and stamps[-1] > stamps[0] and np.all(stamps[1:] > stamps[:-1]):
            times = np.asarray((stamps - stamps[0]) / 10_000_000, dtype=np.float64)
    return dict(color=color, width=width, height=height, channels=channels, dtype=dtype,
                count=count, pixel_depth=bits, frame_bytes=frame_bytes, times=times)


class PixelSource:
    def __init__(self, path, category, selection, parameters, folder, reserve, check_cancel=None):
        self.path, self.category, self.selection = path, category, selection
        self.parameters, self.folder, self.reserve = parameters, folder, reserve
        self.arrays = numpy_arrays(path) if category == "numpy" else []
        self.shape = None
        self.cfa = str(parameters.get("cfa_pattern") or "").upper() if category in {"fits", "xisf"} else None
        self.linear = category in {"fits", "xisf", "numpy"} or path.suffix.lower() == ".ser"
        self.check_cancel = check_cancel

    def checkpoint(self):
        if self.check_cancel is not None:
            self.check_cancel()

    def _decoded(self):
        self.checkpoint()
        cached = self.folder / "pixels.npy"
        if cached.is_file():
            return np.load(cached, mmap_mode="r", allow_pickle=False)
        if self.category == "xisf":
            reader = XISF(str(self.path))
            metadata = reader.get_images_metadata()[0]
            self.reserve(int(np.prod(metadata["geometry"])) * np.dtype(metadata["dtype"]).itemsize + 256)
            array = reader.read_image(0, data_format="channels_last")
            if array.ndim == 3 and array.shape[-1] == 1:
                array = array[..., 0]
        elif self.category == "raw":
            with rawpy.imread(str(self.path)) as raw:
                self.reserve(raw.sizes.width * raw.sizes.height * 3 + 256)
                array = raw.postprocess(half_size=False, output_bps=8, output_color=rawpy.ColorSpace.sRGB)
        elif self.category == "numpy":
            descriptor = next(array for array in self.arrays if array.key == self.selection.array_key)
            self.reserve(int(np.prod(descriptor.shape)) * np.dtype(descriptor.dtype).itemsize + 256)
            with np.load(self.path, allow_pickle=False) as archive:
                array = archive[self.selection.array_key]
        else:
            with Image.open(self.path) as image:
                pixel_bytes = 2 if image.mode.startswith("I;16") else 4 if image.mode in {"I", "F"} else 3
                self.reserve(image.width * image.height * pixel_bytes + 256)
                image = ImageOps.exif_transpose(image)
                array = np.asarray(image if image.mode in {"I", "F", "I;16", "I;16B"} else image.convert("RGB"))
                self.linear = array.dtype != np.uint8
        self.checkpoint()
        self.reserve(array.nbytes + 256)
        part = cached.with_suffix(".part")
        with part.open("wb") as stream:
            np.save(stream, array, allow_pickle=False)
        part.replace(cached)
        return np.load(cached, mmap_mode="r", allow_pickle=False)

    @contextmanager
    def pixels(self):
        if self.category == "fits":
            with fits.open(self.path, memmap=False, lazy_load_hdus=True) as file:
                hdu = file[self.selection.hdu_index or 0]
                from astrophotoflow.modules.data.fits_preview import apply_colour_layout
                apply_colour_layout(hdu, self.parameters.get('colour_layout'))
                shape = hdu.shape
                if shape is None or len(shape) < 2:
                    raise ValueError("所选HDU不是二维图像。")
                yield hdu
        elif self.path.suffix.lower() == ".ser":
            info = ser_info(self.path)
            index = self.selection.frame_index or 0
            if index >= info["count"]:
                raise ValueError("SER帧编号超出范围。")
            shape = (info["height"], info["width"], info["channels"]) if info["channels"] == 3 else (info["height"], info["width"])
            pixels = np.memmap(self.path, dtype=info["dtype"], mode="r", offset=SER_HEADER_SIZE + index * info["frame_bytes"], shape=shape)
            self.cfa = SER_BAYER.get(info["color"])
            yield pixels[..., ::-1] if info["color"] == 101 else pixels
        elif self.category == "frame":
            yield np.load(self.path, mmap_mode="r", allow_pickle=False)
        elif self.category == "numpy" and self.path.suffix.lower() == ".npy":
            yield select_array(np.load(self.path, mmap_mode="r", allow_pickle=False), self.selection)
        else:
            array = self._decoded()
            yield select_array(array, self.selection) if self.category == "numpy" else array

    def dimensions(self):
        self.checkpoint()
        with self.pixels() as data:
            if self.category == "fits":
                self.cfa = str(self.parameters.get("cfa_pattern") or data.header.get("BAYERPAT", "")).upper()
                shape = data.shape
                if len(shape) == 3 and (_rgb_channel_first(data.header) and shape[0] == 3):
                    shape = shape[1:]
                elif len(shape) == 3 and shape[-1] == 3:
                    shape = shape[:2]
                elif len(shape) != 2:
                    raise ValueError("当前HDU没有受支持的二维灰度或RGB布局。")
            else:
                shape = data.shape
                if self.category == "image":
                    self.linear = data.dtype != np.uint8
                if len(shape) not in (2, 3) or len(shape) == 3 and shape[-1] != 3:
                    raise ValueError("当前图像没有二维灰度或RGB布局。")
            self.shape = (int(shape[0]), int(shape[1]))
            if not min(self.shape):
                raise ValueError("图像平面为空。")
            return self.shape[1], self.shape[0]

    def _fits_region(self, hdu, box, step):
        x0, y0, x1, y1 = box
        planar = len(hdu.shape) == 3 and _rgb_channel_first(hdu.header)
        channels = 3 if len(hdu.shape) == 3 else 1
        width = hdu.shape[-1] if planar else hdu.shape[1]
        sample_bytes = max(8, abs(hdu.header["BITPIX"]) // 8)
        row_bytes = width * sample_bytes * (channels if not planar else 1)
        strip_rows = max(1, FITS_STRIP_BYTES // row_bytes)
        output = None
        for channel in range(channels if planar else 1):
            top = y0
            while top < y1:
                self.checkpoint()
                bottom = min(top + strip_rows, y1)
                if planar:
                    strip = np.asarray(hdu.section[channel, top:bottom, :])
                elif channels == 3:
                    strip = np.asarray(hdu.section[top:bottom, :, :])
                else:
                    strip = np.asarray(hdu.section[top:bottom, :])
                self.checkpoint()
                sampled = strip[::step, x0:x1:step]
                if output is None:
                    shape = ((y1 - y0 + step - 1) // step, (x1 - x0 + step - 1) // step)
                    output = np.empty((*shape, channels) if channels == 3 else shape, dtype=sampled.dtype)
                row = (top - y0) // step
                if planar:
                    output[row:row + len(sampled), :, channel] = sampled
                else:
                    output[row:row + len(sampled)] = sampled
                top += len(sampled) * step
                del sampled, strip
        return output

    def read(self, box, step=1):
        self.checkpoint()
        x0, y0, x1, y1 = box
        with self.pixels() as data:
            pattern = self.cfa
            if self.category == "fits":
                array = self._fits_region(data, box, step)
                pattern = str(self.parameters.get("cfa_pattern") or data.header.get("BAYERPAT", "")).upper()
                ox, oy = int(data.header.get("XBAYROFF", 0)), int(data.header.get("YBAYROFF", 0))
            else:
                array = np.asarray(data[y0:y1:step, x0:x1:step])
                ox = oy = 0
            self.checkpoint()
            self.direct_max = np.iinfo(array.dtype).max if np.issubdtype(array.dtype, np.integer) else 1.0
            if pattern in {"RGGB", "BGGR", "GRBG", "GBRG"} and array.ndim == 2:
                array = _bayer_demosaic(array, pattern, x0 + ox, y0 + oy, step)
            return array

    def stretch(self, *, balance_rgb=True):
        if self.category == "fits":
            with fits.open(self.path, memmap=False, lazy_load_hdus=True) as file:
                hdu = file[self.selection.hdu_index or 0]
                from astrophotoflow.modules.data.fits_preview import apply_colour_layout
                apply_colour_layout(hdu, self.parameters.get('colour_layout'))
                kind = "rgb" if len(hdu.shape) == 3 else "bayer" if str(self.parameters.get("cfa_pattern") or hdu.header.get("BAYERPAT", "")).upper() in {"RGGB", "BGGR", "GRBG", "GBRG"} else "mono"
            return calculate_stretch(read_stretch_pixels(self.path, self.selection.hdu_index or 0, kind, self.parameters, self.check_cancel), balance_rgb=balance_rgb)
        with self.pixels() as data:
            if self.cfa:
                from astrophotoflow.modules.data.auto_stretch import sample_statistics
                return calculate_stretch(sample_statistics(data), balance_rgb=balance_rgb)
            return calculate_stretch(data, balance_rgb=balance_rgb)

    def render(self, pixels, recipe):
        if 'display_white_balance' in recipe:
            pixels = np.asarray(pixels, dtype=np.float32) * np.asarray(recipe['display_white_balance'], dtype=np.float32)
        if recipe.get('direct'):
            from astrophotoflow.modules.data.fits_preview import _display
            return _display(pixels, (0, self.direct_max))
        if recipe.get("auto_stretch"):
            return render_stretch(pixels, recipe["auto_stretch"])
        if "stretch_low" in recipe:
            from astrophotoflow.modules.data.fits_preview import _display
            return _display(pixels, (recipe["stretch_low"], recipe["stretch_high"]))
        return Image.fromarray(np.asarray(np.clip(pixels, 0, 255), dtype=np.uint8)).convert("RGB")
