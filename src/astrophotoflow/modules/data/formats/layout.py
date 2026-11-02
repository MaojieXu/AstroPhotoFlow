from __future__ import annotations

import numpy as np

CFA_PATTERNS = {"RGGB", "BGGR", "GRBG", "GBRG"}

def fits_image_kind(hdu, cfa_override: str | None = None) -> str | None:
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
        if rgb_channel_first(header):
            return "rgb"
        axis1 = str(header.get("CTYPE1", "")).strip().upper()
        if int(header.get("NAXIS1", 0)) == 3 and axis1 in {"RGB", "COLOR"}:
            return "rgb"
    return None


def rgb_channel_first(header) -> bool:
    if int(header.get("NAXIS3", 0)) != 3:
        return False
    axis3 = str(header.get("CTYPE3", "")).strip().upper()
    if axis3 in {"RGB", "COLOR"}:
        return True
    if int(header.get('NAXIS1', 0)) == 3 and str(header.get('CTYPE1', '')).strip().upper() in {'RGB', 'COLOR'}:
        return False
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


def apply_colour_layout(hdu, layout):
    if layout is None or int(hdu.header.get('NAXIS', 0)) != 3:
        return
    axis = 3 if layout == 'planar' else 1
    key = 'CTYPE' + str(axis)
    other_axis = 1 if axis == 3 else 3
    if int(hdu.header.get('NAXIS' + str(axis), 0)) != 3 or str(hdu.header.get(key, '')).strip().upper() not in {'', 'RGB', 'COLOR'} or str(hdu.header.get('CTYPE' + str(other_axis), '')).strip().upper() in {'RGB', 'COLOR'}:
        raise ValueError('声明的RGB布局与FITS维度或轴含义不一致。')
    hdu.header[key] = 'RGB'


def bayer_demosaic(mosaic: np.ndarray, pattern: str, x_offset: int, y_offset: int, stride: int) -> np.ndarray:
    rows = [[pattern[((y_offset + y * stride) % 2) * 2 + ((x_offset + x * stride) % 2)] for x in range(2)] for y in range(2)]
    height, width = mosaic.shape
    output = np.empty((height, width, 3), dtype=np.float32)
    padded = np.pad(mosaic.astype(np.float32), 2, mode="reflect")
    for channel, color in enumerate(("R", "G", "B")):
        mask = np.fromfunction(lambda y, x, color=color: np.asarray(rows)[y.astype(int) % 2, x.astype(int) % 2] == color, (height, width), dtype=int)
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
