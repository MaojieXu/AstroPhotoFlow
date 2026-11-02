"""Optional fixed-input software previews assembled from public data/software capabilities."""

import asyncio
import json
import shutil
from concurrent.futures import CancelledError
from io import BytesIO
from threading import Event
from uuid import UUID, uuid4

from astrophotoflow.contracts.software import BundlePreviewRequest
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.public import direct_fits_image, prepare_siril_sample
from astrophotoflow.modules.software.public import get_operation, get_package, preview_operation, validate_parameters


class BundlePreviews:
    def __init__(self, database, settings, executor, cache):
        self.database, self.settings, self.executor, self.cache = database, settings, executor, cache
        self.generations = {}
        self.active = {}
        self.requests = set()
        self.slots = asyncio.Semaphore(settings.preview_workers)

    def start(self, body):
        task = asyncio.create_task(self.render(body))
        self.requests.add(task)
        task.add_done_callback(self.requests.discard)
        return task

    async def render(self, body: BundlePreviewRequest):
        consumer = body.consumer_id
        if body.generation <= self.generations.get(consumer, -1):
            raise ApiError(409, "STALE_VIEW", "该实时预览请求已过期。", message_key='this_live_preview_request_has_expired')
        self.generations[consumer] = body.generation
        old = self.active.get(consumer)
        if old is not None:
            if not old.cancelling():
                old.cancel()
            await asyncio.gather(old, return_exceptions=True)
        if self.generations.get(consumer) != body.generation:
            raise ApiError(409, "STALE_VIEW", "该实时预览请求已被更新。", message_key='a_newer_request_replaced_this_live_preview_request')
        task = asyncio.create_task(self._render(body))
        self.active[consumer] = task
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            if not task.cancelling():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise
        finally:
            if self.active.get(consumer) is task:
                self.active.pop(consumer, None)

    async def _render(self, body):
        async with self.slots:
            cancelled = Event()

            def checkpoint():
                if cancelled.is_set():
                    raise CancelledError("实时预览已取消。")

            package = get_package(self.settings, body.package_id)
            operation = get_operation(self.settings, body.package_id, package.effective_version, body.operation_id)
            layout = next(item.colour_layout for item in operation.inputs if item.name == 'image')
            decoder_key = json.dumps([body.package_id, package.effective_version, package.effective_bundle_commit,
                package.development_source.fingerprint if package.development_source else None, body.parameters.get('runtime', '{}')], sort_keys=True)
            work = self.executor.submit(prepare_siril_sample, self.database, self.settings, self.cache, body, checkpoint, decoder_key, layout)
            sample = None
            directory = None
            future = None
            error = None
            try:
                sample = await asyncio.shield(asyncio.wrap_future(work))
                directory = sample.folder / str(uuid4())
                if sample.path != sample.folder / "linear.fit":
                    result = await preview_operation(self.settings, sample.path, directory, body.parameters, package_id=body.package_id, operation_id=body.operation_id, prepare_sample=True, preview_max_edge=body.preview_max_edge)
                else:
                    result = await preview_operation(self.settings, sample.path, directory, body.parameters, package_id=body.package_id, operation_id=body.operation_id)
                future = self.executor.submit(direct_fits_image, result, None, body.preview_max_edge, display_balance=body.display_balance)
                image = await asyncio.shield(asyncio.wrap_future(future))
                stream = BytesIO()
                image.save(stream, format="PNG")
                self.cache.write(sample.folder / "result.png", stream.getvalue())
                return stream.getvalue()
            except asyncio.CancelledError as exc:
                cancelled.set()
                error = exc
                if sample is None and not work.cancel():
                    try:
                        sample = await asyncio.shield(asyncio.wrap_future(work))
                    except (CancelledError, asyncio.CancelledError):
                        pass
                if future is not None and not future.done():
                    await asyncio.shield(asyncio.wrap_future(future))
                raise
            except BaseException as exc:
                error = exc
                raise
            finally:
                try:
                    if directory is not None and directory.exists():
                        await asyncio.to_thread(shutil.rmtree, directory)
                finally:
                    if sample is not None:
                        sample.close(error)

    async def cancel(self, consumer: UUID):
        self.generations[consumer] = 2**63 - 1
        task = self.active.get(consumer)
        if task is not None:
            if not task.cancelling():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def close(self):
        requests = list(self.requests)
        for task in requests:
            if not task.cancelling():
                task.cancel()
        await asyncio.gather(*requests, return_exceptions=True)
        await asyncio.gather(*(self.cancel(consumer) for consumer in list(self.active)))



def start_preview(manager: BundlePreviews, body: BundlePreviewRequest):
    package = get_package(manager.settings, body.package_id)
    if package.effective_availability != 'ready':
        reason = package.effective_reason or '请先安装所选软件。'
        raise ApiError(503,'SOFTWARE_NOT_READY',reason,message_key='forwarded_service_error',message_params={'message':reason},fields=[{'path':'diagnostic','message':reason}])
    validate_parameters(manager.settings,body.package_id,body.operation_id,body.parameters)
    return manager.start(body)
