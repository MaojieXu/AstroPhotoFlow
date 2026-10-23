from datetime import datetime
from math import isfinite
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer


UuidInput = Annotated[UUID, Field(strict=False)]


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
    cfa_pattern: str | None = None

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


EquipmentCreate = Annotated[CameraCreate | OpticalSystemCreate | FilterCreate, Field(discriminator="kind")]


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
    cfa_pattern: str | None = None

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


EquipmentPatch = Annotated[CameraPatch | OpticalSystemPatch | FilterPatch, Field(discriminator="kind")]


class CaptureProfileCreate(StrictModel):
    name: str
    camera_id: UuidInput
    optical_system_id: UuidInput | None = None
    filter_id: UuidInput | None = None
    frame_type: Literal["light", "bias", "dark", "flat", "dark_flat"]
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
    kind: Literal["camera", "optical_system", "filter"]
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
    current_version_id: UUID | None
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
