"""Facts for one concrete native software call; no workflow or run aggregate."""
from typing import Literal
from pydantic import Field, JsonValue, model_validator
from astrophotoflow.contracts.common import ErrorDetail, StrictModel
from astrophotoflow.contracts.inputs import OutputLocator
from astrophotoflow.contracts.nodes import NodeDefinition
from astrophotoflow.contracts.software import BundleDevelopmentSource, NativeBundleCall, SoftwareInvocation, SoftwareObservation, SoftwareOperation, SoftwareResult

class SoftwareCallBundle(StrictModel):
    version: str | None
    commit: str | None
    development_source: BundleDevelopmentSource | None = None

class NativeResultImage(StrictModel):
    filename: str
    subfolder: str
    type: Literal['output'] = 'output'

class SoftwareCallRecord(StrictModel):
    request: NativeBundleCall
    definition: NodeDefinition
    operation: SoftwareOperation
    parameters: dict[str, JsonValue]
    bundle: SoftwareCallBundle
    output_display: Literal['direct', 'auto']
    state: Literal['starting', 'running', 'completed', 'failed', 'cancelled', 'unknown']
    invocation: SoftwareInvocation | None = None
    observation: SoftwareObservation | None = None
    result: SoftwareResult | None = None
    result_registered: bool = False
    outputs: list[OutputLocator] = Field(default_factory=list)
    images: list[NativeResultImage] = Field(default_factory=list)
    error: ErrorDetail | None = None
    preview_error: str | None = None

    @model_validator(mode='after')
    def same_call(self):
        for fact in (self.invocation, self.observation):
            if fact is not None and (fact.run_id != self.request.prompt_id or fact.call_id != self.request.call_id or fact.node_execution_id != self.request.node_id):
                raise ValueError('Software facts belong to another native call.')
        if self.result is not None and self.result.call_id != self.request.call_id:
            raise ValueError('Software result belongs to another native call.')
        for output in self.outputs:
            if output.run_id != self.request.prompt_id or output.execution_id != self.request.call_id:
                raise ValueError('Software output belongs to another native call.')
        if self.state == 'completed' and (not self.result_registered):
            raise ValueError('Completed software calls require checked result registration.')
        return self
