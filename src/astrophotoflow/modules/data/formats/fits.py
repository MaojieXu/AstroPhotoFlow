from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from astropy.io import fits
from PIL import Image

from astrophotoflow.modules.data.formats.layout import CFA_PATTERNS, apply_colour_layout, bayer_demosaic, fits_image_kind, rgb_channel_first
from astrophotoflow.modules.data.formats.pixels import calculate_stretch, display_pixels, render_stretch, statistics_indices, stretch_bounds

PREVIEW_ALGORITHM_VERSION = "auto-stretch-2"

PARSER_VERSION = "fits-1"

def fits_json_value(value: Any):
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if np.isfinite(value) else str(value)
    return str(value)


def header_cards(header) -> list[dict[str, str]]:
    return [
        {"keyword": card.keyword, "value": fits_json_value(card.value), "comment": card.comment or "", "card": card.image}
        for card in header.cards
    ]


def header_classification(value: Any) -> dict:
    label = " ".join(str(value).strip().casefold().replace("_", " ").replace("-", " ").split())
    frame_class = None
    if label.startswith("master "):
        frame_class, label = "masterframe", label[7:]
    elif label in {"master", "masterframe"}:
        return {"frame_class": "masterframe", "frame_type": None}
    elif label in {"subframe", "video"}:
        return {"frame_class": label, "frame_type": None}
    if label.endswith(" frame"):
        frame_class, label = frame_class or "subframe", label[:-6]
    frame_type = {"light": "light", "bias": "bias", "dark": "dark", "flat": "flat",
                  "dark flat": "dark_flat", "flat dark": "dark_flat"}.get(label)
    return {"frame_class": frame_class, "frame_type": frame_type} if frame_type else {}


def parsed_parameters(header) -> dict[str, Any]:
    aliases = {
        "exposure_seconds": ("EXPTIME",),
        "integration_seconds": ("TOTEXP", "INTTIME"),
        "gain": ("GAIN",),
        "offset": ("OFFSET",),
        "sensor_temperature_setpoint_c": ("CCD-TEMP",),
        "binning_x": ("XBINNING",),
        "binning_y": ("YBINNING",),
        "iso": ("ISOSPEED", "ISO"),
        "cfa_pattern": ("BAYERPAT", "BAYERPATTERN"),
    }
    parsed = {}
    for target, keywords in aliases.items():
        for keyword in keywords:
            if keyword not in header:
                continue
            value = fits_json_value(header[keyword])
            if target == "cfa_pattern":
                value = str(value).strip().upper()
                if value not in CFA_PATTERNS | {"MONO", "XTRANS", "QUAD_BAYER"}:
                    continue
            if target in {
                "exposure_seconds", "integration_seconds", "gain", "offset",
                "sensor_temperature_c", "sensor_temperature_setpoint_c",
            }:
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    continue
                if not np.isfinite(value):
                    continue
            elif target in {"binning_x", "binning_y", "iso"}:
                try:
                    parsed_int = int(value)
                except (TypeError, ValueError):
                    continue
                if parsed_int <= 0:
                    continue
                value = parsed_int
            parsed[target] = value
            break
    if "FILTER" in header:
        parsed["filter_name"] = str(header["FILTER"])
    if "OBJECT" in header:
        parsed["target_name"] = str(header["OBJECT"])
    for keyword in ("IMAGETYP", "IMAGETYPE", "OBSTYPE", "FRAMETYP", "FRAME"):
        if keyword in header:
            parsed["classification"] = header_classification(header[keyword])
            parsed["file_classification_header"] = {
                "keyword": keyword,
                "value": fits_json_value(header[keyword]),
            }
            break
    return parsed


def inspect_fits(path: Path, cfa_override: str | None = None, *, colour_layout=None, verify_span=False) -> dict:
    hdus = []
    parsed = {}
    with fits.open(path, memmap=True, lazy_load_hdus=True) as file:
        for index, hdu in enumerate(file):
            info = hdu.fileinfo()
            if verify_span and info and info['datLoc'] + info['datSpan'] > path.stat().st_size:
                raise ValueError('FITS文件的完整数据范围尚未写完。')
            apply_colour_layout(hdu, colour_layout)
            header = hdu.header
            kind = fits_image_kind(hdu, cfa_override)
            shape = list(reversed([int(header.get(f"NAXIS{i}", 0)) for i in range(1, int(header.get("NAXIS", 0)) + 1)]))
            rows = {
                "hdu_index": index,
                "name": header.get("EXTNAME"),
                "hdu_type": type(hdu).__name__,
                "shape": shape,
                "bitpix": int(header["BITPIX"]) if "BITPIX" in header else None,
                "pixel_type": str(header["BITPIX"]) if "BITPIX" in header else None,
                "bscale": float(header["BSCALE"]) if "BSCALE" in header and np.isfinite(float(header["BSCALE"])) else None,
                "bzero": float(header["BZERO"]) if "BZERO" in header and np.isfinite(float(header["BZERO"])) else None,
                "bunit": str(header["BUNIT"]) if "BUNIT" in header else None,
                "header_cards": header_cards(header),
                "parser_version": PARSER_VERSION,
                "supported_kind": kind,
                "is_selected": False,
                "parse_error": None,
            }
            hdus.append(rows)
            if index == 0:
                parsed.update(parsed_parameters(header))
        selected = next((row for row in hdus if row["supported_kind"] is not None), None)
        if selected is not None:
            selected["is_selected"] = True
            parsed.update(parsed_parameters(file[selected["hdu_index"]].header))
    return {"hdus": hdus, "selected_hdu": selected["hdu_index"] if selected else None, "parsed_parameters": parsed}


def read_preview_pixels(path: Path, hdu_index: int, kind: str, parameters: dict, max_edge: int) -> tuple[np.ndarray, dict]:
    if kind in {"xtrans", "quad_bayer"}:
        raise ValueError(f"{kind} CFA 已登记；当前暂不支持其马赛克彩色预览。")
    with fits.open(path, memmap=False, lazy_load_hdus=True) as file:
        hdu = file[hdu_index]
        apply_colour_layout(hdu, parameters.get('colour_layout'))
        shape = tuple(int(value) for value in hdu.shape)
        if not shape or max(shape[-2:]) == 0:
            raise ValueError("所选 HDU 没有图像数据。")
        stride = max(1, (max(shape[-2:]) + max_edge - 1) // max_edge)
        if kind == "bayer" and stride % 2 == 0:
            stride += 1
        data = hdu.section
        if kind == "rgb":
            header = hdu.header
            if rgb_channel_first(header):
                sample = np.asarray(data[:, ::stride, :][:, :, ::stride], dtype=np.float32)
                sample = np.moveaxis(sample, 0, -1)
            else:
                sample = np.asarray(data[::stride, :, :][:, ::stride, :], dtype=np.float32)
        else:
            sample = np.asarray(data[::stride, :][:, ::stride], dtype=np.float32)
        if kind == "bayer":
            pattern = str(parameters.get("cfa_pattern") or hdu.header.get("BAYERPAT", hdu.header.get("BAYERPATTERN", ""))).upper()
            if pattern not in CFA_PATTERNS:
                raise ValueError("缺少已确认的 Bayer CFA 排列。")
            sample = bayer_demosaic(
                sample, pattern,
                int(hdu.header.get("XBAYROFF", 0)), int(hdu.header.get("YBAYROFF", 0)), stride,
            )
        return sample, {
            "downsample_stride": stride,
            "cfa_pattern": parameters.get("cfa_pattern") if kind == "bayer" else None,
            "algorithm": PREVIEW_ALGORITHM_VERSION,
        }


def read_stretch_pixels(path: Path, hdu_index: int, kind: str, parameters: dict, check_cancel=None) -> np.ndarray:
    if kind in {"xtrans", "quad_bayer"}:
        raise ValueError(f"{kind} CFA 已登记；当前暂不支持其马赛克彩色预览。")
    with fits.open(path, memmap=False, lazy_load_hdus=True) as file:
        hdu = file[hdu_index]
        apply_colour_layout(hdu, parameters.get('colour_layout'))
        planar = kind == "rgb" and rgb_channel_first(hdu.header)
        height, width = hdu.shape[-2:] if planar else hdu.shape[:2]
        cell = 2 if kind == "bayer" else 1
        rows, columns = statistics_indices(height // cell, width // cell)
        output = np.empty((*columns.shape, 3) if kind in {"rgb", "bayer"} else columns.shape, dtype=np.float32)
        if kind == "bayer":
            pattern = str(parameters.get("cfa_pattern") or hdu.header.get("BAYERPAT", hdu.header.get("BAYERPATTERN", ""))).upper()
            if pattern not in CFA_PATTERNS:
                raise ValueError("缺少已确认的 Bayer CFA 排列。")
            x_offset, y_offset = int(hdu.header.get("XBAYROFF", 0)), int(hdu.header.get("YBAYROFF", 0))
        for index, row in enumerate(rows):
            if check_cancel is not None:
                check_cancel()
            cols = columns[index]
            if planar:
                output[index] = np.asarray(hdu.section[:, row:row + 1, :], dtype=np.float32)[:, 0, cols].T
            elif kind == "rgb":
                output[index] = np.asarray(hdu.section[row:row + 1, :, :], dtype=np.float32)[0, cols]
            elif kind == "bayer":
                strip = np.asarray(hdu.section[row * 2:row * 2 + 2, :], dtype=np.float32)
                colors = {color: [] for color in "RGB"}
                for dy in range(2):
                    for dx in range(2):
                        color = pattern[((y_offset + dy) % 2) * 2 + ((x_offset + dx) % 2)]
                        colors[color].append(strip[dy, cols * 2 + dx])
                output[index] = np.stack([np.mean(colors[color], axis=0) for color in "RGB"], axis=-1)
            else:
                output[index] = np.asarray(hdu.section[row:row + 1, :], dtype=np.float32)[0, cols]
        return output


def create_preview(path: Path, hdu_index: int, kind: str, parameters: dict, max_edge: int, stretch: tuple[float, float] | None = None, *, auto: bool = False, auto_stretch: dict | None = None) -> tuple[Image.Image, dict]:
    sample, display_parameters = read_preview_pixels(path, hdu_index, kind, parameters, max_edge)
    if auto:
        recipe = auto_stretch if auto_stretch is not None else calculate_stretch(read_stretch_pixels(path, hdu_index, kind, parameters))
        image = render_stretch(sample, recipe)
        image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        return image, {**display_parameters, "auto_stretch": recipe, "statistics": "stratified-random-1"}
    low, high = stretch if stretch is not None else stretch_bounds(sample)
    image = display_pixels(sample, (low, high))
    image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    return image, {**display_parameters, "stretch": "percentile_1_99", "stretch_low": low, "stretch_high": high}
