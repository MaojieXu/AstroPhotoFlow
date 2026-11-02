from __future__ import annotations

from contextlib import contextmanager

import numpy as np
import rawpy
from astropy.io import fits
from PIL import Image, ImageOps
from xisf import XISF

from astrophotoflow.modules.data.formats import raster
from astrophotoflow.modules.data.formats.fits import read_stretch_pixels
from astrophotoflow.modules.data.formats.layout import bayer_demosaic, rgb_channel_first
from astrophotoflow.modules.data.formats.numpy import numpy_arrays, select_array
from astrophotoflow.modules.data.formats.pixels import calculate_stretch, render_stretch
from astrophotoflow.modules.data.formats.ser import SER_BAYER, SER_HEADER_SIZE, ser_info

FITS_STRIP_BYTES = 8 * 1024**2

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
        elif self.path.suffix.lower() in {'.png', '.tif', '.tiff'}:
            array = raster.read_raster(self.path)
            self.linear = array.dtype != np.uint8
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
                from astrophotoflow.modules.data.formats.layout import apply_colour_layout
                apply_colour_layout(hdu, self.parameters.get('colour_layout'))
                shape = hdu.shape
                if shape is None or len(shape) < 2:
                    raise ValueError("所选HDU不是二维图像。")
                yield hdu
        elif self.path.suffix.lower() == ".ser":
            info = ser_info(self.path)
            index = self.selection.frame_index or 0
            if index >= info.count:
                raise ValueError("SER帧编号超出范围。")
            shape = (info.height, info.width, info.channels) if info.channels == 3 else (info.height, info.width)
            pixels = np.memmap(self.path, dtype=info.dtype, mode="r", offset=SER_HEADER_SIZE + index * info.frame_bytes, shape=shape)
            self.cfa = SER_BAYER.get(info.color)
            yield pixels[..., ::-1] if info.color == 101 else pixels
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
                if len(shape) == 3 and (rgb_channel_first(data.header) and shape[0] == 3):
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

    def read_fits_region(self, hdu, box, step):
        x0, y0, x1, y1 = box
        planar = len(hdu.shape) == 3 and rgb_channel_first(hdu.header)
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
                array = self.read_fits_region(data, box, step)
                pattern = str(self.parameters.get("cfa_pattern") or data.header.get("BAYERPAT", "")).upper()
                ox, oy = int(data.header.get("XBAYROFF", 0)), int(data.header.get("YBAYROFF", 0))
            else:
                array = np.asarray(data[y0:y1:step, x0:x1:step])
                ox = oy = 0
            self.checkpoint()
            self.direct_max = np.iinfo(array.dtype).max if np.issubdtype(array.dtype, np.integer) else 1.0
            if pattern in {"RGGB", "BGGR", "GRBG", "GBRG"} and array.ndim == 2:
                array = bayer_demosaic(array, pattern, x0 + ox, y0 + oy, step)
            return array

    def stretch(self, *, balance_rgb=True):
        if self.category == "fits":
            with fits.open(self.path, memmap=False, lazy_load_hdus=True) as file:
                hdu = file[self.selection.hdu_index or 0]
                from astrophotoflow.modules.data.formats.layout import apply_colour_layout
                apply_colour_layout(hdu, self.parameters.get('colour_layout'))
                kind = "rgb" if len(hdu.shape) == 3 else "bayer" if str(self.parameters.get("cfa_pattern") or hdu.header.get("BAYERPAT", "")).upper() in {"RGGB", "BGGR", "GRBG", "GBRG"} else "mono"
            return calculate_stretch(read_stretch_pixels(self.path, self.selection.hdu_index or 0, kind, self.parameters, self.check_cancel), balance_rgb=balance_rgb)
        with self.pixels() as data:
            if self.cfa:
                from astrophotoflow.modules.data.formats.pixels import sample_statistics
                return calculate_stretch(sample_statistics(data), balance_rgb=balance_rgb)
            return calculate_stretch(data, balance_rgb=balance_rgb)

    def render(self, pixels, recipe):
        if 'display_white_balance' in recipe:
            pixels = np.asarray(pixels, dtype=np.float32) * np.asarray(recipe['display_white_balance'], dtype=np.float32)
        if recipe.get('direct'):
            from astrophotoflow.modules.data.formats.pixels import display_pixels
            return display_pixels(pixels, (0, self.direct_max))
        if recipe.get("auto_stretch"):
            return render_stretch(pixels, recipe["auto_stretch"])
        if "stretch_low" in recipe:
            from astrophotoflow.modules.data.formats.pixels import display_pixels
            return display_pixels(pixels, (recipe["stretch_low"], recipe["stretch_high"]))
        return Image.fromarray(np.asarray(np.clip(pixels, 0, 255), dtype=np.uint8)).convert("RGB")
