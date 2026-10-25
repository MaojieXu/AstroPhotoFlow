from __future__ import annotations
import io
import shutil
import struct
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from .fits_preview import CFA_PATTERNS, _bayer_demosaic, _display, stretch_bounds


SER_HEADER_SIZE = 178
SER_BAYER = {8: "RGGB", 9: "GRBG", 10: "GBRG", 11: "BGGR"}


def _ser_preview(path: Path, max_edge: int, stretch: tuple[float, float] | None = None) -> tuple[Image.Image, dict]:
    with path.open("rb") as stream:
        header = stream.read(SER_HEADER_SIZE)
    if len(header) != SER_HEADER_SIZE or header[:14] != b"LUCAM-RECORDER":
        raise ValueError("SER 文件头无效。")
    _, color_id, little_endian, width, height, bit_depth, frame_count = struct.unpack("<7I", header[14:42])
    if width < 1 or height < 1 or frame_count < 1 or bit_depth < 1 or bit_depth > 16:
        raise ValueError("SER 文件尺寸、位深或帧数无效。")
    if color_id not in {0, 100, 101, *SER_BAYER}:
        raise ValueError(f"SER ColorID {color_id} 暂不支持预览。")
    planes = 3 if color_id in {100, 101} else 1
    bytes_per_channel = 1 if bit_depth <= 8 else 2
    frame_bytes = width * height * planes * bytes_per_channel
    if path.stat().st_size < SER_HEADER_SIZE + frame_bytes:
        raise ValueError("SER 文件不包含完整的第一帧。")
    if bytes_per_channel == 1:
        dtype = np.dtype("u1")
    else:
        dtype = np.dtype("<u2" if little_endian else ">u2")
    shape = (height, width, planes) if planes == 3 else (height, width)
    frame = np.memmap(path, dtype=dtype, mode="r", offset=SER_HEADER_SIZE, shape=shape)
    stride = max(1, (max(width, height) + max_edge - 1) // max_edge)
    if color_id in SER_BAYER and stride % 2 == 0:
        stride += 1
    if color_id in {100, 101}:
        sample = np.asarray(frame[::stride, ::stride, :], dtype=np.float32)
        if color_id == 101:
            sample = sample[:, :, ::-1]
        kind = "rgb"
        pattern = None
    else:
        sample = np.asarray(frame[::stride, ::stride], dtype=np.float32)
        pattern = SER_BAYER.get(color_id)
        kind = "bayer" if pattern else "mono"
        if pattern:
            sample = _bayer_demosaic(sample, pattern, 0, 0, stride)
    low, high = stretch if stretch is not None else stretch_bounds(sample)
    image = _display(sample, (low, high))
    image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    return image, {"video_frame_index": 0, "ser_color_id": color_id, "cfa_pattern": pattern, "algorithm": "ser-first-frame-1", "stretch_low": low, "stretch_high": high}


def first_video_frame(path: Path, max_edge: int, stretch: tuple[float, float] | None = None) -> tuple[Image.Image, dict]:
    if path.suffix.lower() == ".ser":
        return _ser_preview(path, max_edge, stretch)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("资产服务未找到 FFmpeg，无法生成视频首帧预览。")
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(path), "-map", "0:v:0",
         "-frames:v", "1", "-vf", f"scale='min({max_edge},iw)':'min({max_edge},ih)':force_original_aspect_ratio=decrease",
         "-f", "image2pipe", "-vcodec", "png", "pipe:1"],
        capture_output=True, check=False, timeout=60,
    )
    if result.returncode != 0 or not result.stdout:
        raise ValueError(result.stderr.decode("utf-8", errors="replace").strip() or "无法解码视频首帧。")
    with Image.open(io.BytesIO(result.stdout)) as decoded:
        image = decoded.convert("RGB").copy()
    image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    return image, {"video_frame_index": 0, "algorithm": "ffmpeg-first-frame-1"}
