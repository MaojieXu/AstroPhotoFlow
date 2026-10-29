from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, JsonValue

from astrophotoflow.contracts.common import ErrorDetail, JsonObject, StrictModel, UuidInput
from astrophotoflow.contracts.nodes import DefinitionWriteResult, NativeNodeLoad, SavedDefinition
from astrophotoflow.contracts.software import ConfirmSoftwareEvent, SoftwarePackage
from astrophotoflow.contracts.inputs import CanvasDataOut, CanvasDataRequest


SoftwareActionKind = Literal["install", "update", "uninstall"]


class CanvasPageState(StrictModel):
    workflow_id: UuidInput
    graph_id: UuidInput
    title: str
    content_token: str
    control_token: str | None


class CanvasPageOut(CanvasPageState):
    page_id: UuidInput


class CanvasAddRequest(StrictModel):
    operation_id: UuidInput
    page_id: UuidInput
    workflow_id: UuidInput
    graph_id: UuidInput
    content_token: str
    control_token: str
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


class CanvasConnect(StrictModel):
    action: Literal['connect']
    source_node_id: str | int
    source_port: str
    target_node_id: str | int
    target_port: str


CanvasEdit = Annotated[CanvasInspect | CanvasCreateNode | CanvasSetParameter | CanvasConnect, Field(discriminator='action')]


class CanvasGraphRequest(StrictModel):
    operation_id: UuidInput
    page_id: UuidInput
    workflow_id: UuidInput
    graph_id: UuidInput
    content_token: str
    control_token: str | None
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


class WorkflowImpact(StrictModel):
    project_id: UUID
    workflow_id: UUID
    path: str
    content_token: str
    node_execution_ids: list[str]
    parameter_defaults: dict[str, JsonObject]
    retained_link_ids: list[int]
    disconnected_link_ids: list[int]
    missing_definition_ids: list[UUID]
    unsaved_pages: list[UUID]


class SoftwarePlanNodeChange(StrictModel):
    definition_id: UUID
    name: str
    action: Literal["create", "update", "remove", "retain"]
    before_content_token: str | None
    after_content_token: str | None


class SoftwarePlanSummary(StrictModel):
    action: SoftwareActionKind
    package_id: str
    current_version: str | None
    target_version: str | None
    source: str | None
    install_path: Path | None
    package_token: str
    impact_token: str | None
    restart_required: bool | None
    restart_reason: str | None
    node_changes: list[SoftwarePlanNodeChange]
    workflow_impacts: list[WorkflowImpact]


class PendingSoftwareAction(StrictModel):
    operation_id: UuidInput
    state: Literal["awaiting_confirmation", "running", "completed", "failed", "expired", "unknown"]
    plan: SoftwarePlanSummary
    confirmation_url: str
    error: ErrorDetail | None


class NativeWorkflowChangeResult(StrictModel):
    operation_id: UUID
    project_id: UUID
    workflow_id: UUID
    path: str
    file_saved: bool | None
    association_saved: bool | None
    saved_file_sha256: str | None
    error: ErrorDetail | None = None


class WorkflowChangeResult(StrictModel):
    workflow_id: UUID
    applied: bool | None
    save: NativeWorkflowChangeResult | None
    error: ErrorDetail | None


class PackageMutationResult(StrictModel):
    package: SoftwarePackage
    definition_results: list[DefinitionWriteResult]
    loads: list[NativeNodeLoad]
    workflow_results: list[WorkflowChangeResult]
    error: ErrorDetail | None


class SoftwarePackageDetails(StrictModel):
    package: SoftwarePackage
    current_action: PendingSoftwareAction | None
    result: PackageMutationResult | None


class NativePageOpenEvent(StrictModel):
    event_id: UuidInput
    page_id: UuidInput
    page_token: str
    action: Literal["open"]
    payload: None


class NativePageCloseEvent(StrictModel):
    event_id: UuidInput
    page_id: UuidInput
    page_token: str
    action: Literal["close"]
    payload: None


class NativePageConfirmSoftwareEvent(StrictModel):
    event_id: UuidInput
    page_id: UuidInput
    page_token: str
    action: Literal["confirm_software"]
    payload: ConfirmSoftwareEvent


NativePageEvent = Annotated[
    NativePageOpenEvent | NativePageCloseEvent | NativePageConfirmSoftwareEvent,
    Field(discriminator="action"),
]


class NativePageReply(StrictModel):
    event_id: UUID
    page_id: UUID
    page_token: str
    result: PendingSoftwareAction | None
    error: ErrorDetail | None
