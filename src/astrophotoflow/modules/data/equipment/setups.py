"""Ordered setup members, with SQL filtering and caller-owned transactions."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import update
from sqlalchemy.orm import Session

from astrophotoflow.contracts.setups import (
    EquipmentSetupCreate,
    EquipmentSetupOut,
    EquipmentSetupPatch,
    SetupComponent,
)
from astrophotoflow.core.errors import ApiError, invalid_reference, not_found
from astrophotoflow.modules.data.equipment.mapping import setup_out
from astrophotoflow.modules.data.equipment.members import capture_kind, member_kind
from astrophotoflow.modules.data.equipment.models import Equipment, EquipmentSetup, EquipmentSetupMember
from astrophotoflow.modules.data.equipment.optics import validate_setup_optics
from astrophotoflow.modules.data.equipment.presets import clear_member_selections
from astrophotoflow.modules.data.names import named_changes


def _replace_members(session: Session, row: EquipmentSetup, components: list[SetupComponent]) -> None:
    existing = {member.id: member for member in row.members}
    supplied = [str(component.id) for component in components if component.id is not None]
    if len(supplied) != len(set(supplied)) or not set(supplied).issubset(existing):
        raise invalid_reference("Member IDs must be unique and belong to this setup.")
    for component in components:
        if component.source == "registered" and session.get(Equipment, str(component.equipment_id)) is None:
            raise invalid_reference("The setup must reference existing equipment.",
                                    message_key="the_equipment_setup_must_reference_existing_registered_equipment")
    invalidated = set(existing) - set(supplied)
    for component in components:
        if component.id is not None:
            kind = (session.get(Equipment, str(component.equipment_id)).kind if component.source == "registered"
                    else component.equipment.kind)
            kind = capture_kind(kind)
            if member_kind(session, existing[str(component.id)]) != kind:
                invalidated.add(str(component.id))
    clear_member_selections(session, invalidated)
    # Move existing positions out of the final range before reordering; retain
    # member identities, including those referenced by presets.
    shift = max((member.position for member in row.members), default=0) + len(components) + 1
    for member in row.members:
        member.position += shift
    session.flush()
    result = []
    for position, component in enumerate(components):
        member = existing.get(str(component.id)) if component.id is not None else None
        if member is None:
            member = EquipmentSetupMember(id=str(uuid4()), setup_id=row.id)
        member.optical_accessory_id = str(component.optical_accessory_id) if component.optical_accessory_id is not None else None
        member.position = position
        member.equipment_id = str(component.equipment_id) if component.source == "registered" else None
        member.inline_equipment = component.equipment.model_dump(mode="json") if component.source == "inline" else None
        result.append(member)
    row.members = result
    validate_setup_optics(session, row)


def create_setup(session: Session, body: EquipmentSetupCreate) -> EquipmentSetupOut:
    now = datetime.now(UTC)
    row = EquipmentSetup(id=str(uuid4()), name=body.name, notes=body.notes, status="active", revision=1,
                         created_at=now, updated_at=now)
    session.add(row)
    _replace_members(session, row, body.components)
    session.flush()
    return setup_out(row)


def get_setup(session: Session, setup_id: UUID) -> EquipmentSetupOut:
    row = session.get(EquipmentSetup, str(setup_id))
    if row is None:
        raise not_found()
    return setup_out(row)


def update_setup(session: Session, setup_id: UUID, body: EquipmentSetupPatch) -> EquipmentSetupOut:
    row = session.get(EquipmentSetup, str(setup_id))
    if row is None:
        raise not_found()
    changes = body.model_dump(mode="json", exclude_unset=True, exclude={"base_revision", "components"})
    fields = [key for key in ("name", "status", "components") if key in body.model_fields_set and getattr(body, key) is None]
    if fields:
        raise ApiError(422, "VALIDATION_ERROR", "These fields cannot be null.",
                       [{"path": field, "message": "Cannot be null."} for field in fields],
                       message_key="invalid_request_fields", field_message_keys={field: "field_not_nullable" for field in fields})
    changed = session.execute(update(EquipmentSetup).where(EquipmentSetup.id == row.id, EquipmentSetup.revision == body.base_revision)
                              .values(**named_changes(changes), revision=body.base_revision + 1, updated_at=datetime.now(UTC)))
    if changed.rowcount != 1:
        raise ApiError(409, "REVISION_CONFLICT", "The setup changed in another window.",
                       message_key="another_window_changed_the_configuration_read_it_again_before_saving")
    if "components" in body.model_fields_set:
        _replace_members(session, row, body.components)
    session.flush()
    session.refresh(row)
    return setup_out(row)
