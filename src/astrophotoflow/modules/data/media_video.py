from __future__ import annotations

from pathlib import Path
import io
import json
import re
import shutil
import subprocess
from fractions import Fraction

import numpy as np
from PIL import Image

from astrophotoflow.modules.data.media_sources import PixelSource, ser_info
from astrophotoflow.contracts.media import MediaSelection


def ffmpeg():
    executable = shutil.which("ffmpeg")
    if not executable:
        raise ValueError("未找到已有FFmpeg，无法读取或播放此视频。")
    return executable


def frame_times(log):
    base = re.search(r"config in time_base:\s*(\d+)/(\d+)", log)
    if base is None:
        raise ValueError("FFmpeg没有提供可核对的帧时间基准。")
    scale = Fraction(int(base[1]), int(base[2]))
    return [(int(index), float(int(timestamp) * scale)) for index, timestamp in re.findall(r"\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:", log)]


def video_info(path):
    result = subprocess.run([ffmpeg(), "-hide_banner", "-nostdin", "-i", str(path), "-map", "0:v:0", "-frames:v", "0", "-f", "null", "-"],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False, timeout=30)
    log = result.stderr.decode("utf-8", errors="replace").split("Stream mapping:")[0]
    shape = re.search(r"Video:[^\n]*?\b(\d{2,})x(\d{2,})\b", log)
    if result.returncode or shape is None:
        raise ValueError("FFmpeg无法读取视频尺寸和媒体流。")
    width, height = map(int, shape.groups())
    rotation = re.search(r"rotation of ([\d.\-]+) degrees", log)
    if rotation and abs(round(float(rotation[1]) / 90)) % 2:
        width, height = height, width
    duration = re.search(r"Duration: (\d+):(\d+):([\d.]+)", log)
    seconds = int(duration[1]) * 3600 + int(duration[2]) * 60 + float(duration[3]) if duration else None
    return width, height, seconds


def extract_frame(path, selection, folder, reserve):
    filters = []
    if selection.frame_index is not None:
        filters.append(f"select=eq(n\\,{selection.frame_index})")
    elif selection.media_time is not None:
        filters.append(f"trim=start={selection.media_time:.9f}")
    filters.append("showinfo")
    result = subprocess.run([ffmpeg(), "-hide_banner", "-nostdin", "-i", str(path), "-map", "0:v:0", "-vf", ",".join(filters),
        "-frames:v", "1", "-fps_mode", "passthrough", "-f", "image2pipe", "-c:v", "png", "pipe:1"],
        capture_output=True, check=False, timeout=120)
    if result.returncode or not result.stdout:
        raise ValueError("视频当前帧解码失败：" + result.stderr.decode("utf-8", errors="replace")[-1200:])
    log = result.stderr.decode("utf-8", errors="replace")
    times = frame_times(log)
    if selection.media_time is not None and (not times or abs(times[0][1] - selection.media_time) > 0.003):
        raise ValueError("未能将暂停画面精确对应到原件时间戳，请重新暂停后重试。")
    with Image.open(io.BytesIO(result.stdout)) as image:
        array = np.asarray(image.convert("RGB"))
    reserve(array.nbytes + 256)
    target = folder / "frame.npy"
    with target.open("wb") as stream:
        np.save(stream, array, allow_pickle=False)
    return target, array.shape[1], array.shape[0], times[0][1] if times else None


def make_proxy(path, folder, cache, parameters, recipe):
    target = folder / "playback.mp4"
    part = folder / "playback.part.mp4"
    log_path = folder / "playback.log"
    command = [ffmpeg(), "-hide_banner", "-nostdin", "-y"]
    ser = path.suffix.lower() == ".ser"
    source_times = None
    timing_path = folder / "ser-pts.cmd"
    if ser:
        info = ser_info(path)
        source_times = info["times"]
        fps = 10.0 if source_times is None else 25.0
        width, height = info["width"], info["height"]
        factor = min(1, 1920 / max(width, height))
        width, height = max(2, int(width * factor) // 2 * 2), max(2, int(height * factor) // 2 * 2)
        command += ["-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", f"{width}x{height}", "-framerate", str(fps), "-i", "pipe:0"]
        source = PixelSource(path, "video", MediaSelection(frame_index=0), parameters, folder, cache.reserve)
        if source_times is not None:
            commands = "\n".join(f"{max(0, index / fps - 0.000001):.6f} [enter] setpts@ser_pts expr '{timestamp:.9f}/TB';" for index, timestamp in enumerate(source_times))
            cache.write(timing_path, commands.encode())
    else:
        command += ["-i", str(path)]
    timing = "settb=expr=1/10000000,sendcmd=f=ser-pts.cmd,setpts@ser_pts=PTS," if source_times is not None else ""
    command += ["-map", "0:v:0", "-an", "-vf", timing + "scale='min(1920,iw)':'min(1920,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2,showinfo",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-fps_mode", "passthrough", "-movflags", "+faststart", str(part)]
    if source_times is not None:
        command[-1:-1] = ["-enc_time_base", "1:10000000", "-video_track_timescale", "10000000"]
    try:
        with log_path.open("wb") as log:
            process = subprocess.Popen(command, cwd=folder, stdin=subprocess.PIPE if ser else subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=log)
            try:
                if ser:
                    for index in range(info["count"]):
                        source.selection = MediaSelection(frame_index=index)
                        step = max(1, int(max(info["width"], info["height"]) / 3840))
                        if info["color"] in {8, 9, 10, 11} and step % 2 == 0:
                            step += 1
                        pixels = source.read((0, 0, info["width"], info["height"]), step)
                        image = source.render(pixels, recipe).resize((width, height), Image.Resampling.LANCZOS)
                        process.stdin.write(image.tobytes())
                        if part.exists() and part.stat().st_size + log_path.stat().st_size > cache.disk_budget:
                            raise ValueError("视频代理超过4GiB缓存预算。")
                    process.stdin.close()
                while process.poll() is None:
                    try:
                        process.wait(timeout=0.2)
                    except subprocess.TimeoutExpired:
                        cache.reserve(0)
                        if part.exists() and part.stat().st_size > cache.disk_budget:
                            raise ValueError("视频代理超过4GiB缓存预算。")
                if process.returncode:
                    raise ValueError("视频代理生成失败，请检查FFmpeg解码和H.264编码能力。")
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait()
        log = log_path.read_text(encoding="utf-8", errors="replace")
        frames = frame_times(log)
        if not frames:
            raise ValueError("视频代理没有可核对的帧时间戳。")
        if any(current[1] <= previous[1] for previous, current in zip(frames, frames[1:])):
            raise ValueError("视频帧时间戳不唯一，不能建立可靠的暂停帧映射。")
        mapping = [{"time": timestamp - frames[0][1], "source_time": None if ser else timestamp, "index": index} for index, timestamp in frames]
        cache.write(folder / "frames.json", json.dumps(mapping).encode())
        part.replace(target)
        note = "播放代理≤1920px；放大读取原件帧。"
        if ser:
            note += " SER无有效时间戳，按10fps预览。" if source_times is None else " SER保留采集帧时间戳及原始帧对应。"
        return target, note
    finally:
        part.unlink(missing_ok=True)
        log_path.unlink(missing_ok=True)
        timing_path.unlink(missing_ok=True)
