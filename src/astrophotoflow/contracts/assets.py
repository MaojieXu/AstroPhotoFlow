from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from astrophotoflow.contracts.common import CfaPattern, ErrorDetail, JsonObject, PageMetadata, StrictModel, UuidInput, check_name
from astrophotoflow.contracts.equipment import EquipmentSnapshots
from astrophotoflow.contracts.metadata import AssetClassification, AssetParametersPatch, FrameClass, FrameType, ParameterMode
from astrophotoflow.contracts.snapshots import VersionCaptureSnapshot


class AssetVersionOut(StrictModel):
    id: UUID
    asset_id: UUID
    view_base: str
    version_number: int
    storage_mode: Literal["reference", "managed"]
    storage_location: str
    byte_size: int | None
    content_hash: str | None
    availability: Literal["unknown", "available", "changed", "missing"]
    camera_id: UuidInput | None
    optical_system_id: UuidInput | None
    filter_id: UuidInput | None
    frame_type: Literal["light", "bias", "dark", "flat", "dark_flat"] | None
    calibration_level: Literal["individual", "master"] | None
    capture_snapshot: VersionCaptureSnapshot | None
    scientific_metadata: JsonObject | None
    created_at: datetime


class AssetOut(StrictModel):
    id: UUID
    name: str
    scope: Literal["shared", "project"]
    owner_project_id: UUID | None
    role: Literal["raw", "calibration", "intermediate", "final"]
    calibration_level: Literal["individual", "master"] | None
    current_version_id: UUID | None
    classification: AssetClassification
    parameters: AssetParametersPatch
    equipment_snapshot: EquipmentSnapshots
    value_sources: dict[str, Literal["manual", "file", "preset", "unknown"]]
    notes: str | None
    status: Literal["active", "archived"]
    revision: int
    created_at: datetime
    current_version: AssetVersionOut | None


class AssetPage(PageMetadata):
    items: list[AssetOut]




class AssetVersionPage(PageMetadata):
    items: list[AssetVersionOut]


class PreviewReference(StrictModel):
    asset_version_id: UUID
    hdu_index: int | None = Field(ge=0)


class AssetContentObservation(StrictModel):
    asset_id: UUID
    base_version_id: UUID
    base_revision: int = Field(ge=1)
    storage_mode: Literal["reference", "managed"]
    stored_hash: str
    state: Literal["unchanged", "changed", "missing", "unsupported"]
    observed_hash: str | None
    observed_byte_size: int | None = Field(default=None, ge=0)
    observed_mtime_ns: str | None = Field(default=None, pattern=r"^(0|[1-9][0-9]*)$",
                                        description="Exact decimal nanoseconds; encoded as text to avoid JavaScript integer rounding.")
    error: ErrorDetail | None


class AssetContentAccept(StrictModel):
    base_version_id: UuidInput
    base_revision: int = Field(ge=1)
    expected_observed_hash: str = Field(pattern=r"^blake3:[0-9a-f]{64}$")


class OutputRegistration(StrictModel):
    task_id: UUID
    created: bool
    task_status: Literal["queued", "running", "cancelling", "completed", "completed_with_errors", "failed", "cancelled", "interrupted"]
    asset_id: UUID | None
    asset_version_id: UUID | None
    content_status: Literal["pending", "available", "failed"]
    metadata_status: Literal["pending", "available", "unsupported", "failed"]
    preview_status: Literal["pending", "available", "unsupported", "failed"]
    error: ErrorDetail | None


class FilterEquipmentOption(StrictModel):
    id: UUID
    name: str


class NumericRangeOut(StrictModel):
    min: float
    max: float


class LibraryFilterOptions(StrictModel):
    frame_classes: list[str]
    frame_types: list[str]
    roles: list[str]
    parameter_modes: list[str]
    bin_values: list[str]
    equipment: dict[str, list[FilterEquipmentOption]]
    numeric_ranges: dict[str, NumericRangeOut]


class FitsHduOut(StrictModel):
    id: UUID
    asset_version_id: UUID
    hdu_index: int
    name: str | None
    hdu_type: str
    shape: list[int] | None
    bitpix: int | None
    pixel_type: str | None
    bscale: float | None
    bzero: float | None
    bunit: str | None
    parser_version: str
    supported_kind: Literal["mono", "bayer", "rgb", "xtrans", "quad_bayer"] | None
    is_selected: bool
    parse_error: str | None


class FitsHduPage(PageMetadata):
    items: list[FitsHduOut]


class FitsHeaderOut(StrictModel):
    asset_version_id: UUID
    hdu_index: int
    cards: list[dict[str, Any]]


















class AssetPatch(StrictModel):
    base_revision: int = Field(ge=1)
    name: str | None = None
    notes: str | None = None
    classification: AssetClassification | None = None
    parameters: AssetParametersPatch | None = None
    status: Literal["active", "archived"] | None = None

    @field_validator("name")
    @classmethod
    def valid_name(cls, value):
        return None if value is None else check_name(value)

    @model_validator(mode="after")
    def reject_null_objects(self):
        for field in ("classification", "parameters"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} 不能为 null，请传对象")
        return self


class LibraryMemberFilters(StrictModel):
    role: list[Literal["raw", "calibration", "intermediate", "final"]] = Field(default_factory=list)
    frame_class: list[FrameClass] = Field(default_factory=list)
    frame_type: list[FrameType] = Field(default_factory=list)
    camera_id: list[UuidInput] = Field(default_factory=list)
    optical_system_id: list[UuidInput] = Field(default_factory=list)
    filter_id: list[UuidInput] = Field(default_factory=list)
    parameter_mode: list[ParameterMode] = Field(default_factory=list)
    binning: list[str] = Field(default_factory=list)
    exposure_min: float | None = Field(default=None, strict=False, allow_inf_nan=False)
    exposure_max: float | None = Field(default=None, strict=False, allow_inf_nan=False)
    integration_min: float | None = Field(default=None, strict=False, allow_inf_nan=False)
    integration_max: float | None = Field(default=None, strict=False, allow_inf_nan=False)
    temperature_min: float | None = Field(default=None, strict=False, allow_inf_nan=False)
    temperature_max: float | None = Field(default=None, strict=False, allow_inf_nan=False)
    iso_min: float | None = Field(default=None, strict=False, allow_inf_nan=False)
    iso_max: float | None = Field(default=None, strict=False, allow_inf_nan=False)
    gain_min: float | None = Field(default=None, strict=False, allow_inf_nan=False)
    gain_max: float | None = Field(default=None, strict=False, allow_inf_nan=False)
    offset_min: float | None = Field(default=None, strict=False, allow_inf_nan=False)
    offset_max: float | None = Field(default=None, strict=False, allow_inf_nan=False)

    @field_validator("binning")
    @classmethod
    def canonical_binning(cls, values: list[str]) -> list[str]:
        result = []
        for value in values:
            dimensions = value.lower().replace("×", "x").split("x")
            if len(dimensions) == 1:
                dimensions *= 2
            if len(dimensions) != 2 or not all(item.strip().isdigit() and int(item) > 0 for item in dimensions):
                raise ValueError("Binning must contain two positive dimensions, for example 2x2")
            result.append(f"{int(dimensions[0])}x{int(dimensions[1])}")
        return result


LibrarySortKey = Literal[
    "created_at", "name", "classification", "camera", "parameter_mode", "exposure_seconds",
    "sensor_temperature_c", "binning", "cfa_pattern", "optical_system", "filter", "integration_seconds",
    "storage_mode", "status", "notes",
]


class LibraryQuery(LibraryMemberFilters):
    limit: int = Field(default=50, ge=1, le=200, strict=False)
    offset: int = Field(default=0, ge=0, strict=False)
    q: str | None = None
    sort_by: LibrarySortKey = "created_at"
    order: Literal["asc", "desc"] = "desc"


class AssetQuery(StrictModel):
    limit: int = Field(default=50, ge=1, le=200, strict=False)
    offset: int = Field(default=0, ge=0, strict=False)
    q: str | None = None
    sort_by: Literal["created_at", "name"] = "created_at"
    order: Literal["asc", "desc"] = "desc"
    status: Literal["active", "archived", "all"] = "active"
    role: Literal["raw", "calibration", "intermediate", "final"] | None = None
    frame_type: FrameType | None = None
    calibration_level: Literal["individual", "master"] | None = None
    camera_id: UuidInput | None = None
    optical_system_id: UuidInput | None = None
    filter_id: UuidInput | None = None


class LibraryValueSummary[SummaryValue](StrictModel):
    state: Literal["consistent", "mixed", "unknown"]
    value: SummaryValue | None


class LibraryEquipmentLabel(StrictModel):
    id: UUID | None
    name: str


class LibraryParameterSummary(StrictModel):
    parameter_mode: LibraryValueSummary[ParameterMode]
    iso: LibraryValueSummary[int]
    gain: LibraryValueSummary[float]
    offset: LibraryValueSummary[float]
    exposure_seconds: LibraryValueSummary[float]
    integration_seconds: LibraryValueSummary[float]
    sensor_temperature_c: LibraryValueSummary[float]
    binning_x: LibraryValueSummary[int]
    binning_y: LibraryValueSummary[int]
    cfa_pattern: LibraryValueSummary[CfaPattern]


class LibraryClassificationSummary(StrictModel):
    frame_class: LibraryValueSummary[FrameClass]
    frame_type: LibraryValueSummary[FrameType]


class LibraryMetadataSummary(StrictModel):
    classification: LibraryClassificationSummary
    parameters: LibraryParameterSummary
    camera: LibraryValueSummary[LibraryEquipmentLabel]
    optical_system: LibraryValueSummary[LibraryEquipmentLabel]
    filter: LibraryValueSummary[LibraryEquipmentLabel]
    storage_mode: LibraryValueSummary[Literal["managed", "reference"]]
    availability: LibraryValueSummary[Literal["unknown", "available", "changed", "missing"]]


class LibraryThumbnailReference(StrictModel):
    asset_id: UUID
    asset_version_id: UUID
    view_base: str
    hdu_index: int = Field(ge=0)


class LibraryItemSummary(StrictModel):
    entry_type: Literal["asset", "dataset"]
    id: UUID
    name: str
    notes: str | None
    status: Literal["active", "archived"]
    revision: int
    created_at: datetime
    version_id: UUID | None
    version_number: int | None
    member_count: int = Field(ge=0)
    matching_member_count: int = Field(ge=0)
    input_ready: bool
    summary: LibraryMetadataSummary
    thumbnail: LibraryThumbnailReference | None
    import_issue: str | None


class LibraryAssetSummary(LibraryItemSummary):
    entry_type: Literal["asset"]
    view_base: str | None
    member_count: Literal[1]
    matching_member_count: Literal[1]


class LibraryDatasetSummary(LibraryItemSummary):
    entry_type: Literal["dataset"]


LibraryItem = Annotated[LibraryAssetSummary | LibraryDatasetSummary, Field(discriminator="entry_type")]


class LibraryItemPage(PageMetadata):
    items: list[LibraryItem]
