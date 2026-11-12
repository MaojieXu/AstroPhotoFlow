import asyncio
import hashlib
import json
import os
from pathlib import Path

import pytest

from astrophotoflow.contracts.development import BundleWatchPath
from astrophotoflow.interfaces.native.bundles import watcher


async def until(predicate):
    async with asyncio.timeout(5):
        while not predicate():
            await asyncio.sleep(.02)


@pytest.mark.asyncio
async def test_idle_does_not_scan_and_same_timestamp_helper_changes_reload(tmp_path, monkeypatch):
    source = tmp_path / 'adapter'
    source.mkdir()
    helper = source / 'helper.py'
    helper.write_text('VALUE=1')
    monkeypatch.setattr(watcher, 'watch_interests', lambda _: {BundleWatchPath(source, directory=True, recursive=True)})
    scans, refreshes, adopted = [], [], []

    def fingerprint():
        scans.append(1)
        return hashlib.sha256(helper.read_bytes()).hexdigest()

    async def reload():
        adopted.append(helper.read_text())

    monkeypatch.setattr(watcher, 'refresh_bundle_sources', lambda _: refreshes.append(1))
    task = asyncio.create_task(watcher.watch_workspace(tmp_path, fingerprint, reload, fingerprint()))
    try:
        await until(lambda: len(scans) >= 2)
        counts = len(scans), len(refreshes)
        await asyncio.sleep(.65)
        assert (len(scans), len(refreshes)) == counts
        before = helper.stat()
        helper.write_text('VALUE=2')
        os.utime(helper, ns=(before.st_atime_ns, before.st_mtime_ns))
        await until(lambda: adopted == ['VALUE=2'])
        (source / 'ignored.pyc').write_bytes(b'cache')
        (tmp_path / 'science.fit').write_bytes(b'original')
        counts = len(scans), len(refreshes)
        await asyncio.sleep(.65)
        assert (len(scans), len(refreshes)) == counts
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_binding_switch_rearms_roots_and_old_source_stops_triggering(tmp_path, monkeypatch):
    roots = [tmp_path / 'first', tmp_path / 'second']
    for root in roots:
        root.mkdir()
        (root / 'helper.py').write_text(root.name)
    binding = tmp_path / 'binding.json'
    binding.write_text(json.dumps(str(roots[0])))

    def current():
        return Path(json.loads(binding.read_text()))

    monkeypatch.setattr(watcher, 'watch_interests', lambda _: {
        BundleWatchPath(binding), BundleWatchPath(current(), directory=True, recursive=True)})
    monkeypatch.setattr(watcher, 'refresh_bundle_sources', lambda _: None)
    scans, adopted = [], []

    def fingerprint():
        scans.append(1)
        return str(current()) + (current() / 'helper.py').read_text()

    async def reload():
        adopted.append((current() / 'helper.py').read_text())

    task = asyncio.create_task(watcher.watch_workspace(tmp_path, fingerprint, reload, fingerprint()))
    try:
        await until(lambda: len(scans) >= 2)
        binding.write_text(json.dumps(str(roots[1])))
        await until(lambda: adopted == ['second'])
        (roots[1] / 'helper.py').write_text('second changed')
        await until(lambda: adopted == ['second', 'second changed'])
        (roots[0] / 'helper.py').write_text('old source changed')
        await asyncio.sleep(.65)
        assert adopted == ['second', 'second changed']
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_new_and_removed_directories_are_observed_without_polling(tmp_path, monkeypatch):
    target = tmp_path / 'new' / 'adapter'
    monkeypatch.setattr(watcher, 'watch_interests', lambda _: {BundleWatchPath(target, directory=True, recursive=True)})
    monkeypatch.setattr(watcher, 'refresh_bundle_sources', lambda _: None)
    scans, adopted = [], []

    def fingerprint():
        scans.append(1)
        return (target / 'helper.py').read_text() if (target / 'helper.py').is_file() else 'missing'

    async def reload():
        adopted.append(fingerprint())

    task = asyncio.create_task(watcher.watch_workspace(tmp_path, fingerprint, reload, fingerprint()))
    try:
        await until(lambda: len(scans) >= 2)
        target.mkdir(parents=True)
        (target / 'helper.py').write_text('new helper')
        await until(lambda: adopted == ['new helper'])
        (target / 'helper.py').unlink()
        target.rmdir()
        await until(lambda: adopted == ['new helper', 'missing'])
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_monitor_failure_is_not_hidden_by_startup_notification(tmp_path, monkeypatch):
    child = tmp_path / 'adapter'
    child.mkdir()
    monkeypatch.setattr(watcher, 'watch_interests', lambda _: {
        BundleWatchPath(child, directory=True, recursive=True), BundleWatchPath(tmp_path / 'control.json')})

    async def failing(*paths, recursive, **kwargs):
        if recursive:
            raise OSError('watch denied')
        yield set()
        await asyncio.Event().wait()

    monkeypatch.setattr(watcher, 'awatch', failing)
    monkeypatch.setattr(watcher, 'refresh_bundle_sources', lambda _: None)
    with pytest.raises(OSError, match='watch denied'):
        await watcher.watch_workspace(tmp_path, lambda: '', lambda: asyncio.sleep(0), '')
