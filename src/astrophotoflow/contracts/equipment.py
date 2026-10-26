from astrophotoflow.contracts.common import CfaPattern, EquipmentKind, StrictModel, check_name, finite
from datetime import datetime
from pydantic import Field, field_validator
from typing import Annotated, Literal
from uuid import UUID


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


class EquipmentPage(StrictModel):
    items: list[EquipmentOut]
    total: int
    limit: int
    offset: int
