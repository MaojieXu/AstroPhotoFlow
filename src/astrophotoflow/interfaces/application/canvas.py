"""Concrete canvas use cases; ComfyUI owns the graph and its lifecycle."""

from dataclasses import dataclass

import astrophotoflow.modules.data.public as data
import astrophotoflow.modules.nodes.public as nodes
from astrophotoflow.contracts.canvas import (
    CanvasAddRequest,
    CanvasAddResult,
    CanvasGraphRequest,
    NativeCanvasCommand,
    NativeCanvasGraphCommand,
)
from astrophotoflow.core.config import Settings
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.errors import ApiError
from astrophotoflow.interfaces.native.client import NativeClient


@dataclass(frozen=True)
class CanvasDependencies:
    settings: Settings
    database: Database
    native: NativeClient


async def add_canvas_data(dependencies: CanvasDependencies, body: CanvasAddRequest) -> CanvasAddResult:
    prepared = data.prepare_canvas_data(dependencies.database, body.source)
    return await dependencies.native.send(NativeCanvasCommand(request=body, data=prepared))


async def edit_canvas(dependencies: CanvasDependencies, body: CanvasGraphRequest) -> CanvasAddResult:
    definition = None
    if body.edit.action == "add_node":
        capability = nodes.describe_node(dependencies.settings, body.edit.definition_id)
        if not capability.available:
            reason = capability.reason or "节点依赖尚未就绪。"
            raise ApiError(409, "SOFTWARE_NOT_READY", reason, message_key="node_software_not_ready",
                           fields=[{"path": "diagnostic", "message": reason}])
        definition = capability.node
    return await dependencies.native.send(NativeCanvasGraphCommand(request=body, definition=definition))
