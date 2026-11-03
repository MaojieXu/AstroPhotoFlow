from __future__ import annotations

import math
from concurrent.futures import CancelledError, Future
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from threading import Event, RLock

from PIL import Image

from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.formats.source import PixelSource


@dataclass
class PendingTile:
    future: Future
    stop: Event
    readers: int
    retained: bool


class TileService:
    def __init__(self, cache, executor):
        self.cache, self.executor = cache, executor
        self.lock = RLock()
        self.pending: dict[tuple[str, int, int, int], PendingTile] = {}

    def pixel_source(self, job, check_cancel=None):
        return PixelSource(Path(job.get("pixel_path", job["path"])), job.get("pixel_category", job["category"]),
            job["selection"], job["parameters"], job["folder"], self.cache.reserve, check_cancel, self.cache.record)


    def tile(self, job, level, x, y):
        future = self.tile_future(job, level, x, y)
        return future.result()


    def tile_future(self, job, level, x, y, *, tracked=False):
        state = job["state"]
        if state["kind"] != "image":
            raise ApiError(422, "MEDIA_NOT_IMAGE", "请先暂停视频并准备原件帧。", message_key='pause_the_video_and_prepare_the_original_frame_first')
        factor = 2 ** (state["max_level"] - level) if 0 <= level <= state["max_level"] else 0
        if not factor or x < 0 or y < 0 or x * 512 * factor >= state["width"] or y * 512 * factor >= state["height"]:
            raise ApiError(422, "INVALID_TILE", "瓦片坐标超出图像范围。", message_key='tile_coordinates_are_outside_the_image_bounds')
        token = (job["key"], level, x, y)
        cached = self.cache.get(token)
        if cached is not None:
            result = Future()
            result.set_result(cached)
            return result
        target = job["folder"] / f"tile-{level}-{x}-{y}.png"
        if target.is_file():
            value = target.read_bytes()
            self.cache.put(token, value)
            result = Future()
            result.set_result(value)
            return result
        else:
            with self.lock:
                work = self.pending.get(token)
                if work is None:
                    stop = Event()
                    future = self.executor.submit(self._tile, job, level, x, y, target, stop)
                    work = PendingTile(future, stop, int(tracked), not tracked)
                    self.pending[token] = work
                    def complete(completed):
                        with self.lock:
                            self.pending.pop(token, None)
                        if not completed.cancelled() and completed.exception() is None:
                            self.cache.put(token, completed.result())
                    future.add_done_callback(complete)
                else:
                    work.readers += int(tracked)
                    work.retained |= not tracked
            return work.future


    def release_tile(self, job, level, x, y, future):
        with self.lock:
            work = self.pending.get((job["key"], level, x, y))
            if work is not None and work.future is future:
                work.readers -= 1
                if not work.readers and not work.retained:
                    work.stop.set()
                    work.future.cancel()


    def _tile(self, job, level, x, y, target, stop):
        def check_cancel():
            if stop.is_set():
                raise CancelledError("瓦片请求已取消。")
        check_cancel()
        state = job["state"]
        factor = 2 ** (state["max_level"] - level)
        width, height = math.ceil(state["width"] / factor), math.ceil(state["height"] / factor)
        left, top = x * 512, y * 512
        right, bottom = min(left + 512, width), min(top + 512, height)
        source = self.pixel_source(job, check_cancel)
        source.dimensions()
        step = max(1, factor // 2)
        if (source.category == "fits" or source.path.suffix.lower() == ".ser") and step % 2 == 0 and source.cfa in {"RGGB", "BGGR", "GRBG", "GBRG"}:
            step -= 1
        sx, sy = max(0, (left - 3) * factor) // step * step, max(0, (top - 3) * factor) // step * step
        ex, ey = min(state["width"], (right + 3) * factor), min(state["height"], (bottom + 3) * factor)
        image = source.render(source.read((sx, sy, ex, ey), step), job["recipe"])
        box = ((left * factor - sx) / step, (top * factor - sy) / step,
            min(image.width, (right * factor - sx) / step), min(image.height, (bottom * factor - sy) / step))
        image = image.resize((right - left, bottom - top), Image.Resampling.LANCZOS if factor > 1 else Image.Resampling.NEAREST, box=box)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        value = buffer.getvalue()
        check_cancel()
        self.cache.write(target, value)
        return value
