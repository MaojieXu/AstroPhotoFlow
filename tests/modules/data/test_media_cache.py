from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
import numpy as np
from PIL import Image
import pytest
from astrophotoflow.contracts.media import MediaSelection
from astrophotoflow.modules.data.media.cache import MediaCache
from astrophotoflow.modules.data.media.tiles import TileService

def test_repeated_tile_writes_use_incremental_accounting_and_preserve_active_cache(tmp_path, monkeypatch):
    cache = MediaCache(tmp_path, disk_budget=100)
    folder = tmp_path / 'previews' / 'version' / 'media' / 'key'
    folder.mkdir(parents=True)
    with cache.hold(folder):
        monkeypatch.setattr(Path, 'rglob', lambda *args: pytest.fail('tile write rescanned the cache'))
        cache.write(folder / 'first.png', b'a' * 20)
        cache.write(folder / 'second.png', b'b' * 30)
        cache.write(folder / 'first.png', b'c' * 10)
        assert sum((size for size, _ in cache.disk_folders.values())) == 40
        with pytest.raises(ValueError, match='空间不足'):
            cache.write(folder / 'too-large.png', b'd' * 61)
        assert not (folder / 'too-large.png').exists()

def test_external_decodes_and_removed_files_update_cache_budget(tmp_path):
    cache = MediaCache(tmp_path, disk_budget=100)
    folder = tmp_path / 'previews' / 'version' / 'media' / 'key'
    folder.mkdir(parents=True)
    with cache.hold(folder):
        pixels = folder / 'pixels.npy'
        pixels.write_bytes(b'p' * 70)
        cache.record(pixels)
        with pytest.raises(ValueError, match='空间不足'):
            cache.reserve(31)
        pixels.unlink()
        cache.record(pixels)
        cache.write(folder / 'overview.jpg', b'j' * 100)
        assert cache.disk_folders[folder][0] == 100

def test_disk_lru_does_not_remove_active_view_or_original(tmp_path):
    original = tmp_path / 'objects' / 'source.fits'
    original.parent.mkdir()
    original.write_bytes(b'science')
    cache = MediaCache(tmp_path, disk_budget=100)
    older = tmp_path / 'previews' / 'v1' / 'media' / 'old'
    active = tmp_path / 'previews' / 'v2' / 'media' / 'active'
    older.mkdir(parents=True)
    active.mkdir(parents=True)
    (older / 'tile.png').write_bytes(b'o' * 50)
    (active / 'tile.png').write_bytes(b'a' * 40)
    with cache.hold(active):
        cache.write(active / 'new.png', b'n' * 30)
        assert not older.exists()
        assert original.read_bytes() == b'science'
        assert (active / 'tile.png').read_bytes() == b'a' * 40
        with pytest.raises(ValueError, match='空间不足'):
            cache.reserve(50)

def test_memory_cache_uses_byte_budget_and_access_order(tmp_path):
    cache = MediaCache(tmp_path, memory_budget=8)
    cache.put('first', b'1111')
    cache.put('second', b'2222')
    assert cache.get('first') == b'1111'
    cache.put('third', b'3333')
    assert cache.get('second') is None
    assert cache.get('first') == b'1111'
    assert cache.memory_bytes == 8

def test_native_tiles_reassemble_original_pixels_and_share_pending_work(tmp_path):
    path = tmp_path / 'source.png'
    pixels = np.random.default_rng(8).integers(0, 255, (519, 1031, 3), dtype=np.uint8)
    Image.fromarray(pixels).save(path)
    folder = tmp_path / 'previews' / 'version' / 'media' / 'key'
    folder.mkdir(parents=True)
    cache = MediaCache(tmp_path)
    job = dict(key='key', path=path, category='image', selection=MediaSelection(), parameters={}, folder=folder, recipe={}, state={'kind': 'image', 'width': 1031, 'height': 519, 'max_level': 11})
    with ThreadPoolExecutor(1) as executor:
        service = TileService(cache, executor)
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
        assert len(list(folder.glob('tile-10-0-0.png'))) == 1
        with pytest.raises(Exception, match='瓦片坐标'):
            service.tile(job, 12, 0, 0)

def test_shared_tile_only_cancels_when_last_reader_disconnects(tmp_path, monkeypatch):
    from concurrent.futures import CancelledError
    from threading import Event
    from astrophotoflow.modules.data.media.executor import PreviewExecutor
    cache = MediaCache(tmp_path)
    entered, proceed = (Event(), Event())

    def tile(job, level, x, y, target, stop):
        entered.set()
        assert proceed.wait(5)
        if stop.is_set():
            raise CancelledError()
        return b'tile'
    job = dict(key='shared', folder=tmp_path, state={'kind': 'image', 'width': 1024, 'height': 1024, 'max_level': 10})
    with PreviewExecutor(1) as executor:
        service = TileService(cache, executor)
        monkeypatch.setattr(service, '_tile', tile)
        first = service.tile_future(job, 10, 0, 0, tracked=True)
        try:
            assert entered.wait(5)
            second = service.tile_future(job, 10, 0, 0, tracked=True)
            assert second is first
            service.release_tile(job, 10, 0, 0, first)
            assert not service.pending['shared', 10, 0, 0].stop.is_set()
            service.release_tile(job, 10, 0, 0, first)
            assert service.pending['shared', 10, 0, 0].stop.is_set()
        finally:
            proceed.set()
        with pytest.raises(CancelledError):
            first.result(timeout=5)

@pytest.fixture
def output_lease(tmp_path):
    import json
    from threading import RLock
    from types import SimpleNamespace
    from astrophotoflow.modules.data.media.leases import MediaLeases
    path = tmp_path / 'science.fits'
    path.write_bytes(b'science')
    key = 'a' * 40
    folder = tmp_path / 'previews' / 'run-outputs' / 'media' / key
    folder.mkdir(parents=True)
    stat = path.stat()
    manifest = {'key': key, 'path': str(path), 'stamp': [stat.st_size, stat.st_mtime_ns], 'selection': {}, 'output_source': True}
    (folder / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    cache = MediaCache(tmp_path)
    leases = MediaLeases(None, SimpleNamespace(data_dir=tmp_path), cache, RLock())
    return (leases, cache, SimpleNamespace(path=path), key, folder)

def test_repeated_release_does_not_unpin_another_response(output_lease):
    leases, cache, checked, key, folder = output_lease
    _, release_first = leases.acquire_output(checked, key)
    _, release_second = leases.acquire_output(checked, key)
    release_first()
    release_first()
    assert leases.active[key] == cache.active[folder] == 1
    release_second()
    assert leases.active == cache.active == {}

def test_failed_lease_preparation_releases_cache_hold(output_lease, monkeypatch):
    leases, cache, checked, key, folder = output_lease
    original_touch = Path.touch

    def fail_touch(path, *args, **kwargs):
        if path == folder:
            raise OSError('cache directory unavailable')
        return original_touch(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'touch', fail_touch)
    with pytest.raises(OSError, match='unavailable'):
        leases.acquire_output(checked, key)
    assert leases.active == cache.active == {}

def test_output_lease_refuses_foreign_file_even_with_same_stamp(output_lease, tmp_path):
    import os
    from types import SimpleNamespace
    from astrophotoflow.core.errors import ApiError
    leases, cache, checked, key, _ = output_lease
    foreign = tmp_path / 'foreign.fits'
    foreign.write_bytes(checked.path.read_bytes())
    stat = checked.path.stat()
    os.utime(foreign, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    with pytest.raises(ApiError) as failure:
        leases.acquire_output(SimpleNamespace(path=foreign), key)
    assert failure.value.code == 'SOURCE_CHANGED'
    assert leases.active == cache.active == {}
