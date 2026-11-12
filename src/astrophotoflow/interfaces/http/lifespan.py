"""Own resources for one serving application, never for schema inspection."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

import httpx
from fastapi import FastAPI

from astrophotoflow.core.database.db import Database
from astrophotoflow.core.localization import workspace_locale
from astrophotoflow.interfaces.application.software_calls import recover_software_calls
from astrophotoflow.interfaces.application.software_previews import BundlePreviews
from astrophotoflow.modules.data.public import (
    DataExports,
    DisplayPreviews,
    MediaViews,
    ThumbnailService,
    configure_library,
    import_workers,
    recover_import_tasks,
    recover_library_organization,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = app.state.settings
    async with AsyncExitStack() as stack:
        database = app.state.database = Database(settings.database_path)
        stack.callback(database.close)
        configure_library(database, settings)
        recover_library_organization(database, settings)
        interrupted = recover_import_tasks(database, locale=workspace_locale(settings.workspace))
        if interrupted:
            logging.getLogger(__name__).info("interrupted_tasks: %s", interrupted)
        app.state.http_client = await stack.enter_async_context(httpx.AsyncClient())
        await recover_software_calls(settings)
        workers = stack.enter_context(import_workers(settings))
        app.state.import_workers = workers
        app.state.display_previews = DisplayPreviews(database, settings, workers[1])
        app.state.media_views = MediaViews(database, settings, workers[1])
        app.state.thumbnails = ThumbnailService(database, settings, workers[1])
        app.state.thumbnails.start()
        stack.callback(app.state.thumbnails.close)
        exports = app.state.data_exports = DataExports(database, settings, workers)
        stack.push_async_callback(asyncio.to_thread, exports.close)
        previews = app.state.bundle_previews = BundlePreviews(database, settings, workers[1], app.state.media_views.cache)
        stack.push_async_callback(previews.close)
        yield
