"""Per-photo display recipe: RGB background white balance and linked auto MTF.

Uses the median/MAD background estimate, -2.8 sigma shadow clipping and
0.25 target background of astronomical auto-stretch. Original samples, not
JPEG previews, are the input. This is display white balance, not photometry.
"""
from __future__ import annotations
from astrophotoflow.contracts.previews import AutoStretch

from typing import Literal

import numpy as np
from PIL import Image
from pydantic import Field

from astrophotoflow.contracts.common import StrictModel




def calculate_stretch(pixels: np.ndarray) -> dict:
    values = np.asarray(pixels, dtype=np.float32)
    color = values.ndim == 3
    valid = values[np.isfinite(values).all(axis=-1)] if color else values[np.isfinite(values)]
    if not valid.size:
        raise ValueError("此照片没有可用于自动拉伸的有效像素。")
    offset = min(0.0, float(valid.min()))
    positive = valid - offset
    if color:
        # Median background is robust to sparse stars. Balance all channels
        # before applying a single linked tone curve, keeping background neutral.
        background = np.median(positive, axis=0)
        gains = np.divide(float(background.mean()), background, out=np.ones(3, dtype=np.float32), where=background > 0)
    else:
        gains = np.ones(1, dtype=np.float32)
    balanced = positive * gains
    luminance = balanced.mean(axis=-1) if color else balanced
    median = float(np.median(luminance))
    sigma = 1.4826 * float(np.median(np.abs(luminance - median)))
    shadows = max(0.0, median - 2.8 * sigma) if sigma > 0 else 0.0
    highlights = float(balanced.max())
    if highlights <= shadows:
        highlights = shadows + 1.0
    background = float(np.clip((median - shadows) / (highlights - shadows), 1e-6, 1 - 1e-6))
    target = 0.25
    midtones = background * (1 - target) / (background + target - 2 * background * target)
    return AutoStretch(input_offset=offset, white_balance=[float(gain) for gain in gains],
                       shadows=shadows, highlights=highlights, midtones=midtones).model_dump()


def render_stretch(pixels: np.ndarray, recipe: dict) -> Image.Image:
    values = np.asarray(pixels, dtype=np.float32)
    finite = np.isfinite(values)
    balanced = (values - recipe["input_offset"]) * np.asarray(recipe["white_balance"], dtype=np.float32)
    normalized = np.clip((balanced - recipe["shadows"]) / (recipe["highlights"] - recipe["shadows"]), 0, 1)
    midtones = recipe["midtones"]
    transformed = (midtones - 1) * normalized / ((2 * midtones - 1) * normalized - midtones)
    transformed[~finite] = 0
    image = np.asarray(np.clip(transformed * 255, 0, 255), dtype=np.uint8)
    return Image.fromarray(image).convert("RGB")
