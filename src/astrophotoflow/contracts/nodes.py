from typing import Annotated, Literal
import hashlib
import json
from uuid import UUID

from pydantic import Field, JsonValue, field_validator, model_validator

from astrophotoflow.contracts.common import ErrorDetail, StrictModel, UuidInput, check_name
from astrophotoflow.contracts.software import ParameterDefinition, SoftwareOperation
from astrophotoflow.contracts.bundles import BundlePreview
from astrophotoflow.contracts.localization import CapabilityDisplay, Locale


class NodePort(StrictModel):
    name: str
    type: str

    _name = field_validator("name")(check_name)
    _type = field_validator("type")(check_name)


class NodeParameterBinding(StrictModel):
    kind: Literal["parameter"]
    name: str

    _name = field_validator("name")(check_name)


class FixedParameterBinding(StrictModel):
    kind: Literal["fixed"]
    value: JsonValue


ParameterBinding = Annotated[NodeParameterBinding | FixedParameterBinding, Field(discriminator="kind")]


class SoftwareBinding(StrictModel):
    package_id: str
    operation_id: str
    inputs: dict[str, str]
    parameters: dict[str, ParameterBinding]
    outputs: dict[str, str]


class NodeDefinition(StrictModel):
    definition_id: UuidInput
    source: Literal["custom", "package"]
    name: str
    description: str
    inputs: list[NodePort]
    outputs: list[NodePort]
    parameters: list[ParameterDefinition]
    execution: SoftwareBinding

    _name = field_validator("name")(check_name)

    @model_validator(mode="after")
    def valid_names(self):
        input_names = [port.name for port in self.inputs]
        output_names = [port.name for port in self.outputs]
        parameter_names = [parameter.name for parameter in self.parameters]
        if len(set(input_names)) != len(input_names):
            raise ValueError("节点输入名称必须唯一。")
        if len(set(output_names)) != len(output_names):
            raise ValueError("节点输出名称必须唯一。")
        if len(set(parameter_names)) != len(parameter_names):
            raise ValueError("节点参数名称必须唯一。")
        if set(input_names) & set(parameter_names) or "apf_execution_token" in set(input_names) | set(parameter_names):
            raise ValueError("节点参数不能与数据输入或内部执行键重名。")
        return self


class SavedDefinition(StrictModel):
    definition: NodeDefinition
    content_token: str
    native_type: str


class PortRemap(StrictModel):
    name: str
    type: str
    before_index: int = Field(ge=0)
    after_index: int = Field(ge=0)


class DefinitionChange(StrictModel):
    before: SavedDefinition
    after: SavedDefinition
    input_remap: list[PortRemap]
    output_remap: list[PortRemap]
    disconnected_inputs: list[str]
    disconnected_outputs: list[str]
    parameter_defaults: dict[str, JsonValue]


class DefinitionWriteResult(StrictModel):
    definition_id: UUID
    action: Literal["create", "update", "remove"]
    applied: bool
    content: SavedDefinition | None
    error: ErrorDetail | None


class NativeNodeLoad(StrictModel):
    definition_id: UUID
    content_token: str | None
    state: Literal["loaded", "not_loaded", "failed", "unknown"]
    reason: str | None


class NodeCapability(StrictModel):
    node: SavedDefinition
    operation: SoftwareOperation | None
    available: bool
    reason: str | None
    preview: BundlePreview | None
    help: str
    examples: list[dict[str, JsonValue]]
    display: dict[Locale, CapabilityDisplay] = Field(default_factory=dict)


def definition_content_token(definition: NodeDefinition) -> str:
    content = definition.model_dump(mode="json")
    encoded = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
