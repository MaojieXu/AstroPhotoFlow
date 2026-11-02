from typing import Annotated, Literal

from pydantic import Field, JsonValue

from astrophotoflow.contracts.common import ErrorDetail, JsonObject, StrictModel, UuidInput
from astrophotoflow.contracts.inputs import CanvasDataOut, CanvasDataRequest
from astrophotoflow.contracts.nodes import SavedDefinition


class CanvasPageState(StrictModel):
    workflow_id: UuidInput
    graph_id: UuidInput
    title: str
    content_token: str


class CanvasPageOut(CanvasPageState):
    page_id: UuidInput


class CanvasAddRequest(StrictModel):
    operation_id: UuidInput
    page_id: UuidInput
    workflow_id: UuidInput
    graph_id: UuidInput
    content_token: str
    source: CanvasDataRequest


class CanvasAddResult(StrictModel):
    operation_id: UuidInput
    page_id: UuidInput
    workflow_id: UuidInput
    graph_id: UuidInput
    applied: bool | None
    node_id: str | int | None
    error: ErrorDetail | None
    graph: JsonObject | None = None
    link_id: str | int | None = None
    content_token: str | None = None


class NativeCanvasCommand(StrictModel):
    request: CanvasAddRequest
    data: CanvasDataOut


class CanvasInspect(StrictModel):
    action: Literal['inspect']


class CanvasCreateNode(StrictModel):
    action: Literal['add_node']
    definition_id: UuidInput
    parameters: dict[str, JsonValue] = Field(default_factory=dict)


class CanvasSetParameter(StrictModel):
    action: Literal['set_parameter']
    node_id: str | int
    name: str
    value: JsonValue


class CanvasDeleteNode(StrictModel):
    action: Literal['delete_node']
    node_id: str | int


class CanvasConnect(StrictModel):
    action: Literal['connect']
    source_node_id: str | int
    source_port: str
    target_node_id: str | int
    target_port: str


CanvasEdit = Annotated[CanvasInspect | CanvasCreateNode | CanvasSetParameter | CanvasDeleteNode | CanvasConnect, Field(discriminator='action')]


class CanvasGraphRequest(StrictModel):
    operation_id: UuidInput
    page_id: UuidInput
    workflow_id: UuidInput
    graph_id: UuidInput
    content_token: str
    edit: CanvasEdit


class NativeCanvasGraphCommand(StrictModel):
    request: CanvasGraphRequest
    definition: SavedDefinition | None = None


class NativeCanvasStateEvent(StrictModel):
    action: Literal["state"]
    state: CanvasPageState | None


class NativeCanvasResultEvent(StrictModel):
    action: Literal["result"]
    result: CanvasAddResult


NativeCanvasEvent = Annotated[NativeCanvasStateEvent | NativeCanvasResultEvent, Field(discriminator="action")]


NativeCanvasMessage = NativeCanvasCommand | NativeCanvasGraphCommand
