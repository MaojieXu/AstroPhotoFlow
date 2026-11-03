from __future__ import annotations

import json
import subprocess
from itertools import pairwise

from PIL import Image

from astrophotoflow.contracts.media import MediaSelection
from astrophotoflow.modules.data.formats import video
from astrophotoflow.modules.data.formats.ser import ser_info
from astrophotoflow.modules.data.formats.source import PixelSource


def make_proxy(path, folder, cache, parameters, recipe):
    target = folder / "playback.mp4"
    part = folder / "playback.part.mp4"
    log_path = folder / "playback.log"
    command = [video.ffmpeg(), "-hide_banner", "-nostdin", "-y"]
    ser = path.suffix.lower() == ".ser"
    source_times = None
    timing_path = folder / "ser-pts.cmd"
    if ser:
        info = ser_info(path)
        source_times = info.times
        fps = 10.0 if source_times is None else 25.0
        width, height = info.width, info.height
        factor = min(1, 1920 / max(width, height))
        width, height = max(2, int(width * factor) // 2 * 2), max(2, int(height * factor) // 2 * 2)
        command += ["-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", f"{width}x{height}", "-framerate", str(fps), "-i", "pipe:0"]
        source = PixelSource(path, "video", MediaSelection(frame_index=0), parameters, folder, cache.reserve, record=cache.record)
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
                    for index in range(info.count):
                        source.selection = MediaSelection(frame_index=index)
                        step = max(1, int(max(info.width, info.height) / 3840))
                        if info.color in {8, 9, 10, 11} and step % 2 == 0:
                            step += 1
                        pixels = source.read((0, 0, info.width, info.height), step)
                        image = source.render(pixels, recipe).resize((width, height), Image.Resampling.LANCZOS)
                        process.stdin.write(image.tobytes())
                        if part.exists() and part.stat().st_size + log_path.stat().st_size > cache.disk_budget:
                            raise ValueError("视频代理超过4GiB缓存预算。")
                        cache.record(part)
                        cache.record(log_path)
                        cache.reserve(0)
                    process.stdin.close()
                while process.poll() is None:
                    try:
                        process.wait(timeout=0.2)
                    except subprocess.TimeoutExpired:
                        cache.record(part)
                        cache.record(log_path)
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
        frames = video.frame_times(log)
        if not frames:
            raise ValueError("视频代理没有可核对的帧时间戳。")
        if any(current[1] <= previous[1] for previous, current in pairwise(frames)):
            raise ValueError("视频帧时间戳不唯一，不能建立可靠的暂停帧映射。")
        mapping = [{"time": timestamp - frames[0][1], "source_time": None if ser else timestamp, "index": index} for index, timestamp in frames]
        cache.write(folder / "frames.json", json.dumps(mapping).encode())
        part.replace(target)
        cache.record(part)
        cache.record(target)
        note = "播放代理≤1920px；放大读取原件帧。"
        if ser:
            note += " SER无有效时间戳，按10fps预览。" if source_times is None else " SER保留采集帧时间戳及原始帧对应。"
        return target, note
    finally:
        part.unlink(missing_ok=True)
        log_path.unlink(missing_ok=True)
        timing_path.unlink(missing_ok=True)
        for path in (part, log_path, timing_path):
            cache.record(path)
