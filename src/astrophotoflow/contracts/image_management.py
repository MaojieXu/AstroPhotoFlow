"""Typed image management facts and explicit metadata/equipment changes."""
import re
from datetime import UTC, datetime
from typing import Annotated, Literal
from pydantic import MISSING, AfterValidator, ConfigDict, Field, field_validator, model_validator
from astrophotoflow.contracts.assets import AssetOut
from astrophotoflow.contracts.calibration import CalibrationTarget
from astrophotoflow.contracts.common import JsonObject, PageMetadata, StrictModel, UuidInput, check_name
from astrophotoflow.contracts.datasets import DatasetMemberOut, DatasetOut
from astrophotoflow.contracts.metadata import AssetClassification, CaptureParametersPatch, FrameClass, FrameType, ParameterMode
from astrophotoflow.contracts.snapshots import ImportDefaultsSnapshot
ImageName = Annotated[str, AfterValidator(check_name)]
Revision = Annotated[int, Field(ge=1)]
PageLimit = Annotated[int, Field(ge=1, le=200, strict=False)]
PageOffset = Annotated[int, Field(ge=0, strict=False)]

class ScientificTime(StrictModel):
    raw_value: str | None = None
    time_system: str | None = None
    utc: datetime | None = Field(default=None, strict=False)

    @field_validator('utc', mode='before')
    @classmethod
    def rfc3339_input(cls, value):
        if value is None or isinstance(value, datetime):
            return value
        if not isinstance(value, str) or re.fullmatch('\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z|[+-]\\d{2}:\\d{2})', value) is None:
            raise ValueError('utc must be an aware RFC3339 timestamp.')
        return value

    @field_validator('utc')
    @classmethod
    def aware_utc(cls, value):
        if value is not None:
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError('UTC time must include an explicit timezone.')
            if value.utcoffset().total_seconds() != 0:
                raise ValueError('UTC time must have a zero UTC offset.')
            return value.astimezone(UTC)
        return value

    @model_validator(mode='after')
    def has_value(self):
        if self.utc is None and (self.raw_value is None or not self.raw_value.strip()):
            raise ValueError('Scientific time requires raw_value or utc.')
        return self

class ImageTimes(StrictModel):
    capture_start: ScientificTime | None | MISSING = MISSING
    capture_end: ScientificTime | None | MISSING = MISSING
    master_created_at: ScientificTime | None | MISSING = MISSING

    @model_validator(mode='after')
    def ordered_times(self):
        start, end = (self.capture_start, self.capture_end)
        if isinstance(start, ScientificTime) and isinstance(end, ScientificTime) and (start.utc is not None) and (end.utc is not None) and (end.utc < start.utc):
            raise ValueError('capture_end cannot precede capture_start.')
        return self

class ImageCaptureParameters(CaptureParametersPatch):
    """Capture facts only: device identity is applied through EquipmentApplication."""

class ImageMetadata(StrictModel):
    target_name: str | None | MISSING = MISSING
    classification: AssetClassification | MISSING = MISSING
    parameters: ImageCaptureParameters | MISSING = MISSING
    times: ImageTimes | MISSING = MISSING

from astrophotoflow.contracts.calibration_status import CalibrationStatus

class ImageChanges(ImageMetadata):
    calibration_status: CalibrationStatus | MISSING = MISSING
    calibration_reason: str | MISSING = Field(default=MISSING, min_length=1)
    name: ImageName | MISSING = MISSING
    notes: str | None | MISSING = MISSING
    status: Literal['active', 'archived'] | MISSING = MISSING

class AssetRevisionRef(StrictModel):
    asset_id: UuidInput
    expected_revision: Revision

class AssetMetadataChange(AssetRevisionRef):
    changes: ImageChanges

class DeviceRevisionRef(StrictModel):
    equipment_id: UuidInput
    expected_revision: Revision

class FilterInherit(StrictModel):
    mode: Literal['inherit']

class FilterNone(StrictModel):
    mode: Literal['none']

class FilterMember(StrictModel):
    mode: Literal['member']
    member_id: UuidInput
ImageFilterChoice = Annotated[FilterInherit | FilterNone | FilterMember, Field(discriminator='mode')]

class DeviceEquipmentChoice(StrictModel):
    source: Literal['devices']
    camera: DeviceRevisionRef | None | MISSING = MISSING
    telescope: DeviceRevisionRef | None | MISSING = MISSING
    filter: DeviceRevisionRef | None | MISSING = MISSING
    mount: DeviceRevisionRef | None | MISSING = MISSING
    optical_accessory_id: UuidInput | None | MISSING = MISSING

class SetupEquipmentChoice(StrictModel):
    source: Literal['setup']
    setup_id: UuidInput
    expected_revision: Revision
    filter: ImageFilterChoice | MISSING = MISSING
EquipmentChoice = Annotated[DeviceEquipmentChoice | SetupEquipmentChoice, Field(discriminator='source')]

class EquipmentApplication(StrictModel):
    choice: EquipmentChoice
    fields: list[Literal['camera', 'telescope', 'filter', 'mount', 'optical_accessory']] = Field(min_length=1)

    @field_validator('fields')
    @classmethod
    def unique_fields(cls, value):
        if len(value) != len(set(value)):
            raise ValueError('Equipment fields must be unique.')
        return value

class ImageSearch(StrictModel):
    calibration_status: CalibrationStatus | None = None
    model_config = ConfigDict(extra='forbid', strict=False)
    text: str | None = None
    status: Literal['active', 'archived', 'all'] = 'active'
    target_name: str | None = None
    frame_class: FrameClass | None = None
    frame_type: FrameType | None = None
    camera_id: UuidInput | None = None
    telescope_id: UuidInput | None = None
    filter_id: UuidInput | None = None
    parameter_mode: ParameterMode | None = None
    binning_x: int | None = Field(default=None, gt=0)
    binning_y: int | None = Field(default=None, gt=0)
    exposure_min: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    exposure_max: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    temperature_min: float | None = Field(default=None, allow_inf_nan=False)
    temperature_max: float | None = Field(default=None, allow_inf_nan=False)
    gain_min: float | None = Field(default=None, allow_inf_nan=False)
    gain_max: float | None = Field(default=None, allow_inf_nan=False)
    offset_min: float | None = Field(default=None, allow_inf_nan=False)
    offset_max: float | None = Field(default=None, allow_inf_nan=False)
    iso_min: int | None = Field(default=None, gt=0)
    iso_max: int | None = Field(default=None, gt=0)
    captured_from: datetime | None = None
    captured_to: datetime | None = None
    master_created_from: datetime | None = None
    master_created_to: datetime | None = None
    sort_by: Literal['name', 'created_at', 'capture_start', 'master_created_at'] = 'created_at'
    order: Literal['asc', 'desc'] = 'desc'
    limit: PageLimit = 50
    offset: PageOffset = 0

    @field_validator('captured_from', 'captured_to', 'master_created_from', 'master_created_to')
    @classmethod
    def aware_range(cls, value):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError('Time range requires an explicit timezone.')
        return value

    @model_validator(mode='after')
    def valid_ranges(self):
        for lower, upper in (('exposure_min', 'exposure_max'), ('temperature_min', 'temperature_max'), ('gain_min', 'gain_max'), ('offset_min', 'offset_max'), ('iso_min', 'iso_max'), ('captured_from', 'captured_to'), ('master_created_from', 'master_created_to')):
            low, high = (getattr(self, lower), getattr(self, upper))
            if low is not None and high is not None and (low > high):
                raise ValueError(f'{upper} cannot be less than {lower}.')
        return self

class DatasetSearch(ImageSearch):
    match: Literal['any', 'all'] = 'any'

class DatasetMemberSearch(ImageSearch):
    status: Literal['active', 'archived', 'all'] = 'all'
    sort_by: Literal['position', 'name', 'created_at', 'capture_start', 'master_created_at'] = 'position'
    order: Literal['asc', 'desc'] = 'asc'

class DatasetChanges(StrictModel):
    name: ImageName | MISSING = MISSING
    notes: str | None | MISSING = MISSING
    status: Literal['active', 'archived'] | MISSING = MISSING

class FixedAssetSource(StrictModel):
    kind: Literal['asset']
    asset_id: UuidInput

class FixedDatasetSource(StrictModel):
    kind: Literal['dataset']
    dataset_id: UuidInput
    member_asset_ids: list[UuidInput] | None = Field(default=None, min_length=1)

    @field_validator('member_asset_ids')
    @classmethod
    def unique_members(cls, value):
        if value is not None and len(value) != len(set(value)):
            raise ValueError('Selected member asset IDs must be unique.')
        return value
FixedSource = Annotated[FixedAssetSource | FixedDatasetSource, Field(discriminator='kind')]

class ProcessingProvenance(StrictModel):
    software_name: str | None = None
    software_version: str | None = None
    operation: str | None = None
    parameters: JsonObject | None = None

class MasterProvenanceChanges(StrictModel):
    sources: list[FixedSource] | None | MISSING = Field(default=MISSING, min_length=1)
    made_at: ScientificTime | None | MISSING = MISSING
    processing: ProcessingProvenance | None | MISSING = MISSING
    applied_calibrations: dict[Literal['bias', 'dark', 'flat', 'dark_flat'], CalibrationTarget] | None | MISSING = MISSING
    bias_state: Literal['included', 'removed', 'unknown'] | MISSING = MISSING
    normalized: bool | None | MISSING = MISSING
    debayered: bool | None | MISSING = MISSING
    notes: str | None | MISSING = MISSING

class ImageMetadataBatch(StrictModel):
    items: list[AssetMetadataChange] = Field(min_length=1)

    @field_validator('items')
    @classmethod
    def unique_assets(cls, value):
        ids = [item.asset_id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError('Assets must be unique.')
        return value

class ImageEquipmentApply(StrictModel):
    assets: list[AssetRevisionRef] = Field(min_length=1)
    equipment: EquipmentApplication

    @model_validator(mode='after')
    def explicit_selection(self):
        ids = [item.asset_id for item in self.assets]
        if len(ids) != len(set(ids)):
            raise ValueError('Assets must be unique.')
        return self

class ImageUpdate(StrictModel):
    expected_revision: Revision
    changes: ImageChanges

class MasterProvenanceUpdate(StrictModel):
    expected_revision: Revision
    changes: MasterProvenanceChanges

class ImageDetail(StrictModel):
    asset: AssetOut
    metadata: ImageMetadata
    equipment_context: ImportDefaultsSnapshot | None = None

class ImagePage(PageMetadata):
    items: list[ImageDetail]

class ImageBatchResult(StrictModel):
    items: list[ImageDetail]

class ImageHeaderPage(PageMetadata):
    asset_id: UuidInput
    hdu_index: int = Field(ge=0)
    cards: list[JsonObject]

class MasterSourceTimeRange(StrictModel):
    start: ScientificTime | None
    end: ScientificTime | None
    complete: bool

class MasterProvenanceOut(StrictModel):
    asset_id: UuidInput
    asset_revision: Revision
    revision: int = Field(ge=0)
    source_kind: Literal['user_declared']
    declaration: MasterProvenanceChanges
    platform_provenance: JsonObject | None
    source_time_range: MasterSourceTimeRange

class DatasetImageSummary(StrictModel):
    dataset: DatasetOut
    member_count: int = Field(ge=0)
    matching_member_count: int = Field(ge=0)

class DatasetImagePage(PageMetadata):
    items: list[DatasetImageSummary]

class DatasetImageDetail(StrictModel):
    dataset: DatasetOut

class DatasetImageMember(StrictModel):
    member: DatasetMemberOut
    metadata: ImageMetadata

class DatasetImageMemberPage(PageMetadata):
    items: list[DatasetImageMember]

class ImageDatasetUpdate(StrictModel):
    expected_revision: Revision
    changes: DatasetChanges
