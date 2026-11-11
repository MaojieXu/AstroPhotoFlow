from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID
from pydantic import Field, field_validator
from astrophotoflow.contracts.common import EquipmentKind, PageMetadata, StrictModel, UuidInput, check_name
from astrophotoflow.contracts.equipment import EquipmentCreate

class RegisteredComponent(StrictModel):
    id: UuidInput | None = None
    source: Literal['registered']
    equipment_id: UuidInput
    optical_accessory_id: UuidInput | None = None

class InlineComponent(StrictModel):
    id: UuidInput | None = None
    source: Literal['inline']
    equipment: EquipmentCreate
    optical_accessory_id: UuidInput | None = None
SetupComponent = Annotated[RegisteredComponent | InlineComponent, Field(discriminator='source')]

class EquipmentSetupCreate(StrictModel):
    name: str
    components: list[SetupComponent] = Field(default_factory=list)
    notes: str | None = None
    _name = field_validator('name')(check_name)

class EquipmentSetupPatch(StrictModel):
    base_revision: int = Field(ge=1)
    name: str | None = None
    components: list[SetupComponent] | None = None
    notes: str | None = None
    status: Literal['active', 'archived'] | None = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, value):
        return None if value is None else check_name(value)

class RegisteredComponentOut(RegisteredComponent):
    id: UUID
    effective_focal_length_mm: float | None = None

class InlineComponentOut(InlineComponent):
    id: UUID
    effective_focal_length_mm: float | None = None
SetupComponentOut = Annotated[RegisteredComponentOut | InlineComponentOut, Field(discriminator='source')]

class EquipmentSetupOut(EquipmentSetupCreate):
    components: list[SetupComponentOut]
    id: UUID
    status: Literal['active', 'archived']
    revision: int
    created_at: datetime
    updated_at: datetime

class EquipmentSetupPage(PageMetadata):
    items: list[EquipmentSetupOut]

class EquipmentSetupQuery(StrictModel):
    limit: int = Field(default=50, ge=1, le=200, strict=False)
    offset: int = Field(default=0, ge=0, strict=False)
    sort_by: Literal['created_at', 'name', 'camera', 'telescope', 'filter', 'mount'] = 'created_at'
    order: Literal['asc', 'desc'] = 'desc'
    q: str | None = None
    status: Literal['active', 'archived', 'all'] = 'active'
    component_kind: EquipmentKind | None = None
