"""Contracts shared by equipment setup UI, imports, CLI and MCP."""
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator

from .import_schemas import AssetClassification, AssetParametersPatch
from .schemas import EquipmentCreate, StrictModel, UuidInput, check_name


class RegisteredComponent(StrictModel):
    source: Literal["registered"]
    equipment_id: UuidInput


class InlineComponent(StrictModel):
    source: Literal["inline"]
    equipment: EquipmentCreate


SetupComponent = Annotated[RegisteredComponent | InlineComponent, Field(discriminator="source")]


class EquipmentSetupCreate(StrictModel):
    name: str
    components: list[SetupComponent] = Field(default_factory=list)
    notes: str | None = None

    _name = field_validator("name")(check_name)


class EquipmentSetupPatch(StrictModel):
    base_revision: int = Field(ge=1)
    name: str | None = None
    components: list[SetupComponent] | None = None
    notes: str | None = None
    status: Literal["active", "archived"] | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        return None if value is None else check_name(value)


class EquipmentSetupOut(EquipmentSetupCreate):
    id: UUID
    status: Literal["active", "archived"]
    revision: int
    created_at: datetime
    updated_at: datetime


class EquipmentSetupPage(StrictModel):
    items: list[EquipmentSetupOut]
    total: int
    limit: int
    offset: int


class CapturePresetCreate(StrictModel):
    name: str
    classification: AssetClassification = Field(default_factory=AssetClassification)
    parameters: AssetParametersPatch = Field(default_factory=AssetParametersPatch)
    notes: str | None = None

    _name = field_validator("name")(check_name)


class CapturePresetPatch(StrictModel):
    base_revision: int = Field(ge=1)
    name: str | None = None
    classification: AssetClassification | None = None
    parameters: AssetParametersPatch | None = None
    notes: str | None = None
    status: Literal["active", "archived"] | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        return None if value is None else check_name(value)


class CapturePresetOut(CapturePresetCreate):
    id: UUID
    equipment_setup_id: UUID
    status: Literal["active", "archived"]
    revision: int
    created_at: datetime
    updated_at: datetime


class CapturePresetPage(StrictModel):
    items: list[CapturePresetOut]
    total: int
    limit: int
    offset: int
