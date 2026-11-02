from astrophotoflow.modules.software.metadata import contained

"""Execute an optional display-sample operation."""
import asyncio
import os
import subprocess
from pathlib import Path
from uuid import UUID

from astrophotoflow.core.config import Settings
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.software import bundles, development
from astrophotoflow.modules.software.environment import bundle_environment
from astrophotoflow.modules.software.execution.state import LIVE_PREVIEWS
from astrophotoflow.modules.software.packages.catalog import get_package
from astrophotoflow.modules.software.packages.maintenance import PACKAGE_LOCKS


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
        raise ApiError(503, "SOFTWARE_NOT_READY", package.effective_reason or "请先在软件包页面安装 Siril。", message_key='siril_install_required', fields=[{'path': 'software', 'message': package.effective_reason}] if package.effective_reason else [])
    lock = PACKAGE_LOCKS.get(package_id)
    if lock is not None and lock.locked():
        raise ApiError(409, "SOFTWARE_BUSY", "Siril 正在维护。", message_key='siril_is_undergoing_maintenance')
    root = (settings.data_dir / "previews").resolve()
    if not directory.resolve().is_relative_to(root) or (not prepare_sample and not source.resolve().is_relative_to(root)):
        raise ApiError(422, "INVALID_REFERENCE", "实时预览仅接受平台生成的显示样本。", message_key='live_previews_accept_only_platform_generated_display_samples')
    job_id = UUID(directory.name)
    LIVE_PREVIEWS[job_id] = (package_id, None)
    process = None
    try:
        directory.mkdir(parents=True, exist_ok=False)
        plan = bundles.adapter_plan(settings.workspace, package_id, operation_id, {'image': [source]}, parameters,
                                    directory, preview=True, prepare_sample=prepare_sample and preview_max_edge == 1024)
        target = plan.outputs['image'].files[0].path
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
            raise ApiError(422, "SIRIL_PREVIEW_FAILED", "Siril 实时预览未完成：" + detail, message_key='siril_live_preview_failed', fields=[{'path': 'software_log', 'message': detail}])
        if prepare_sample:
            after = source.stat()
            if (source_stamp.st_size, source_stamp.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ApiError(409, "SOURCE_CHANGED", "准备预览时原件发生变化。", message_key='the_original_changed_while_preparing_the_preview')
            if preview_max_edge == 1024:
                plan.linear_sample.replace(directory.parent / "linear.fit")
        return target
    except asyncio.CancelledError:
        if process is not None:
            await stop_preview(process)
        raise
    finally:
        if process is None or process.returncode is not None:
            LIVE_PREVIEWS.pop(job_id, None)

