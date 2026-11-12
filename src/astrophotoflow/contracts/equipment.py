from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4
from pydantic import Field, field_validator
from astrophotoflow.contracts.common import CfaPattern, EquipmentKind, PageMetadata, SnapshotModel, StrictModel, UuidInput, check_name, finite

class CameraSpecs(StrictModel):
    sensor_width_px: int | None = Field(default=None, gt=0)
    sensor_height_px: int | None = Field(default=None, gt=0)
    pixel_size_um: float | None = Field(default=None, gt=0)
    native_bit_depth: int | None = Field(default=None, gt=0)
    cfa_pattern: CfaPattern | None = None
    default_parameter_mode: Literal['iso', 'gain'] | None = None

    @field_validator('pixel_size_um')
    @classmethod
    def validate_pixel_size(cls, value):
        return finite(value)

class OpticalAccessory(StrictModel):
    id: UuidInput = Field(default_factory=uuid4)
    name: str
    factor: float = Field(gt=0)
    _name = field_validator('name')(check_name)
    _factor = field_validator('factor')(finite)

class TelescopeSpecs(StrictModel):
    native_focal_length_mm: float | None = Field(default=None, gt=0)
    optical_accessories: list[OpticalAccessory] = Field(default_factory=list)

    @field_validator('native_focal_length_mm')
    @classmethod
    def validate_optics(cls, value):
        return finite(value)

    @field_validator('optical_accessories')
    @classmethod
    def validate_accessory_ids(cls, value):
        if len({item.id for item in value}) != len(value):
            raise ValueError('Optical accessory IDs must be unique within a telescope.')
        return value
FILTER_CHANNEL_PROMPT = "Channel is a free-text imaging-channel/passband label, not a product name, camera CFA pattern, or mandatory display-color assignment. Prefer the user's explicit label and spelling. The Agent may fill a clear passband from supplied facts, FITS FILTER, or reliable product specifications; omit unknowns. Examples: luminance -> L; red/green/blue -> R/G/B; Ha -> H; OIII -> O; SII -> S; one confirmed RGB filter -> RGB; an explicitly described IR875nm filter -> Ir875nm. Three separate SII/Ha/OIII filters are three entries with S/H/O; one confirmed multi-band SHO filter remains one entry with SHO. A color camera does not imply an RGB filter. Do not derive bandwidth or central wavelength from channel: 875nm may be a long-pass cutoff. Different filters with the same channel remain separate devices. Omitted PATCH keeps the value; null clears it. 中文：Channel是成像通道／通带自由文本标签，明确用途可由Agent填写，未知不猜，用户自定义值优先。"

class FilterSpecs(StrictModel):
    channel: str | None = Field(default=None, description=FILTER_CHANNEL_PROMPT)
    filter_type: str | None = None
    central_wavelength_nm: float | None = Field(default=None, gt=0)
    bandwidth_nm: float | None = Field(default=None, gt=0)
    bandpass_note: str | None = None

    @field_validator('central_wavelength_nm', 'bandwidth_nm')
    @classmethod
    def validate_band(cls, value):
        return finite(value)

    @field_validator('channel')
    @classmethod
    def validate_channel(cls, value):
        return value.strip() or None if value is not None else None

class EquipmentCreateBase(StrictModel):
    name: str
    model: str | None = None
    notes: str | None = None
    _name = field_validator('name')(check_name)

class CameraCreate(EquipmentCreateBase):
    kind: Literal['camera']
    specs: CameraSpecs = Field(default_factory=CameraSpecs)

class FilterCreate(EquipmentCreateBase):
    kind: Literal['filter']
    specs: FilterSpecs = Field(default_factory=FilterSpecs)

class TelescopeCreate(EquipmentCreateBase):
    kind: Literal['telescope']
    specs: TelescopeSpecs = Field(default_factory=TelescopeSpecs)

class MountCreate(EquipmentCreateBase):
    kind: Literal['mount']
EquipmentCreate = Annotated[CameraCreate | FilterCreate | TelescopeCreate | MountCreate, Field(discriminator='kind')]

class EquipmentPatchBase(StrictModel):
    base_revision: int = Field(ge=1)
    name: str | None = None
    model: str | None = None
    notes: str | None = None
    status: Literal['active', 'archived'] | None = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, value):
        return None if value is None else check_name(value)

class CameraPatch(EquipmentPatchBase):
    kind: Literal['camera']
    specs: CameraSpecs | None = None

class FilterPatch(EquipmentPatchBase):
    kind: Literal['filter']
    specs: FilterSpecs | None = None

class TelescopePatch(EquipmentPatchBase):
    kind: Literal['telescope']
    specs: TelescopeSpecs | None = None

class MountPatch(EquipmentPatchBase):
    kind: Literal['mount']
EquipmentPatch = Annotated[CameraPatch | FilterPatch | TelescopePatch | MountPatch, Field(discriminator='kind')]

class EquipmentOutBase(StrictModel):
    id: UUID
    name: str
    model: str | None
    notes: str | None
    status: Literal['active', 'archived']
    revision: int
    created_at: datetime
    updated_at: datetime

class CameraOut(EquipmentOutBase):
    kind: Literal['camera']
    specs: CameraSpecs

class FilterOut(EquipmentOutBase):
    kind: Literal['filter']
    specs: FilterSpecs

class TelescopeOut(EquipmentOutBase):
    kind: Literal['telescope']
    specs: TelescopeSpecs

class MountOut(EquipmentOutBase):
    kind: Literal['mount']
EquipmentOut = Annotated[CameraOut | FilterOut | TelescopeOut | MountOut, Field(discriminator='kind')]

class EquipmentQuery(StrictModel):
    limit: int = Field(default=50, ge=1, le=200, strict=False)
    offset: int = Field(default=0, ge=0, strict=False)
    sort_by: Literal['created_at', 'name'] = 'created_at'
    order: Literal['asc', 'desc'] = 'desc'
    q: str | None = None
    status: Literal['active', 'archived', 'all'] = 'active'
    kind: EquipmentKind | None = None

class EquipmentPage(PageMetadata):
    items: list[EquipmentOut]

class EquipmentSnapshotBase(SnapshotModel):
    id: UuidInput | None = None
    name: str
    model: str | None = None
    serial_number: str | None = None
    notes: str | None = None
    revision: int | None = Field(default=None, ge=1)

class CameraSnapshotSpecs(CameraSpecs):
    """Previously recorded sensor facts; never accepted by the device editor."""
    sensor_mode: Literal['mono', 'color'] | None = None

class TelescopeSnapshotSpecs(TelescopeSpecs):
    """Keep previously frozen aperture observations readable without rewriting them."""
    aperture_mm: float | None = Field(default=None, gt=0)
    _aperture = field_validator('aperture_mm')(finite)

class CameraSnapshot(EquipmentSnapshotBase):
    kind: Literal['camera']
    specs: CameraSnapshotSpecs

class FilterSnapshot(EquipmentSnapshotBase):
    kind: Literal['filter']
    specs: FilterSpecs

class TelescopeSnapshot(EquipmentSnapshotBase):
    kind: Literal['telescope']
    specs: TelescopeSnapshotSpecs
    optical_accessory: OpticalAccessory | None = None
    effective_focal_length_mm: float | None = Field(default=None, gt=0)

class MountSnapshot(EquipmentSnapshotBase):
    kind: Literal['mount']
EquipmentSnapshot = Annotated[CameraSnapshot | FilterSnapshot | TelescopeSnapshot | MountSnapshot, Field(discriminator='kind')]

class EquipmentSnapshots(SnapshotModel):
    camera_id: CameraSnapshot | None = None
    optical_system_id: TelescopeSnapshot | None = None
    filter_id: FilterSnapshot | None = None
    mount_id: MountSnapshot | None = None
