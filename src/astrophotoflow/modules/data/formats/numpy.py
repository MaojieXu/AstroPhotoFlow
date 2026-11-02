from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np

from astrophotoflow.contracts.media import MediaArray, MediaSelection


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


def select_array(array, selection: MediaSelection, *, drop_alpha: bool = True):
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
        result = result[..., 0] if result.shape[-1] == 1 else result[..., :3] if drop_alpha else result
    return result
