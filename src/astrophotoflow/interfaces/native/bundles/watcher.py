"""Event-driven native catalogue updates; fingerprints decide content adoption."""

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import replace
from pathlib import Path

from watchfiles import Change, DefaultFilter, awatch

from astrophotoflow.contracts.development import BundleWatchPath
from astrophotoflow.modules.software.public import bundle_watch_paths, refresh_bundle_sources

logger = logging.getLogger(__name__)


def watch_interests(workspace: Path) -> set[BundleWatchPath]:
    paths = bundle_watch_paths(workspace) | {BundleWatchPath(workspace / 'nodes', directory=True)}
    return {replace(interest, path=interest.path.resolve()) for interest in paths}


def watch_targets(interests: set[BundleWatchPath]) -> set[tuple[Path, bool]]:
    targets = set()
    candidates = {
        (interest.path if interest.directory else interest.path.parent,
         interest.directory and (interest.recursive or interest.watch_subtree))
        for interest in interests
    }
    for path, recursive in candidates:
        while not path.is_dir():
            if path.parent == path:
                raise ValueError('No accessible parent for Bundle watch.')
            path, recursive = path.parent, False
        targets.add((path.resolve(), recursive))
    return {target for target in targets if not any(
        recursive and target[0].is_relative_to(parent) and target != (parent, recursive)
        for parent, recursive in targets)}


def relevant_change(path: Path, interests: set[BundleWatchPath]) -> bool:
    if path.suffix in {'.part', '.pending', '.pyc'} or '__pycache__' in path.parts:
        return False
    for interest in interests:
        root = interest.path
        if path == root or root.is_relative_to(path):
            return True
        if interest.directory and (path.parent == root or interest.recursive and path.is_relative_to(root)):
            return True
    return False


async def watch_workspace(
    workspace: Path,
    fingerprint: Callable[[], str],
    reload: Callable[[], Awaitable[None]],
    initial: str,
) -> None:
    queue: asyncio.Queue[Exception | None] = asyncio.Queue(maxsize=1)
    active: list[asyncio.Task] = []
    pending: list[asyncio.Task] = []
    targets: set[tuple[Path, bool]] = set()
    interests: set[BundleWatchPath] = set()
    default_filter = DefaultFilter()

    def notify(error: Exception | None = None):
        if error is not None and queue.full():
            previous = queue.get_nowait()
            if previous is not None:
                error = previous
        if not queue.full():
            queue.put_nowait(error)

    def accept(change, raw):
        path = Path(raw).resolve()
        return (
            relevant_change(path, interests)
            and (change != Change.modified or not path.is_dir())
            and ('.git' in path.parts or default_filter(change, raw))
        )

    async def monitor(paths: list[Path], recursive: bool, ready: asyncio.Event):
        try:
            async for changes in awatch(*paths, recursive=recursive, watch_filter=accept,
                    debounce=200, step=50, rust_timeout=250, yield_on_timeout=True):
                if not ready.is_set():
                    ready.set()
                    notify()  # Close the initial registration gap exactly once.
                if changes:
                    notify()
        except (OSError, RuntimeError) as exc:
            notify(exc)
        finally:
            ready.set()

    previous = initial
    try:
        while True:
            interests = await asyncio.to_thread(watch_interests, workspace)
            current_targets = watch_targets(interests)
            if current_targets != targets:
                pending, ready_events = [], []
                for recursive in (False, True):
                    paths = [path for path, flag in current_targets if flag == recursive]
                    if paths:
                        ready = asyncio.Event()
                        ready_events.append(ready)
                        pending.append(asyncio.create_task(monitor(paths, recursive, ready)))
                await asyncio.gather(*(ready.wait() for ready in ready_events))
                # Keep old watches until the replacement has registered its paths.
                for task in active:
                    task.cancel()
                await asyncio.gather(*active, return_exceptions=True)
                active, targets = pending, current_targets
                pending = []
            error = await queue.get()
            if error is not None:
                raise error
            await asyncio.to_thread(refresh_bundle_sources, workspace)
            current = await asyncio.to_thread(fingerprint)
            if current != previous:
                await reload()
                previous = current
                # A save can land while the new catalogue is being registered.
                notify()
    finally:
        for task in [*active, *pending]:
            task.cancel()
        await asyncio.gather(*active, *pending, return_exceptions=True)


def watch_bundle_nodes(server) -> None:
    if not (value := os.environ.get('APF_WORKSPACE')):
        return
    from .catalog import bundle_fingerprint, reload_bundle_nodes

    workspace = Path(value)
    server.apf_bundle_lock = asyncio.Lock()
    initial = bundle_fingerprint(workspace)

    async def run():
        try:
            await watch_workspace(workspace, lambda: bundle_fingerprint(workspace),
                                  lambda: reload_bundle_nodes(server), initial)
        except (OSError, ValueError, RuntimeError):
            logger.exception('Bundle event watcher stopped')

    task = server.loop.create_task(run())

    async def close(_app):
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    server.app.on_cleanup.append(close)
