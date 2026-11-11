"""Resolve a setup member without treating inline equipment as registered."""
from sqlalchemy.orm import Session
from astrophotoflow.core.errors import invalid_reference
from astrophotoflow.modules.data.equipment.models import Equipment, EquipmentSetupMember

def capture_kind(kind: str) -> str:
    return 'optical_system' if kind == 'telescope' else kind

def member_kind(session: Session, member: EquipmentSetupMember) -> str:
    if member.equipment_id is None:
        kind = member.inline_equipment['kind']
    else:
        equipment = session.get(Equipment, member.equipment_id)
        if equipment is None:
            raise invalid_reference('The selected setup equipment no longer exists.')
        kind = equipment.kind
    return capture_kind(kind)
