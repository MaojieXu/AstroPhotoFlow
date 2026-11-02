"""Observe and stop concrete process trees truthfully."""
import asyncio
import codecs
from datetime import UTC, datetime
from pathlib import Path

import psutil

from astrophotoflow.modules.software.execution.state import ObservationFailed


def capture_descendants(call):
    runtime = call.observation.runtime_ref
    if call.process is None or runtime is None or call.process.returncode is not None:
        return False
    try:
        parent = psutil.Process(call.process.pid)
        if parent.create_time() != runtime['create_time']:
            return False
        for child in parent.children(recursive=True):
            call.descendants[child.pid] = child.create_time()
        call.inspection_unknown = False
    except psutil.NoSuchProcess:
        pass
    except psutil.AccessDenied:
        call.inspection_unknown = True
    children = [{'pid': pid, 'create_time': created} for pid, created in sorted(call.descendants.items())]
    updated = {**runtime, 'children': children, 'children_unknown': call.inspection_unknown}
    changed = updated != runtime
    call.observation = call.observation.model_copy(update={'runtime_ref': updated})
    return changed


async def watch_process(call, task, log, reader, observe):
    decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
    pending = ''
    with log.open('rb') as stream:
        while True:
            await asyncio.wait({task}, timeout=0.25)
            changed = capture_descendants(call)
            pending += decoder.decode(stream.read())
            end = pending.rfind('\n')
            if reader is not None and end >= 0:
                progress = reader(pending[:end + 1])
                if progress.phase is not None or progress.progress is not None:
                    phase = progress.phase if progress.phase is not None else call.observation.phase
                    changed = changed or (phase, progress.progress) != (call.observation.phase, call.observation.progress)
                    call.observation = call.observation.model_copy(update={'phase': phase, 'progress': progress.progress})
                pending = pending[end + 1:]
            elif reader is None:
                pending = ''
            if changed:
                call.observation = call.observation.model_copy(update={'observed_at': datetime.now(UTC)})
                try:
                    await observe(call.observation)
                except Exception as exc:
                    raise ObservationFailed(str(exc)) from exc
            if task.done():
                return task.result()


async def stop_call(call):
    capture_descendants(call)
    children = []
    for pid, created in call.descendants.items():
        try:
            child = psutil.Process(pid)
            if child.create_time() == created:
                child.terminate()
                children.append(child)
        except psutil.NoSuchProcess:
            pass
        except psutil.AccessDenied:
            call.inspection_unknown = True
    if call.process is not None and call.process.returncode is None:
        try:
            call.process.terminate()
        except ProcessLookupError:
            pass
    waits = [asyncio.to_thread(psutil.wait_procs, children, timeout=5)] if children else []
    if call.process is not None:
        waits.append(call.process.wait())
    try:
        await asyncio.wait_for(asyncio.gather(*waits), timeout=5)
    except TimeoutError:
        return None
    if call.inspection_unknown:
        return None
    return runtime_active(call.observation.runtime_ref) if call.observation.runtime_ref else None


def runtime_active(runtime) -> bool | None:
    unknown = runtime.get('children_unknown', False)
    try:
        process = psutil.Process(runtime["pid"])
        if process.create_time() == runtime["create_time"] and \
            Path(process.exe()).resolve() == Path(runtime["executable"]).resolve() and process.is_running():
            return True
    except psutil.NoSuchProcess:
        pass
    except psutil.AccessDenied:
        unknown = True
    for child in runtime.get('children', []):
        try:
            process = psutil.Process(child['pid'])
            if process.create_time() == child['create_time'] and process.is_running():
                return True
        except psutil.NoSuchProcess:
            pass
        except psutil.AccessDenied:
            unknown = True
    return None if unknown else False
