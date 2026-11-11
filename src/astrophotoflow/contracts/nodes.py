import hashlib
import json
from typing import Annotated, Literal
from uuid import UUID
from pydantic import Field, JsonValue, field_validator, model_validator
from astrophotoflow.contracts.bundles import BundlePreview
from astrophotoflow.contracts.common import ErrorDetail, SnapshotModel, StrictModel, UuidInput, check_name
from astrophotoflow.contracts.localization import CapabilityDisplay, Locale
from astrophotoflow.contracts.software import BundleDevelopmentSource, ParameterDefinition, SoftwareOperation

class NodePort(StrictModel):
    name: str
    type: str
    _name = field_validator('name')(check_name)
    _type = field_validator('type')(check_name)

class NodeParameterBinding(StrictModel):
    kind: Literal['parameter']
    name: str
    _name = field_validator('name')(check_name)

class FixedParameterBinding(StrictModel):
    kind: Literal['fixed']
    value: JsonValue
ParameterBinding = Annotated[NodeParameterBinding | FixedParameterBinding, Field(discriminator='kind')]

class SoftwareBinding(StrictModel):
    package_id: str
    operation_id: str
    inputs: dict[str, str]
    parameters: dict[str, ParameterBinding]
    outputs: dict[str, str]

class NodeDisplayLabel(SnapshotModel):
    label: str = Field(default_factory=str)
    description: str = Field(default_factory=str)
    _label = field_validator('label')(check_name)

class NodeLocalization(SnapshotModel):
    name: str = Field(default_factory=str)
    description: str = Field(default_factory=str)
    help: str = Field(default_factory=str)
    category: list[str] = Field(default_factory=list)
    inputs: dict[str, NodeDisplayLabel] = Field(default_factory=dict)
    outputs: dict[str, NodeDisplayLabel] = Field(default_factory=dict)
    parameters: dict[str, NodeDisplayLabel] = Field(default_factory=dict)
    _name = field_validator('name')(check_name)

class NodeDefinition(StrictModel):
    definition_id: UuidInput
    source: Literal['custom', 'package']
    name: str
    description: str
    category: list[str] = Field(default_factory=list)
    inputs: list[NodePort]
    outputs: list[NodePort]
    parameters: list[ParameterDefinition]
    execution: SoftwareBinding
    localizations: dict[Locale, NodeLocalization] = Field(default_factory=dict)
    _name = field_validator('name')(check_name)

    @field_validator('category')
    @classmethod
    def valid_category(cls, value):
        if any((not part.strip() or part != part.strip() or '/' in part for part in value)):
            raise ValueError('Category levels must be non-empty names without slashes.')
        return value

    @model_validator(mode='after')
    def valid_names(self):
        input_names = [port.name for port in self.inputs]
        output_names = [port.name for port in self.outputs]
        parameter_names = [parameter.name for parameter in self.parameters]
        if len(set(input_names)) != len(input_names):
            raise ValueError('节点输入名称必须唯一。')
        if len(set(output_names)) != len(output_names):
            raise ValueError('节点输出名称必须唯一。')
        if len(set(parameter_names)) != len(parameter_names):
            raise ValueError('节点参数名称必须唯一。')
        if set(input_names) & set(parameter_names) or 'apf_execution_token' in set(input_names) | set(parameter_names):
            raise ValueError('节点参数不能与数据输入或内部执行键重名。')
        for display in self.localizations.values():
            if 'category' in display.model_fields_set:
                if len(display.category) != len(self.category) or any(not part.strip() for part in display.category):
                    raise ValueError('Localized category levels must match the node category.')
            for section in ('inputs', 'outputs', 'parameters'):
                names = {item.name for item in getattr(self, section)}
                if not set(getattr(display, section)) <= names:
                    raise ValueError('Localized labels must match node ' + section + '.')
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
    action: Literal['create', 'update', 'remove']
    applied: bool
    content: SavedDefinition | None
    error: ErrorDetail | None

class NativeNodeLoad(StrictModel):
    definition_id: UUID
    content_token: str | None
    state: Literal['loaded', 'not_loaded', 'failed', 'unknown']
    reason: str | None

class NodeCapability(StrictModel):
    automatic_result_preview: bool = False
    implementation_token: str | None = None
    development_source: BundleDevelopmentSource | None = None
    node: SavedDefinition
    operation: SoftwareOperation | None
    available: bool
    reason: str | None
    preview: BundlePreview | None
    help: str
    examples: list[dict[str, JsonValue]]
    display: dict[Locale, CapabilityDisplay] = Field(default_factory=dict)

def definition_content_token(definition: NodeDefinition) -> str:
    content = definition.model_dump(mode='json')
    if not definition.category:
        content.pop('category')
    if not definition.localizations:
        content.pop('localizations')
    for parameter in content['parameters']:
        parameter.pop('unit')
        if parameter['editor'] is None:
            parameter.pop('editor')
    encoded = json.dumps(content, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()

class NodeCapabilitySummary(StrictModel):
    definition_id: UuidInput
    name: str
    description: str
    available: bool
    reason: str | None
    content_token: str

class NodeSearchPage(StrictModel):
    items: list[NodeCapabilitySummary]
    total: int
    limit: int
    offset: int

class NodeCapabilities(StrictModel):
    items: list[NodeCapability]
