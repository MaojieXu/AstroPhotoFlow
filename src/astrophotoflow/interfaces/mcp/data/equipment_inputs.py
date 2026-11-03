"""Explicit MCP views over the shared device configuration contracts."""

from typing import Annotated, ClassVar, Literal

from pydantic import MISSING, AfterValidator, Field, model_validator

from astrophotoflow.contracts.common import EquipmentKind, StrictModel, UuidInput, check_name
from astrophotoflow.contracts.equipment import CameraSpecs, EquipmentCreate, EquipmentQuery, FilterSpecs, TelescopeSpecs
from astrophotoflow.contracts.setups import EquipmentSetupQuery
from astrophotoflow.contracts.trash import EquipmentDeleteSelection

EquipmentName = Annotated[str, AfterValidator(check_name)]


class EquipmentChanges(StrictModel):
    name: EquipmentName | MISSING = MISSING
    model: str | None | MISSING = MISSING
    notes: str | None | MISSING = MISSING
    status: Literal["active", "archived"] | MISSING = MISSING


class CameraChanges(EquipmentChanges):
    specs: CameraSpecs | MISSING = MISSING


class TelescopeChanges(EquipmentChanges):
    specs: TelescopeSpecs | MISSING = MISSING


class FilterChanges(EquipmentChanges):
    specs: FilterSpecs | MISSING = MISSING


class MountChanges(EquipmentChanges):
    """A mount has common identity fields, without capture or control settings."""


class EquipmentSearch(EquipmentQuery):
    q: ClassVar
    kind: ClassVar
    text: str | None = Field(default=None, description="Search the user-provided device name or model; a name is not a unique identity.")
    equipment_type: EquipmentKind | None = None

    def to_query(self) -> EquipmentQuery:
        return EquipmentQuery.model_validate({**self.model_dump(exclude={"text", "equipment_type"}),
                                              "q": self.text, "kind": self.equipment_type})


class SetupSearch(EquipmentSetupQuery):
    q: ClassVar
    component_kind: ClassVar
    text: str | None = None
    component_type: EquipmentKind | None = None

    def to_query(self) -> EquipmentSetupQuery:
        return EquipmentSetupQuery.model_validate({**self.model_dump(exclude={"text", "component_type"}),
                                                   "q": self.text, "component_kind": self.component_type})


class RegisteredMember(StrictModel):
    source: Literal["registered"]
    member_id: UuidInput | None = Field(default=None, description="Existing setup component id; retain it when replacing an existing member.")
    equipment_id: UuidInput
    optical_accessory_id: UuidInput | None = None


class InlineMember(StrictModel):
    source: Literal["inline"]
    member_id: UuidInput | None = Field(default=None, description="Existing setup component id; retain it when replacing an existing member.")
    equipment: EquipmentCreate
    optical_accessory_id: UuidInput | None = None


SetupMember = Annotated[RegisteredMember | InlineMember, Field(discriminator="source")]


def member_inputs(members: list[SetupMember]) -> list[dict]:
    result = []
    for member in members:
        payload = member.model_dump(mode="json", exclude_unset=True)
        if "member_id" in payload:
            payload["id"] = payload.pop("member_id")
        result.append(payload)
    return result


class SetupChanges(StrictModel):
    name: EquipmentName | MISSING = MISSING
    notes: str | None | MISSING = MISSING
    status: Literal["active", "archived"] | MISSING = MISSING
    members: list[SetupMember] | MISSING = Field(default=MISSING, description="Complete ordered replacement; preserve existing member_id values. Omit to keep all members.")

    def to_changes(self) -> dict:
        result = self.model_dump(mode="json", exclude_unset=True, exclude={"members"})
        if self.members is not MISSING:
            result["components"] = member_inputs(self.members)
        return result


class VersionedRef(StrictModel):
    id: UuidInput
    revision: int = Field(ge=1)


class ConfigurationTargets(StrictModel):
    equipment: list[VersionedRef] = Field(default_factory=list)
    setups: list[VersionedRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_targets(self):
        if not (self.equipment or self.setups):
            raise ValueError("Select at least one equipment or setup with its current revision.")
        for group in (self.equipment, self.setups):
            if len({item.id for item in group}) != len(group):
                raise ValueError("Each target id may appear only once in its group.")
        return self

    def to_selection(self) -> EquipmentDeleteSelection:
        groups = (("equipment", self.equipment), ("equipment_setup", self.setups))
        return EquipmentDeleteSelection(items=[{"entry_type": kind, "id": item.id, "revision": item.revision}
                                                for kind, values in groups for item in values])
