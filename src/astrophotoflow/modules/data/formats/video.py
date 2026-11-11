from __future__ import annotations
import io
import re
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path
import numpy as np
from PIL import Image
from astrophotoflow.modules.data.formats.ser import read_ser_preview

def ffmpeg():
    executable = shutil.which('ffmpeg')
    if not executable:
        raise ValueError('未找到已有FFmpeg，无法读取或播放此视频。')
    return executable

def frame_times(log):
    base = re.search('config in time_base:\\s*(\\d+)/(\\d+)', log)
    if base is None:
        raise ValueError('FFmpeg没有提供可核对的帧时间基准。')
    scale = Fraction(int(base[1]), int(base[2]))
    return [(int(index), float(int(timestamp) * scale)) for index, timestamp in re.findall('\\bn:\\s*(\\d+)\\s+pts:\\s*(-?\\d+)\\s+pts_time:', log)]

def video_info(path):
    result = subprocess.run([ffmpeg(), '-hide_banner', '-nostdin', '-i', str(path), '-map', '0:v:0', '-frames:v', '0', '-f', 'null', '-'], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False, timeout=30)
    log = result.stderr.decode('utf-8', errors='replace').split('Stream mapping:')[0]
    shape = re.search('Video:[^\\n]*?\\b(\\d{2,})x(\\d{2,})\\b', log)
    if result.returncode or shape is None:
        raise ValueError('FFmpeg无法读取视频尺寸和媒体流。')
    width, height = map(int, shape.groups())
    rotation = re.search('rotation of ([\\d.\\-]+) degrees', log)
    if rotation and abs(round(float(rotation[1]) / 90)) % 2:
        width, height = (height, width)
    duration = re.search('Duration: (\\d+):(\\d+):([\\d.]+)', log)
    seconds = int(duration[1]) * 3600 + int(duration[2]) * 60 + float(duration[3]) if duration else None
    return (width, height, seconds)

def extract_frame(path, selection, folder, reserve):
    filters = []
    if selection.frame_index is not None:
        filters.append(f'select=eq(n\\,{selection.frame_index})')
    elif selection.media_time is not None:
        filters.append(f'trim=start={selection.media_time:.9f}')
    filters.append('showinfo')
    result = subprocess.run([ffmpeg(), '-hide_banner', '-nostdin', '-i', str(path), '-map', '0:v:0', '-vf', ','.join(filters), '-frames:v', '1', '-fps_mode', 'passthrough', '-f', 'image2pipe', '-c:v', 'png', 'pipe:1'], capture_output=True, check=False, timeout=120)
    if result.returncode or not result.stdout:
        raise ValueError('视频当前帧解码失败：' + result.stderr.decode('utf-8', errors='replace')[-1200:])
    log = result.stderr.decode('utf-8', errors='replace')
    times = frame_times(log)
    if selection.media_time is not None and (not times or abs(times[0][1] - selection.media_time) > 0.003):
        raise ValueError('未能将暂停画面精确对应到原件时间戳，请重新暂停后重试。')
    with Image.open(io.BytesIO(result.stdout)) as image:
        array = np.asarray(image.convert('RGB'))
    reserve(array.nbytes + 256)
    target = folder / 'frame.npy'
    with target.open('wb') as stream:
        np.save(stream, array, allow_pickle=False)
    return (target, array.shape[1], array.shape[0], times[0][1] if times else None)

def first_video_frame(path: Path, max_edge: int, stretch: tuple[float, float] | None=None) -> tuple[Image.Image, dict]:
    if path.suffix.lower() == '.ser':
        return read_ser_preview(path, max_edge, stretch)
    ffmpeg = shutil.which('ffmpeg')
    if ffmpeg is None:
        raise RuntimeError('资产服务未找到 FFmpeg，无法生成视频首帧预览。')
    result = subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-i', str(path), '-map', '0:v:0', '-frames:v', '1', '-vf', f"scale='min({max_edge},iw)':'min({max_edge},ih)':force_original_aspect_ratio=decrease", '-f', 'image2pipe', '-vcodec', 'png', 'pipe:1'], capture_output=True, check=False, timeout=60)
    if result.returncode != 0 or not result.stdout:
        raise ValueError(result.stderr.decode('utf-8', errors='replace').strip() or '无法解码视频首帧。')
    with Image.open(io.BytesIO(result.stdout)) as decoded:
        image = decoded.convert('RGB').copy()
    image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    return (image, {'video_frame_index': 0, 'algorithm': 'ffmpeg-first-frame-1'})
