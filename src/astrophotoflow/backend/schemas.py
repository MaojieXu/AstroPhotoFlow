from datetime import datetime
from math import isfinite
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer


UuidInput = Annotated[UUID, Field(strict=False)]
CfaPattern = Literal["MONO", "RGGB", "BGGR", "GRBG", "GBRG", "XTRANS", "QUAD_BAYER"]
EquipmentKind = Literal["camera", "optical_system", "filter", "telescope", "mount", "accessory"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    @model_serializer(mode="wrap")
    def serialize_utc(self, handler):
        serialized = handler(self)
        if isinstance(serialized, dict):
            for field_name, field_value in self:
                value = serialized.get(field_name)
                if isinstance(field_value, datetime) and isinstance(value, str) and value.endswith("+00:00"):
                    serialized[field_name] = value[:-6] + "Z"
        return serialized


def check_name(value: str) -> str:
    if not value.strip():
        raise ValueError("名称不能为空或仅含空白。")
    return value


class CalibrationTarget(StrictModel):
    kind: Literal["asset_version", "dataset_version"]
    id: UuidInput


CalibrationBindings = dict[Literal["bias", "dark", "flat", "dark_flat"], CalibrationTarget | None]


def finite(value: float | None) -> float | None:
    if value is not None and not isfinite(value):
        raise ValueError("数值必须是有限值。")
    return value


class ProjectCreate(StrictModel):
    name: str
    target_name: str | None = None
    notes: str | None = None
    capture_profile_ids: list[UuidInput] = Field(default_factory=list)

    _name = field_validator("name")(check_name)


class ProjectPatch(StrictModel):
    base_revision: int = Field(ge=1)
    name: str | None = None
    target_name: str | None = None
    notes: str | None = None
    status: Literal["active", "archived"] | None = None
    capture_profile_ids: list[UuidInput] | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        return None if value is None else check_name(value)


class CameraSpecs(StrictModel):
    sensor_mode: Literal["mono", "color"] | None = None
    sensor_width_px: int | None = Field(default=None, gt=0)
    sensor_height_px: int | None = Field(default=None, gt=0)
    pixel_size_x_um: float | None = Field(default=None, gt=0)
    pixel_size_y_um: float | None = Field(default=None, gt=0)
    native_bit_depth: int | None = Field(default=None, gt=0)
    cfa_pattern: CfaPattern | None = None

    @field_validator("pixel_size_x_um", "pixel_size_y_um")
    @classmethod
    def validate_pixel_size(cls, value):
        return finite(value)


class OpticalSystemSpecs(StrictModel):
    aperture_mm: float | None = Field(default=None, gt=0)
    native_focal_length_mm: float | None = Field(default=None, gt=0)
    effective_focal_length_mm: float | None = Field(default=None, gt=0)
    focal_adjustment_note: str | None = None

    @field_validator("aperture_mm", "native_focal_length_mm", "effective_focal_length_mm")
    @classmethod
    def validate_optics(cls, value):
        return finite(value)


class FilterSpecs(StrictModel):
    filter_type: str | None = None
    central_wavelength_nm: float | None = Field(default=None, gt=0)
    bandwidth_nm: float | None = Field(default=None, gt=0)
    bandpass_note: str | None = None

    @field_validator("central_wavelength_nm", "bandwidth_nm")
    @classmethod
    def validate_band(cls, value):
        return finite(value)


class EquipmentCreateBase(StrictModel):
    name: str
    model: str | None = None
    serial_number: str | None = None
    notes: str | None = None

    _name = field_validator("name")(check_name)


class CameraCreate(EquipmentCreateBase):
    kind: Literal["camera"]
    specs: CameraSpecs = Field(default_factory=CameraSpecs)


class OpticalSystemCreate(EquipmentCreateBase):
    kind: Literal["optical_system"]
    specs: OpticalSystemSpecs = Field(default_factory=OpticalSystemSpecs)


class FilterCreate(EquipmentCreateBase):
    kind: Literal["filter"]
    specs: FilterSpecs = Field(default_factory=FilterSpecs)


class TelescopeCreate(EquipmentCreateBase):
    kind: Literal["telescope"]
    specs: OpticalSystemSpecs = Field(default_factory=OpticalSystemSpecs)


class MountSpecs(StrictModel):
    mount_type: str | None = None
    payload_kg: float | None = Field(default=None, gt=0)
    connection_note: str | None = None

    _finite = field_validator("payload_kg")(finite)


class AccessorySpecs(StrictModel):
    accessory_type: str | None = None
    connection_note: str | None = None


class MountCreate(EquipmentCreateBase):
    kind: Literal["mount"]
    specs: MountSpecs = Field(default_factory=MountSpecs)


class AccessoryCreate(EquipmentCreateBase):
    kind: Literal["accessory"]
    specs: AccessorySpecs = Field(default_factory=AccessorySpecs)


EquipmentCreate = Annotated[CameraCreate | OpticalSystemCreate | FilterCreate | TelescopeCreate | MountCreate | AccessoryCreate, Field(discriminator="kind")]


class EquipmentPatchBase(StrictModel):
    base_revision: int = Field(ge=1)
    name: str | None = None
    model: str | None = None
    serial_number: str | None = None
    notes: str | None = None
    status: Literal["active", "archived"] | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        return None if value is None else check_name(value)


class CameraSpecsPatch(StrictModel):
    sensor_mode: Literal["mono", "color"] | None = None
    sensor_width_px: int | None = Field(default=None, gt=0)
    sensor_height_px: int | None = Field(default=None, gt=0)
    pixel_size_x_um: float | None = Field(default=None, gt=0)
    pixel_size_y_um: float | None = Field(default=None, gt=0)
    native_bit_depth: int | None = Field(default=None, gt=0)
    cfa_pattern: CfaPattern | None = None

    @field_validator("pixel_size_x_um", "pixel_size_y_um")
    @classmethod
    def validate_pixel_size(cls, value):
        return finite(value)


class OpticalSystemSpecsPatch(StrictModel):
    aperture_mm: float | None = Field(default=None, gt=0)
    native_focal_length_mm: float | None = Field(default=None, gt=0)
    effective_focal_length_mm: float | None = Field(default=None, gt=0)
    focal_adjustment_note: str | None = None

    @field_validator("aperture_mm", "native_focal_length_mm", "effective_focal_length_mm")
    @classmethod
    def validate_optics(cls, value):
        return finite(value)


class FilterSpecsPatch(StrictModel):
    filter_type: str | None = None
    central_wavelength_nm: float | None = Field(default=None, gt=0)
    bandwidth_nm: float | None = Field(default=None, gt=0)
    bandpass_note: str | None = None

    @field_validator("central_wavelength_nm", "bandwidth_nm")
    @classmethod
    def validate_band(cls, value):
        return finite(value)


class CameraPatch(EquipmentPatchBase):
    kind: Literal["camera"]
    specs: CameraSpecsPatch | None = None


class OpticalSystemPatch(EquipmentPatchBase):
    kind: Literal["optical_system"]
    specs: OpticalSystemSpecsPatch | None = None


class FilterPatch(EquipmentPatchBase):
    kind: Literal["filter"]
    specs: FilterSpecsPatch | None = None


class TelescopePatch(OpticalSystemPatch):
    kind: Literal["telescope"]


class MountPatch(EquipmentPatchBase):
    kind: Literal["mount"]
    specs: MountSpecs | None = None


class AccessoryPatch(EquipmentPatchBase):
    kind: Literal["accessory"]
    specs: AccessorySpecs | None = None


EquipmentPatch = Annotated[CameraPatch | OpticalSystemPatch | FilterPatch | TelescopePatch | MountPatch | AccessoryPatch, Field(discriminator="kind")]


class CaptureProfileCreate(StrictModel):
    name: str
    camera_id: UuidInput
    optical_system_id: UuidInput | None = None
    filter_id: UuidInput | None = None
    frame_type: Literal["light", "bias", "dark", "flat", "dark_flat"]
    parameter_mode: Literal["iso", "gain"] | None = None
    iso: int | None = Field(default=None, gt=0)
    exposure_seconds: float | None = Field(default=None, ge=0)
    gain: float | None = None
    offset: float | None = None
    sensor_temperature_c: float | None = None
    binning_x: int | None = Field(default=None, gt=0)
    binning_y: int | None = Field(default=None, gt=0)
    notes: str | None = None

    _name = field_validator("name")(check_name)
    _finite = field_validator("exposure_seconds", "gain", "offset", "sensor_temperature_c")(finite)


class CaptureProfilePatch(StrictModel):
    base_revision: int = Field(ge=1)
    name: str | None = None
    camera_id: UuidInput | None = None
    optical_system_id: UuidInput | None = None
    filter_id: UuidInput | None = None
    frame_type: Literal["light", "bias", "dark", "flat", "dark_flat"] | None = None
    parameter_mode: Literal["iso", "gain"] | None = None
    iso: int | None = Field(default=None, gt=0)
    exposure_seconds: float | None = Field(default=None, ge=0)
    gain: float | None = None
    offset: float | None = None
    sensor_temperature_c: float | None = None
    binning_x: int | None = Field(default=None, gt=0)
    binning_y: int | None = Field(default=None, gt=0)
    notes: str | None = None
    status: Literal["active", "archived"] | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        return None if value is None else check_name(value)

    _finite = field_validator("exposure_seconds", "gain", "offset", "sensor_temperature_c")(finite)


class ProjectOut(StrictModel):
    id: UUID
    name: str
    target_name: str | None
    notes: str | None
    capture_profile_ids: list[UuidInput]
    status: Literal["active", "archived"]
    revision: int
    created_at: datetime
    updated_at: datetime


class EquipmentOut(StrictModel):
    id: UUID
    kind: EquipmentKind
    name: str
    model: str | None
    serial_number: str | None
    notes: str | None
    specs: dict
    status: Literal["active", "archived"]
    revision: int
    created_at: datetime
    updated_at: datetime


class CaptureProfileOut(StrictModel):
    id: UUID
    name: str
    camera_id: UuidInput
    optical_system_id: UuidInput | None
    filter_id: UuidInput | None
    frame_type: Literal["light", "bias", "dark", "flat", "dark_flat"]
    parameter_mode: Literal["iso", "gain"] | None
    iso: int | None
    exposure_seconds: float | None
    gain: float | None
    offset: float | None
    sensor_temperature_c: float | None
    binning_x: int | None
    binning_y: int | None
    notes: str | None
    status: Literal["active", "archived"]
    revision: int
    created_at: datetime
    updated_at: datetime


class AssetVersionOut(StrictModel):
    id: UUID
    asset_id: UUID
    version_number: int
    storage_mode: Literal["reference", "managed"]
    storage_location: str
    byte_size: int | None
    content_hash: str | None
    availability: Literal["unknown", "available", "changed", "missing"]
    camera_id: UuidInput | None
    optical_system_id: UuidInput | None
    filter_id: UuidInput | None
    capture_profile_id: UUID | None
    frame_type: Literal["light", "bias", "dark", "flat", "dark_flat"] | None
    calibration_level: Literal["individual", "master"] | None
    capture_snapshot: dict | None
    scientific_metadata: dict | None
    created_at: datetime


class AssetOut(StrictModel):
    id: UUID
    name: str
    scope: Literal["shared", "project"]
    owner_project_id: UUID | None
    role: Literal["raw", "calibration", "intermediate", "final"]
    calibration_level: Literal["individual", "master"] | None
    current_version_id: UUID | None
    classification: dict | None
    parameters: dict
    value_sources: dict
    notes: str | None
    status: Literal["active", "archived"]
    revision: int
    created_at: datetime
    current_version: AssetVersionOut | None


class ProjectAssetReferenceOut(StrictModel):
    id: UUID
    project_id: UUID
    asset_version_id: UUID
    added_at: datetime
    asset: AssetOut
    version: AssetVersionOut



class ProjectPage(StrictModel):
    items: list[ProjectOut]
    total: int
    limit: int
    offset: int


class EquipmentPage(StrictModel):
    items: list[EquipmentOut]
    total: int
    limit: int
    offset: int


class CaptureProfilePage(StrictModel):
    items: list[CaptureProfileOut]
    total: int
    limit: int
    offset: int


class AssetPage(StrictModel):
    items: list[AssetOut]
    total: int
    limit: int
    offset: int


class LibraryAssetItemOut(StrictModel):
    entry_type: Literal["asset"]
    asset: AssetOut
    import_issue: str | None


class ProjectAssetReferencePage(StrictModel):
    items: list[ProjectAssetReferenceOut]
    total: int
    limit: int
    offset: int


class ErrorDetail(StrictModel):
    code: str
    message: str
    fields: list[dict[str, str]]


class ErrorEnvelope(StrictModel):
    error: ErrorDetail
    request_id: UUID


class AssetVersionPage(StrictModel):
    items: list[AssetVersionOut]
    total: int
    limit: int
    offset: int


class ImportRootOut(StrictModel):
    id: str
    label: str
    available: bool


class ImportRootEntryOut(StrictModel):
    name: str
    path: str
    kind: Literal["file", "directory"]
    format: str | None
    supported: bool
    size: int | None


class ImportRootEntryPage(StrictModel):
    items: list[ImportRootEntryOut]
    total: int
    limit: int
    offset: int


class ImportAccepted(StrictModel):
    task_id: UUID
    status: Literal["queued"]


class TaskItemOut(StrictModel):
    id: UUID
    task_id: UUID
    root_item_id: UUID
    retry_of_item_id: UUID | None
    root_id: str
    source_path: str
    position: int
    status: str
    content_status: str
    metadata_status: str
    preview_status: str
    asset_id: UUID | None
    asset_version_id: UUID | None
    error: dict | None
    created_at: datetime
    updated_at: datetime


class AssetTaskOut(StrictModel):
    id: UUID
    status: str
    sources: list[dict]
    storage_mode: Literal["reference", "managed"]
    classification: dict
    parameters: dict
    notes: str | None
    dataset_name: str | None
    target_dataset_id: UUID | None
    dataset_base_revision: int | None
    dataset_id: UUID | None
    enumeration_completed: bool
    retry_of_task_id: UUID | None
    report: dict
    error: dict | None
    created_at: datetime
    updated_at: datetime
    items: list[TaskItemOut]
    items_total: int
    items_completed: int
    items_limit: int
    items_offset: int


class AssetTaskPage(StrictModel):
    items: list[AssetTaskOut]
    total: int
    limit: int
    offset: int


class DatasetOut(StrictModel):
    id: UUID
    name: str
    notes: str | None
    status: Literal["active", "archived"]
    revision: int
    current_version_id: UUID | None
    member_count: int
    created_at: datetime
    updated_at: datetime


class DatasetMemberParametersUpdateOut(StrictModel):
    dataset_id: UUID
    revision: int
    version_id: UUID
    assets: list[AssetOut]


class DatasetPage(StrictModel):
    items: list[DatasetOut]
    total: int
    limit: int
    offset: int


class DatasetMemberOut(StrictModel):
    id: UUID
    dataset_version_id: UUID
    asset_version_id: UUID
    position: int
    relative_path: str | None
    calibration_overrides: CalibrationBindings = Field(default_factory=dict)
    asset: AssetOut
    version: AssetVersionOut


class DatasetVersionOut(StrictModel):
    id: UUID
    dataset_id: UUID
    version_number: int
    created_at: datetime
    calibration_defaults: CalibrationBindings = Field(default_factory=dict)
    members: list[DatasetMemberOut]


class LibraryDatasetItemOut(StrictModel):
    entry_type: Literal["dataset"]
    dataset: DatasetOut
    version: DatasetVersionOut | None
    import_issue: str | None


LibraryItemOut = Annotated[LibraryAssetItemOut | LibraryDatasetItemOut, Field(discriminator="entry_type")]


class LibraryItemPage(StrictModel):
    items: list[LibraryItemOut]
    total: int
    limit: int
    offset: int


class LibraryEntriesRemoveOut(StrictModel):
    removed_count: int


class LibraryTrashGroupOut(StrictModel):
    id: UUID
    name: str
    in_trash: bool


class LibraryTrashItemOut(StrictModel):
    entry_type: Literal["asset", "dataset"]
    id: UUID
    name: str
    removed_at: datetime
    revision: int
    current_version_id: UUID | None
    cleanup_status: Literal["trash", "partial", "failed"]
    cleanup_error: str | None
    photo_count: int
    member_asset_ids: list[UUID] = Field(default_factory=list)
    groups: list[LibraryTrashGroupOut] = Field(default_factory=list)
    source_dataset_id: UUID | None = None


class LibraryTrashPage(StrictModel):
    items: list[LibraryTrashItemOut]
    total: int
    limit: int
    offset: int


class LibraryTrashReferenceOut(StrictModel):
    id: UUID
    kind: Literal["project_asset", "project_dataset", "dataset_member"]
    name: str
    version: int


class LibraryTrashPreviewOut(StrictModel):
    items: list[LibraryTrashItemOut]
    references: list[LibraryTrashReferenceOut]
    tasks: list[str]
    photo_count: int
    managed_file_count: int
    managed_bytes: int
    preview_fingerprint: str


class LibraryTrashDeleteOut(StrictModel):
    deleted_count: int
    deleted_entry_count: int
    deleted_file_count: int
    deleted_bytes: int
    missing_file_count: int
    failed: list[dict]


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


class DatasetVersionPage(StrictModel):
    items: list[DatasetVersionOut]
    total: int
    limit: int
    offset: int


class ProjectDatasetReferenceOut(StrictModel):
    id: UUID
    project_id: UUID
    dataset_id: UUID
    dataset_version_id: UUID
    base_revision: int
    added_at: datetime
    dataset: DatasetOut
    version: DatasetVersionOut


class ProjectDatasetReferencePage(StrictModel):
    items: list[ProjectDatasetReferenceOut]
    total: int
    limit: int
    offset: int


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


class FitsHduPage(StrictModel):
    items: list[FitsHduOut]
    total: int
    limit: int
    offset: int


class FitsHeaderOut(StrictModel):
    asset_version_id: UUID
    hdu_index: int
    cards: list[dict[str, Any]]
