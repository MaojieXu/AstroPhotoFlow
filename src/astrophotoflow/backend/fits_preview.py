from __future__ import annotations
from pathlib import Path
from typing import Any

import numpy as np
from astropy.io import fits
from PIL import Image

PARSER_VERSION = "fits-1"
PREVIEW_ALGORITHM_VERSION = "auto-stretch-2"
CFA_PATTERNS = {"RGGB", "BGGR", "GRBG", "GBRG"}


def _json_value(value: Any):
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if np.isfinite(value) else str(value)
    return str(value)


def _image_kind(hdu, cfa_override: str | None = None) -> str | None:
    if not hdu.is_image:
        return None
    header = hdu.header
    ndim = int(header.get("NAXIS", 0))
    if ndim == 2:
        if cfa_override == "MONO":
            return "mono"
        if cfa_override == "XTRANS":
            return "xtrans"
        if cfa_override == "QUAD_BAYER":
            return "quad_bayer"
        if cfa_override in CFA_PATTERNS:
            return "bayer"
        pattern = str(header.get("BAYERPAT", header.get("BAYERPATTERN", ""))).upper()
        if pattern == "XTRANS":
            return "xtrans"
        if pattern in {"QUAD_BAYER", "QUADBAYER"}:
            return "quad_bayer"
        return "bayer" if pattern in CFA_PATTERNS or cfa_override in CFA_PATTERNS else "mono"
    if ndim == 3:
        if _rgb_channel_first(header):
            return "rgb"
        axis1 = str(header.get("CTYPE1", "")).strip().upper()
        if int(header.get("NAXIS1", 0)) == 3 and axis1 in {"RGB", "COLOR"}:
            return "rgb"
    return None


def _rgb_channel_first(header) -> bool:
    if int(header.get("NAXIS3", 0)) != 3:
        return False
    axis3 = str(header.get("CTYPE3", "")).strip().upper()
    if axis3 in {"RGB", "COLOR"}:
        return True
    return (
        not axis3
        and (
            str(header.get("PROGRAM", "")).strip().upper().startswith("PIXINSIGHT ")
            or (
                str(header.get("CTYPE1", "")).strip().upper().startswith("RA")
                and str(header.get("CTYPE2", "")).strip().upper().startswith("DEC")
            )
        )
    )


def _header_cards(header) -> list[dict[str, str]]:
    return [
        {"keyword": card.keyword, "value": _json_value(card.value), "comment": card.comment or "", "card": card.image}
        for card in header.cards
    ]


def _header_classification(value: Any) -> dict:
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


def _parsed_parameters(header) -> dict[str, Any]:
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
            value = _json_value(header[keyword])
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
            parsed["classification"] = _header_classification(header[keyword])
            parsed["file_classification_header"] = {
                "keyword": keyword,
                "value": _json_value(header[keyword]),
            }
            break
    return parsed


def inspect_fits(path: Path, cfa_override: str | None = None) -> dict:
    hdus = []
    parsed = {}
    with fits.open(path, memmap=True, lazy_load_hdus=True) as file:
        for index, hdu in enumerate(file):
            header = hdu.header
            kind = _image_kind(hdu, cfa_override)
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
                "header_cards": _header_cards(header),
                "parser_version": PARSER_VERSION,
                "supported_kind": kind,
                "is_selected": False,
                "parse_error": None,
            }
            hdus.append(rows)
            if index == 0:
                parsed.update(_parsed_parameters(header))
        selected = next((row for row in hdus if row["supported_kind"] is not None), None)
        if selected is not None:
            selected["is_selected"] = True
            parsed.update(_parsed_parameters(file[selected["hdu_index"]].header))
    return {"hdus": hdus, "selected_hdu": selected["hdu_index"] if selected else None, "parsed_parameters": parsed}


def _bayer_demosaic(mosaic: np.ndarray, pattern: str, x_offset: int, y_offset: int, stride: int) -> np.ndarray:
    rows = [[pattern[((y_offset + y * stride) % 2) * 2 + ((x_offset + x * stride) % 2)] for x in range(2)] for y in range(2)]
    height, width = mosaic.shape
    yy, xx = np.indices((height, width))
    output = np.empty((height, width, 3), dtype=np.float32)
    padded = np.pad(mosaic.astype(np.float32), 2, mode="reflect")
    for channel, color in enumerate(("R", "G", "B")):
        mask = np.fromfunction(lambda y, x: np.asarray(rows)[y.astype(int) % 2, x.astype(int) % 2] == color, (height, width), dtype=int)
        padded_mask = np.pad(mask, 2, mode="constant", constant_values=False)
        values = np.zeros((height, width), dtype=np.float32)
        counts = np.zeros((height, width), dtype=np.float32)
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                source = padded[2 + dy:2 + dy + height, 2 + dx:2 + dx + width]
                source_mask = padded_mask[2 + dy:2 + dy + height, 2 + dx:2 + dx + width]
                valid = source_mask
                values += source * valid
                counts += valid
        output[:, :, channel] = np.divide(values, counts, out=np.zeros_like(values), where=counts > 0)
    return output


def stretch_bounds(array: np.ndarray) -> tuple[float, float]:
    finite = np.asarray(array, dtype=np.float32)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        raise ValueError("所选 HDU 没有有效像素。")
    low, high = (float(value) for value in np.percentile(finite, (1, 99)))
    return low, high if high > low else low + 1.0


def _display(array: np.ndarray, stretch: tuple[float, float] | None = None) -> Image.Image:
    pixels = np.asarray(array, dtype=np.float32)
    if stretch is not None and not np.isfinite(pixels).any():
        raise ValueError("所选 HDU 没有有效像素。")
    if pixels.ndim == 2:
        low, high = stretch if stretch is not None else stretch_bounds(pixels)
        gray = np.clip((pixels - low) / (high - low), 0, 1)
        gray[~np.isfinite(gray)] = 0
        return Image.fromarray(np.asarray(gray * 255, dtype=np.uint8), mode="L").convert("RGB")
    if pixels.ndim == 3 and pixels.shape[-1] == 3:
        low, high = stretch if stretch is not None else stretch_bounds(pixels)
        rgb = np.clip((pixels - low) / (high - low), 0, 1)
        rgb[~np.isfinite(rgb)] = 0
        return Image.fromarray(np.asarray(rgb * 255, dtype=np.uint8), mode="RGB")
    raise ValueError("预览数据形状不受支持。")


def create_preview(path: Path, hdu_index: int, kind: str, parameters: dict, max_edge: int, stretch: tuple[float, float] | None = None) -> tuple[Image.Image, dict]:
    if kind in {"xtrans", "quad_bayer"}:
        raise ValueError(f"{kind} CFA 已登记；当前暂不支持其马赛克彩色预览。")
    with fits.open(path, memmap=False, lazy_load_hdus=True) as file:
        hdu = file[hdu_index]
        shape = tuple(int(value) for value in hdu.shape)
        if not shape or max(shape[-2:]) == 0:
            raise ValueError("所选 HDU 没有图像数据。")
        stride = max(1, (max(shape[-2:]) + max_edge - 1) // max_edge)
        if kind == "bayer" and stride % 2 == 0:
            stride += 1
        data = hdu.section
        if kind == "rgb":
            header = hdu.header
            if _rgb_channel_first(header):
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
            sample = _bayer_demosaic(
                sample, pattern,
                int(hdu.header.get("XBAYROFF", 0)), int(hdu.header.get("YBAYROFF", 0)), stride,
            )
        low, high = stretch if stretch is not None else stretch_bounds(sample)
        image = _display(sample, (low, high))
        image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        display_parameters = {
            "stretch": "percentile_1_99",
            "stretch_low": low,
            "stretch_high": high,
            "downsample_stride": stride,
            "cfa_pattern": parameters.get("cfa_pattern") if kind == "bayer" else None,
            "algorithm": PREVIEW_ALGORITHM_VERSION,
        }
        return image, display_parameters
