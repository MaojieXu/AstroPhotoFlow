from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image
import pytest

from astrophotoflow.contracts.media import MediaSelection
from astrophotoflow.modules.data.media_cache import MediaCache
from astrophotoflow.modules.data.media_view import MediaViews


def test_disk_lru_does_not_remove_active_view_or_original(tmp_path):
    original = tmp_path / "objects" / "source.fits"
    original.parent.mkdir()
    original.write_bytes(b"science")
    cache = MediaCache(tmp_path, disk_budget=100)
    older = tmp_path / "previews" / "v1" / "media" / "old"
    active = tmp_path / "previews" / "v2" / "media" / "active"
    older.mkdir(parents=True)
    active.mkdir(parents=True)
    (older / "tile.png").write_bytes(b"o" * 50)
    (active / "tile.png").write_bytes(b"a" * 40)
    with cache.hold(active):
        cache.write(active / "new.png", b"n" * 30)
        assert not older.exists()
        assert original.read_bytes() == b"science"
        assert (active / "tile.png").read_bytes() == b"a" * 40
        with pytest.raises(ValueError, match="空间不足"):
            cache.reserve(50)


def test_memory_cache_uses_byte_budget_and_access_order(tmp_path):
    cache = MediaCache(tmp_path, memory_budget=8)
    cache.put("first", b"1111")
    cache.put("second", b"2222")
    assert cache.get("first") == b"1111"
    cache.put("third", b"3333")
    assert cache.get("second") is None
    assert cache.get("first") == b"1111"
    assert cache.memory_bytes == 8


def test_native_tiles_reassemble_original_pixels_and_share_pending_work(tmp_path):
    path = tmp_path / "source.png"
    pixels = np.random.default_rng(8).integers(0, 255, (519, 1031, 3), dtype=np.uint8)
    Image.fromarray(pixels).save(path)
    folder = tmp_path / "previews" / "version" / "media" / "key"
    folder.mkdir(parents=True)
    service = MediaViews.__new__(MediaViews)
    from threading import RLock
    service.cache, service.lock, service.pending = MediaCache(tmp_path), RLock(), {}
    job = dict(key="key", path=path, category="image", selection=MediaSelection(), parameters={}, folder=folder,
               recipe={}, state={"kind": "image", "width": 1031, "height": 519, "max_level": 11})
    with ThreadPoolExecutor(1) as executor:
        service.executor = executor
        result = np.empty_like(pixels)
        for y in range(2):
            for x in range(3):
                payload = service.tile(job, 11, x, y)
                tile = np.asarray(Image.open(BytesIO(payload)))
                result[y * 512:y * 512 + tile.shape[0], x * 512:x * 512 + tile.shape[1]] = tile
        np.testing.assert_array_equal(result, pixels)
        first = service.tile_future(job, 10, 0, 0)
        second = service.tile_future(job, 10, 0, 0)
        assert first.result() == second.result()
        assert len(list(folder.glob("tile-10-0-0.png"))) == 1
        with pytest.raises(Exception, match="瓦片坐标"):
            service.tile(job, 12, 0, 0)


def test_shared_tile_only_cancels_when_last_reader_disconnects(tmp_path, monkeypatch):
    from concurrent.futures import CancelledError
    from threading import Event, RLock
    from astrophotoflow.modules.data.preview_executor import PreviewExecutor
    service = MediaViews.__new__(MediaViews)
    service.cache, service.lock, service.pending = MediaCache(tmp_path), RLock(), {}
    entered, proceed = Event(), Event()
    def tile(job, level, x, y, target, stop):
        entered.set()
        assert proceed.wait(5)
        if stop.is_set():
            raise CancelledError()
        return b'tile'
    monkeypatch.setattr(service, '_tile', tile)
    job = dict(key='shared', folder=tmp_path, state={'kind': 'image', 'width': 1024, 'height': 1024, 'max_level': 10})
    with PreviewExecutor(1) as executor:
        service.executor = executor
        first = service.tile_future(job, 10, 0, 0, tracked=True)
        try:
            assert entered.wait(5)
            second = service.tile_future(job, 10, 0, 0, tracked=True)
            assert second is first
            service.release_tile(job, 10, 0, 0, first)
            assert not service.pending[('shared', 10, 0, 0)]['stop'].is_set()
            service.release_tile(job, 10, 0, 0, first)
            assert service.pending[('shared', 10, 0, 0)]['stop'].is_set()
        finally:
            proceed.set()
        with pytest.raises(CancelledError):
            first.result(timeout=5)
