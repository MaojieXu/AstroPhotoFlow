from __future__ import annotations

import numpy as np
from PIL import Image

from astrophotoflow.contracts.previews import AutoStretch


def statistics_indices(height: int, width: int) -> tuple[np.ndarray, np.ndarray]:
    rows = min(height, STATISTICS_SAMPLES, max(1, int(np.sqrt(STATISTICS_SAMPLES * height / width))))
    columns = min(width, max(1, STATISTICS_SAMPLES // rows))
    row_edges = np.linspace(0, height, rows + 1, dtype=np.int64)
    column_edges = np.linspace(0, width, columns + 1, dtype=np.int64)
    rng = np.random.default_rng(0)
    selected_rows = rng.integers(row_edges[:-1], row_edges[1:])
    selected_columns = rng.integers(column_edges[:-1], column_edges[1:], size=(rows, columns))
    return selected_rows, selected_columns


def sample_statistics(pixels: np.ndarray) -> np.ndarray:
    rows, columns = statistics_indices(*pixels.shape[:2])
    return np.asarray(pixels[rows[:, None], columns], dtype=np.float32)


def sample_pixels(pixels: np.ndarray, max_edge: int) -> np.ndarray:
    stride = max(1, (max(pixels.shape[:2]) + max_edge - 1) // max_edge)
    return np.asarray(pixels[::stride, ::stride], dtype=np.float32)


def calculate_stretch(pixels: np.ndarray, *, balance_rgb: bool = True) -> dict:
    values = sample_statistics(pixels)
    color = values.ndim == 3
    valid = values[np.isfinite(values).all(axis=-1)] if color else values[np.isfinite(values)]
    if not valid.size:
        raise ValueError("此照片没有可用于自动拉伸的有效像素。")
    offset = min(0.0, float(valid.min()))
    positive = valid - offset
    if color and balance_rgb:
        # Median background is robust to sparse stars. Balance all channels
        # before applying a single linked tone curve, keeping background neutral.
        background = np.median(positive, axis=0)
        gains = np.divide(float(background.mean()), background, out=np.ones(3, dtype=np.float32), where=background > 0)
    else:
        gains = np.ones(3 if color else 1, dtype=np.float32)
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


def stretch_values(pixels: np.ndarray, recipe: dict) -> np.ndarray:
    values = np.asarray(pixels, dtype=np.float32)
    finite = np.isfinite(values)
    balanced = (values - recipe["input_offset"]) * np.asarray(recipe["white_balance"], dtype=np.float32)
    normalized = np.clip((balanced - recipe["shadows"]) / (recipe["highlights"] - recipe["shadows"]), 0, 1)
    midtones = recipe["midtones"]
    transformed = (midtones - 1) * normalized / ((2 * midtones - 1) * normalized - midtones)
    transformed[~finite] = 0
    return np.clip(transformed, 0, 1)


def render_stretch(pixels: np.ndarray, recipe: dict) -> Image.Image:
    transformed = stretch_values(pixels, recipe)
    image = np.asarray(np.clip(transformed * 255, 0, 255), dtype=np.uint8)
    return Image.fromarray(image).convert("RGB")


def stretch_bounds(array: np.ndarray) -> tuple[float, float]:
    finite = sample_statistics(array)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        raise ValueError("所选 HDU 没有有效像素。")
    low, high = (float(value) for value in np.percentile(finite, (1, 99)))
    return low, high if high > low else low + 1.0


def display_pixels(array: np.ndarray, stretch: tuple[float, float] | None = None) -> Image.Image:
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

STATISTICS_SAMPLES = 262_144
