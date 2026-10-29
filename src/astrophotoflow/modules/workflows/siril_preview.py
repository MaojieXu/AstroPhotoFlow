import asyncio
from concurrent.futures import CancelledError
from io import BytesIO
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4
import shutil

from fastapi import APIRouter, Depends, Request, Response

from astrophotoflow.contracts.software import SirilPreviewRequest
from astrophotoflow.core.http import authenticate, ERROR_RESPONSES
from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.public import prepare_siril_sample, direct_fits_image
from astrophotoflow.modules.software.public import preview_autostretch, get_package


router = APIRouter(prefix="/api/v1/software/packages/siril", dependencies=[Depends(authenticate)], responses=ERROR_RESPONSES)


class SirilPreviews:
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

    async def render(self, body: SirilPreviewRequest):
        consumer = body.consumer_id
        if body.generation <= self.generations.get(consumer, -1):
            raise ApiError(409, "STALE_VIEW", "该实时预览请求已过期。")
        self.generations[consumer] = body.generation
        old = self.active.get(consumer)
        if old is not None:
            if not old.cancelling():
                old.cancel()
            await asyncio.gather(old, return_exceptions=True)
        if self.generations.get(consumer) != body.generation:
            raise ApiError(409, "STALE_VIEW", "该实时预览请求已被更新。")
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

            work = self.executor.submit(prepare_siril_sample, self.database, self.settings, self.cache, body, checkpoint)
            sample = None
            directory = None
            future = None
            error = None
            try:
                sample = await asyncio.shield(asyncio.wrap_future(work))
                directory = sample.folder / str(uuid4())
                if sample.path != sample.folder / "linear.fit":
                    result = await preview_autostretch(self.settings, sample.path, directory, body, prepare_sample=True)
                else:
                    result = await preview_autostretch(self.settings, sample.path, directory, body)
                future = self.executor.submit(direct_fits_image, result, 0, 1024)
                image = await asyncio.shield(asyncio.wrap_future(future))
                stream = BytesIO()
                image.save(stream, format="PNG")
                self.cache.write(sample.folder / "result.png", stream.getvalue())
                return stream.getvalue()
            except asyncio.CancelledError as exc:
                cancelled.set()
                error = exc
                if sample is None:
                    if not work.cancel():
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


@router.post("/autostretch-preview", response_class=Response,
             responses={200: {"content": {"image/png": {"schema": {"type": "string", "format": "binary"}}}}})
async def preview(body: SirilPreviewRequest, request: Request):
    package = get_package(request.app.state.settings, "siril")
    if package.availability != "ready":
        raise ApiError(503, "SOFTWARE_NOT_READY", package.reason or "请先安装 Siril。")
    manager = request.app.state.siril_previews
    async with request.app.state.maintenance_lock:
        if request.app.state.maintenance or request.app.state.shutdown_started:
            raise ApiError(409, "WORKBENCH_MAINTENANCE", "工作台正在维护。")
        operation = manager.start(body)
    try:
        while not operation.done():
            await asyncio.wait({operation}, timeout=0.1)
            if await request.is_disconnected():
                operation.cancel()
                await asyncio.gather(operation, return_exceptions=True)
                raise ApiError(409, "PREVIEW_CANCELLED", "实时预览请求已关闭。")
        return Response(await operation, media_type="image/png", headers={"Cache-Control": "no-store"})
    except asyncio.CancelledError:
        operation.cancel()
        await asyncio.gather(operation, return_exceptions=True)
        raise


@router.delete("/autostretch-preview/{consumer_id}", status_code=204, response_class=Response)
async def release(consumer_id: UUID, request: Request):
    await request.app.state.siril_previews.cancel(consumer_id)
    return Response(status_code=204)
