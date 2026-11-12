from astrophotoflow.modules.software.metadata import contained

"""Execute an optional display-sample operation."""
import asyncio
import json
import os
import subprocess
from pathlib import Path
from uuid import UUID

from astrophotoflow.contracts.bundles import BundlePreview
from astrophotoflow.core.config import Settings
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.software import bundles, development
from astrophotoflow.modules.software.environment import bundle_environment
from astrophotoflow.modules.software.execution.state import LIVE_PREVIEWS
from astrophotoflow.modules.software.packages.catalog import get_package
from astrophotoflow.modules.software.packages.maintenance import PACKAGE_LOCKS


def get_preview_definition(settings, package_id, operation_id) -> BundlePreview:
    _, entries, _ = bundles.metadata(settings.workspace, package_id)
    entry = next((item for item in entries if item['operation']['operation_id'] == operation_id), None)
    if entry is None or entry.get('preview') is None:
        raise ApiError(422, 'UNSUPPORTED_SELECTION', 'Operation does not provide a sample preview.', message_key='forwarded_service_error', message_params={'message': 'Operation does not provide a sample preview.'})
    preview = BundlePreview.model_validate(entry['preview'])
    inputs = {item['name'] for item in entry['operation']['inputs'] if item.get('data_kind', 'image') == 'image'}
    outputs = {item['name'] for item in entry['operation']['outputs'] if item['type'] == 'APF_SCIENCE' and 'fits' in item['formats']}
    output = preview.output if preview.output is not None else next(iter(outputs)) if len(outputs) == 1 else None
    if preview.input not in inputs or output not in outputs:
        raise ValueError('Bundle preview must identify an image input and output.')
    return preview.model_copy(update={'output': output})


async def stop_preview(process):
    if process.returncode is None:
        try:
            process.terminate()
        except ProcessLookupError:
            pass
    await asyncio.shield(process.wait())


async def preview_operation(settings: Settings, source: Path, directory: Path, parameters, *, package_id: str, operation_id: str, prepare_sample: bool = False, preview_max_edge: int | None = 1024) -> Path:
    package = get_package(settings, package_id)
    if package.effective_availability != "ready":
        raise ApiError(503, "SOFTWARE_NOT_READY", package.effective_reason or "请先在软件包页面安装软件。", message_key='bundle_preview_install_required', fields=[{'path': 'software', 'message': package.effective_reason}] if package.effective_reason else [])
    lock = PACKAGE_LOCKS.get(package_id)
    if lock is not None and lock.locked():
        raise ApiError(409, "SOFTWARE_BUSY", "软件包正在维护。", message_key='bundle_preview_maintenance')
    root = (settings.data_dir / "previews").resolve()
    if not directory.resolve().is_relative_to(root) or (not prepare_sample and not source.resolve().is_relative_to(root)):
        raise ApiError(422, "INVALID_REFERENCE", "实时预览仅接受平台生成的显示样本。", message_key='live_previews_accept_only_platform_generated_display_samples')
    job_id = UUID(directory.name)
    LIVE_PREVIEWS[job_id] = (package_id, None)
    process = None
    try:
        directory.mkdir(parents=True, exist_ok=False)
        preview = get_preview_definition(settings, package_id, operation_id)
        prepare_cached_sample = prepare_sample and preview_max_edge == preview.max_edge
        plan = bundles.adapter_plan(settings.workspace, package_id, operation_id, {preview.input: [source]}, parameters,
                                    directory, preview=True, prepare_sample=prepare_cached_sample)
        output = plan.outputs.get(preview.output)
        if output is None or len(output.files) != 1 or output.files[0].format != 'fits':
            raise ValueError('Bundle preview must produce exactly one declared image file.')
        target = output.files[0].path
        plan.temporary_directory.mkdir(parents=True, exist_ok=True)
        environment = {**os.environ, **plan.environment, **{name: str(plan.temporary_directory) for name in ('TEMP', 'TMP', 'TMPDIR')}}
        if plan.thread_limit is not None:
            environment.update(OPENBLAS_NUM_THREADS=str(plan.thread_limit), OMP_NUM_THREADS=str(plan.thread_limit))
        source_stamp = source.stat()
        log = directory / "preview.log"
        executable = contained(development.source_root(settings.workspace, package_id), bundles.metadata(settings.workspace, package_id)[0].executable)
        with log.open("wb") as stream:
            spawn = asyncio.create_task(asyncio.create_subprocess_exec(
                str(executable), *plan.arguments, cwd=directory,
                stdout=stream, stderr=asyncio.subprocess.STDOUT, env={**bundle_environment(executable), **{key: value for key, value in (environment or {}).items() if key.upper() != "PATH"}},
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            ))
            try:
                process = await asyncio.shield(spawn)
            except asyncio.CancelledError:
                process = await asyncio.shield(spawn)
                await stop_preview(process)
                raise
            LIVE_PREVIEWS[job_id] = (package_id, process)
            code = await process.wait()
        if code != 0 or not target.is_file():
            detail = log.read_text(encoding="utf-8", errors="replace")[-2000:]
            raise ApiError(422, "BUNDLE_PREVIEW_FAILED", "软件实时预览未完成：" + detail, message_key='bundle_preview_failed', fields=[{'path': 'software_log', 'message': detail}])
        if prepare_sample:
            after = source.stat()
            if (source_stamp.st_size, source_stamp.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ApiError(409, "SOURCE_CHANGED", "准备预览时原件发生变化。", message_key='the_original_changed_while_preparing_the_preview')
            if prepare_cached_sample and plan.linear_sample is not None:
                cached = directory.parent / ('sample' + ''.join(plan.linear_sample.suffixes))
                plan.linear_sample.replace(cached)
                (directory.parent / 'manifest.json').write_text(json.dumps({'input': cached.name, 'output': 'result.png'}), encoding='utf-8')
        return target
    except asyncio.CancelledError:
        if process is not None:
            await stop_preview(process)
        raise
    finally:
        if process is None or process.returncode is not None:
            LIVE_PREVIEWS.pop(job_id, None)
