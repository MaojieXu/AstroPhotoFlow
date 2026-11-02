from astrophotoflow.interfaces.http.data.assets import router as asset_router
from astrophotoflow.interfaces.http.data.batches import router as batch_router
from astrophotoflow.interfaces.http.data.calibration import router as calibration_router
from astrophotoflow.interfaces.http.data.canvas import router as data_canvas_router
from astrophotoflow.interfaces.http.data.content import router as content_router
from astrophotoflow.interfaces.http.data.datasets import router as dataset_router
from astrophotoflow.interfaces.http.data.imports import router as import_router
from astrophotoflow.interfaces.http.data.inspection import router as inspection_router
from astrophotoflow.interfaces.http.data.library import router as library_router
from astrophotoflow.interfaces.http.data.media import router as media_router
from astrophotoflow.interfaces.http.data.previews import router as preview_router
from astrophotoflow.interfaces.http.data.projects import router as project_router
from astrophotoflow.interfaces.http.data.trash import router as trash_router
from astrophotoflow.interfaces.http.schema import register_native_schemas

"""Assemble the HTTP surface without opening serving resources."""

import asyncio

from fastapi import FastAPI

from astrophotoflow.contracts.common import ErrorEnvelope
from astrophotoflow.core.config import Settings
from astrophotoflow.interfaces.application.package_actions import register_package_actions
from astrophotoflow.interfaces.http import system
from astrophotoflow.interfaces.http.canvas import router as canvas_router
from astrophotoflow.interfaces.http.data.equipment import router as equipment_router
from astrophotoflow.interfaces.http.data.exports import router as export_router
from astrophotoflow.interfaces.http.data.management import equipment_router as equipment_management_router
from astrophotoflow.interfaces.http.data.management import router as management_router
from astrophotoflow.interfaces.http.data.presets import router as preset_router
from astrophotoflow.interfaces.http.data.result_media import router as result_media_router
from astrophotoflow.interfaces.http.data.results import router as data_node_router
from astrophotoflow.interfaces.http.data.setups import router as setup_router
from astrophotoflow.interfaces.http.errors import register_error_handlers
from astrophotoflow.interfaces.http.lifespan import lifespan
from astrophotoflow.interfaces.http.maintenance import register_maintenance
from astrophotoflow.interfaces.http.native_pages import register_native_pages
from astrophotoflow.interfaces.http.nodes import router as nodes_router
from astrophotoflow.interfaces.http.software import router as software_router
from astrophotoflow.interfaces.http.software_calls import router as software_call_router
from astrophotoflow.interfaces.http.software_previews import router as software_preview_router


def create_app(settings: Settings, token: str) -> FastAPI:
    app = FastAPI(
        lifespan=lifespan, title="AstroPhotoFlow Asset Service", version="1.0.0",
        docs_url=None, redoc_url=None,
        responses={422: {"model": ErrorEnvelope}, "default": {"model": ErrorEnvelope}},
    )
    app.state.settings = settings
    app.state.token = token
    app.state.data_exports = None
    app.state.bundle_previews = None
    app.state.maintenance_lock = asyncio.Lock()
    app.state.maintenance = False
    app.state.maintenance_owner = None
    app.state.shutdown_started = False
    for router in (library_router, data_canvas_router, canvas_router, data_node_router, export_router, software_preview_router):
        app.include_router(router)
    register_package_actions(app, settings, token)
    app.state.software_calls = {}
    app.include_router(software_call_router)
    app.include_router(result_media_router)
    register_maintenance(app, settings)
    register_native_pages(app, settings)
    register_error_handlers(app)
    for router in (media_router, preview_router, inspection_router, batch_router, content_router, system.router, management_router, equipment_management_router, trash_router, import_router, asset_router, project_router, equipment_router, setup_router, preset_router, dataset_router, calibration_router, software_router, nodes_router):
        app.include_router(router)
    register_native_schemas(app)
    return app
