"""Validate the stored specification against its equipment discriminator."""

from datetime import UTC
from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy.orm import object_session

from astrophotoflow.contracts.equipment import EquipmentOut
from astrophotoflow.contracts.setups import EquipmentSetupOut, InlineComponentOut, RegisteredComponentOut
from astrophotoflow.modules.data.equipment.models import Equipment, EquipmentSetup
from astrophotoflow.modules.data.equipment.optics import member_equipment, resolve_optics

_output = TypeAdapter(EquipmentOut)


def equipment_out(row: Equipment) -> EquipmentOut:
    return _output.validate_python({
        "id": UUID(row.id), "kind": row.kind, "name": row.name, "model": row.model,
        "notes": row.notes, **({} if row.kind == "mount" else {"specs": row.specs}),
        "status": row.status, "revision": row.revision,
        "created_at": row.created_at.replace(tzinfo=UTC) if row.created_at.tzinfo is None else row.created_at,
        "updated_at": row.updated_at.replace(tzinfo=UTC) if row.updated_at.tzinfo is None else row.updated_at,
    })


def setup_out(row: EquipmentSetup) -> EquipmentSetupOut:
    session = object_session(row)
    components = []
    for member in row.members:
        focal = resolve_optics(*member_equipment(session, member), member.optical_accessory_id)["effective_focal_length_mm"]
        shared = {"id": UUID(member.id), "optical_accessory_id": member.optical_accessory_id,
                  "effective_focal_length_mm": focal}
        components.append(RegisteredComponentOut(source="registered", equipment_id=member.equipment_id, **shared)
                          if member.equipment_id is not None else
                          InlineComponentOut(source="inline", equipment=member.inline_equipment, **shared))
    return EquipmentSetupOut(id=UUID(row.id), name=row.name, components=components, notes=row.notes,
                             status=row.status, revision=row.revision,
                             created_at=row.created_at.replace(tzinfo=UTC) if row.created_at.tzinfo is None else row.created_at,
                             updated_at=row.updated_at.replace(tzinfo=UTC) if row.updated_at.tzinfo is None else row.updated_at)
