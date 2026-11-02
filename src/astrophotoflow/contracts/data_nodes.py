from typing import Literal

from pydantic import Field, field_validator, model_validator

from astrophotoflow.contracts.assets import OutputRegistration
from astrophotoflow.contracts.common import StrictModel, UuidInput, check_name
from astrophotoflow.contracts.inputs import InputReference, OutputLocator
from astrophotoflow.contracts.media import MediaSelection
from astrophotoflow.contracts.previews import AutoStretch

ScienceReference = InputReference | OutputLocator


class NativeDataExecute(StrictModel):
    run_id: UuidInput
    execution_id: UuidInput
    node_id: str = Field(min_length=1)
    workflow_id: UuidInput | None = None
    reference: ScienceReference | None = None
    image_count: int = Field(default=0, ge=0)
    input_dtype: Literal['float16', 'float32', 'float64'] | None = None
    input_bindings: dict[str, list[str | int]] = Field(default_factory=dict)

    @model_validator(mode='after')
    def one_source(self):
        if (self.reference is not None) == (self.image_count > 0):
            raise ValueError('Exactly one science reference or nonempty IMAGE batch is required.')
        if bool(self.image_count) != (self.input_dtype is not None):
            raise ValueError('IMAGE batch requires its input dtype.')
        return self


class DataNodeIdentity(StrictModel):
    run_id: UuidInput
    execution_id: UuidInput


class ExportSettings(StrictModel):
    format: Literal['original', 'fits', 'xisf', 'tiff', 'png', 'jpeg'] = 'original'
    precision: Literal['original', 'uint8', 'uint16', 'uint32', 'int16', 'int32', 'float32', 'float64'] = 'original'
    conversion: Literal['preserve', 'round', 'normalize', 'display'] = 'preserve'
    value_range: tuple[float, float] | None = None
    display_range: tuple[float, float] | None = None
    auto_stretch: AutoStretch | None = None
    jpeg_quality: int = Field(default=95, ge=1, le=100)

    @field_validator('value_range', 'display_range', mode='before')
    @classmethod
    def wire_ranges(cls, value):
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode='after')
    def supported(self):
        import math
        allowed = {
            'fits': {'uint8','uint16','uint32','int16','int32','float32','float64'},
            'xisf': {'uint8','uint16','uint32','float32','float64'},
            'tiff': {'uint8','uint16','uint32','int16','int32','float32','float64'},
            'png': {'uint8','uint16'}, 'jpeg': {'uint8'},
        }
        if self.format == 'original':
            if self.precision != 'original' or self.conversion != 'preserve':
                raise ValueError('Original copy does not convert precision or values.')
        elif self.precision not in allowed[self.format]:
            raise ValueError('Choose an explicitly supported format/precision combination.')
        for bounds in (self.value_range, self.display_range):
            if bounds is not None and (not all(math.isfinite(value) for value in bounds) or not bounds[0] < bounds[1]):
                raise ValueError('Ranges must be finite and increasing.')
        if self.conversion == 'normalize' and self.value_range is None:
            raise ValueError('Normalization requires an explicit value_range.')
        if self.conversion == 'display' and (self.display_range is None) == (self.auto_stretch is None):
            raise ValueError('Display export requires one frozen display_range or auto_stretch recipe.')
        if self.conversion == 'round' and self.precision.startswith('float'):
            raise ValueError('Rounding is an explicit integer conversion; choose preserve for floating output.')
        if self.auto_stretch is not None:
            recipe = self.auto_stretch
            values = [recipe.input_offset, recipe.shadows, recipe.highlights, recipe.midtones, *recipe.white_balance]
            if not all(math.isfinite(value) for value in values) or not recipe.highlights > recipe.shadows or not 0 < recipe.midtones < 1 or any(value <= 0 for value in recipe.white_balance):
                raise ValueError('Invalid finite display stretch recipe.')
        return self


class ExportRequest(StrictModel):
    request_id: UuidInput
    source: DataNodeIdentity
    member_indexes: list[int] = Field(min_length=1)
    target: Literal['library', 'local']
    destination: str | None = None
    name: str | None = None
    settings: ExportSettings = Field(default_factory=ExportSettings)
    selections: dict[str, MediaSelection] = Field(default_factory=dict)

    @field_validator('name')
    @classmethod
    def valid_name(cls, value):
        if value is not None:
            check_name(value)
            if '/' in value or '\\' in value:
                raise ValueError('Names cannot contain directory components.')
        return value

    @model_validator(mode='after')
    def selected(self):
        if self.member_indexes != sorted(set(self.member_indexes)) or self.member_indexes[0] < 0:
            raise ValueError('Select unique members in their original order.')
        if (self.target == 'local') != (self.destination is not None):
            raise ValueError('Only a local export requires a destination.')
        return self


class ExportSelection(StrictModel):
    mode: Literal['file', 'folder']
    suggested_name: str = Field(default='image.fits', min_length=1)


class DataNodeMember(StrictModel):
    name: str
    view_base: str
    selection: dict
    format: str
    metadata: dict | None
    byte_size: int


class DataNodeResult(StrictModel):
    run_id: UuidInput
    execution_id: UuidInput
    node_id: str
    workflow_id: UuidInput | None
    state: Literal['preparing', 'completed', 'failed']
    error: str | None
    reference: ScienceReference | None
    output: OutputLocator | None
    input_bindings: dict[str, list[str | int]]
    members: list[DataNodeMember]


class ExportMemberResult(StrictModel):
    member_index: int
    state: Literal['running', 'completed', 'failed', 'cancelled']
    path: str | None = None
    byte_size: int | None = None
    content_hash: str | None = None
    registration_task_id: UuidInput | None = None
    registration: OutputRegistration | None = None
    error: dict | None = None
    verification: dict | None = None
    settings: ExportSettings | None = None
    selection: MediaSelection | None = None


class ExportReceipt(StrictModel):
    request_id: UuidInput
    state: Literal['queued', 'running', 'cancelling', 'completed', 'completed_with_errors', 'cancelled', 'failed', 'interrupted']
    source: DataNodeIdentity
    target: Literal['library', 'local']
    member_indexes: list[int]
    destination: str | None
    settings: ExportSettings
    results: list[ExportMemberResult]
    error: str | None
