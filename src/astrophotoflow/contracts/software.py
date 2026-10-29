from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from math import isfinite

from pydantic import Field, JsonValue, field_validator, model_validator

from astrophotoflow.contracts.common import ErrorDetail, JsonObject, StrictModel, UuidInput, check_name
from astrophotoflow.contracts.inputs import InputReference, OutputLocator, ResolvedInput, ScienceFormat


class ParameterDefinition(StrictModel):
    name: str
    kind: Literal["int", "float", "string", "boolean", "choice"]
    default: JsonValue
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    choices: list[JsonValue] | None = None
    advanced: bool = False
    nullable: bool = False

    _name = field_validator("name")(check_name)

    @model_validator(mode="after")
    def valid_default_and_constraints(self):
        value = self.default
        if value is None:
            if not self.nullable:
                raise ValueError("非nullable参数不能使用null默认值。")
        elif self.kind == "int" and (not isinstance(value, int) or isinstance(value, bool)):
            raise ValueError("int参数默认值必须是整数。")
        elif self.kind == "float" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
            raise ValueError("float参数默认值必须是数值。")
        elif self.kind == "string" and not isinstance(value, str):
            raise ValueError("string参数默认值必须是字符串。")
        elif self.kind == "boolean" and not isinstance(value, bool):
            raise ValueError("boolean参数默认值必须是布尔值。")
        if self.minimum is not None and not isfinite(self.minimum):
            raise ValueError("参数minimum必须是有限值。")
        if self.maximum is not None and not isfinite(self.maximum):
            raise ValueError("参数maximum必须是有限值。")
        if self.step is not None and (not isfinite(self.step) or self.step <= 0):
            raise ValueError("参数step必须是正有限值。")
        if self.kind in {"int", "float"}:
            if value is not None and not isfinite(value):
                raise ValueError("数值参数默认值必须是有限值。")
            if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
                raise ValueError("参数minimum不能大于maximum。")
            if value is not None and self.minimum is not None and value < self.minimum:
                raise ValueError("参数默认值不能小于minimum。")
            if value is not None and self.maximum is not None and value > self.maximum:
                raise ValueError("参数默认值不能大于maximum。")
        elif self.minimum is not None or self.maximum is not None or self.step is not None:
            raise ValueError("minimum、maximum和step只用于数值参数。")
        if self.kind == "choice":
            if self.choices is None or value not in self.choices:
                raise ValueError("choice参数默认值必须存在于choices中。")
        elif self.choices is not None:
            raise ValueError("choices只用于choice参数。")
        return self


class SoftwareInputDefinition(StrictModel):
    name: str
    type: str
    formats: list[ScienceFormat]
    cardinality: Literal["one", "many"]
    required: bool
    supports_hdu: bool | None
    supports_slice: bool | None


class SoftwareOutputDefinition(StrictModel):
    name: str
    type: str
    formats: list[ScienceFormat]
    cardinality: Literal["one", "many"]


class SoftwareOperation(StrictModel):
    package_id: str
    version: str
    operation_id: str
    name: str
    description: str
    syntax: str
    scriptable: bool
    inputs: list[SoftwareInputDefinition]
    outputs: list[SoftwareOutputDefinition]
    parameters: list[ParameterDefinition]
    content_token: str
    ready: bool
    reason: str | None = None
    cancel_supported: bool | None


class SoftwarePackage(StrictModel):
    package_id: str
    name: str
    available_versions: list[str]
    installed_version: str | None
    install_path: Path | None
    package_token: str
    availability: Literal["not_installed", "ready", "not_ready", "unknown"]
    reason: str | None = None
    operation: Literal["install", "prepare", "update", "uninstall"] | None = None
    operation_state: Literal["idle", "running", "completed", "failed", "unknown"]
    phase: str | None = None
    progress: float | None = Field(default=None, ge=0, le=1)
    last_error: ErrorDetail | None = None
    node_definition_ids: list[UUID]
    bundle_version: str | None = None
    bundle_commit: str | None = None
    restart_required: bool = False
    migration_required: bool = False


class SoftwarePackageState(StrictModel):
    installed_version: str | None
    install_path: Path | None
    availability: Literal["not_installed", "ready", "not_ready", "unknown"]
    reason: str | None
    operation: Literal["install", "prepare", "update", "uninstall"] | None
    operation_state: Literal["idle", "running", "completed", "failed", "unknown"]
    phase: str | None
    progress: float | None = Field(default=None, ge=0, le=1)
    last_error: ErrorDetail | None
    node_definition_ids: list[UUID]


class SoftwarePreparation(StrictModel):
    package: SoftwarePackage
    user_action: str | None
    ui_kind: Literal["software", "platform"] | None
    ui_target: str | None


class SoftwareInstallRequest(StrictModel):
    version: str
    package_token: str


class SoftwareUninstallRequest(StrictModel):
    package_token: str


class SoftwareInvocation(StrictModel):
    run_id: UUID
    node_execution_id: str
    call_id: UUID
    package_id: str
    version: str
    operation_id: str
    operation_content_token: str
    inputs: dict[str, list[ResolvedInput]]
    parameters: dict[str, JsonValue]
    work_directory: Path


class ProducedFile(StrictModel):
    path: Path
    format: ScienceFormat


class SoftwareObservation(StrictModel):
    run_id: UUID
    node_execution_id: str
    call_id: UUID
    observed_at: datetime
    active: bool | None
    runtime_ref: JsonObject | None
    state: Literal["starting", "running", "completed", "failed", "cancelled", "unknown"]
    phase: str | None = None
    progress: float | None = Field(default=None, ge=0, le=1)
    log_path: Path | None = None
    exit_code: int | None = None
    error: ErrorDetail | None = None


class SoftwareResult(StrictModel):
    call_id: UUID
    state: Literal["completed", "failed", "cancelled", "unknown"]
    started_at: datetime
    ended_at: datetime | None
    exit_code: int | None
    outputs: dict[str, list[ProducedFile]]
    log_path: Path | None
    error: ErrorDetail | None


class SoftwareCancelResult(StrictModel):
    call_id: UUID
    request_state: Literal["sent", "not_supported", "not_running", "unknown"]
    stop_state: Literal["stopped", "running", "unknown"]
    observed_at: datetime
    reason: str | None = None


class SoftwareUse(StrictModel):
    call_id: UUID
    run_id: UUID
    node_execution_id: str
    state: Literal["running", "unknown"]


class AutostretchParameters(StrictModel):
    linked: bool = Field(default=False, strict=True)
    shadowsclip: float = Field(default=-2.8, strict=True)
    targetbg: float = Field(default=0.25, ge=0, le=1, strict=True)

    @field_validator("shadowsclip", "targetbg")
    @classmethod
    def finite_parameter(cls, value: float):
        if not isfinite(value):
            raise ValueError("Siril 参数必须为有限数值。")
        return value


class NativeSirilCall(AutostretchParameters):
    call_id: UuidInput
    prompt_id: UuidInput
    node_id: str
    reference: InputReference | OutputLocator


class SirilPreviewRequest(AutostretchParameters):
    reference: InputReference
    member_index: int = Field(default=0, ge=0)
    consumer_id: UuidInput
    generation: int = Field(ge=0)


class NativeBundleCall(StrictModel):
    call_id: UuidInput
    prompt_id: UuidInput
    node_id: str
    definition_id: UuidInput
    definition_token: str
    reference: InputReference | OutputLocator
    parameters: dict[str, JsonValue]


class BundlePreviewRequest(StrictModel):
    reference: InputReference
    member_index: int = Field(default=0, ge=0)
    consumer_id: UuidInput
    generation: int = Field(ge=0)
    package_id: str
    operation_id: str
    parameters: dict[str, JsonValue]


class ConfirmSoftwareEvent(StrictModel):
    operation_id: UuidInput


class SirilCommandAssessment(StrictModel):
    parameter_details: str
    structured_parameter_defaults_ranges: str
    single_image_sequence_context: str
    input_output_semantics: str
    headless_status: str
    dependencies: str
    security_risk: str
    semantic_review_status: str
    node_definition_status: str
    node_definition_reason: str
    node_generation_status: str
    node_generation_reason: str
    registry_load_status: str
    registry_load_reason: str
    runtime_test_status: str
    runtime_test_reason: str


class SirilCommand(StrictModel):
    command: str
    scriptable: bool
    syntax: str
    description: str
    url: str
    assessment: SirilCommandAssessment
