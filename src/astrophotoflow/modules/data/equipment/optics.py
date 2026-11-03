"""Resolve telescope-owned accessories and the effective focal length."""

from math import isfinite

from sqlalchemy import select
from sqlalchemy.orm import Session

from astrophotoflow.core.errors import invalid_reference
from astrophotoflow.modules.data.equipment.models import Equipment, EquipmentSetup, EquipmentSetupMember


def member_equipment(session: Session, member: EquipmentSetupMember) -> tuple[str, dict]:
    if member.equipment_id is None:
        return member.inline_equipment["kind"], member.inline_equipment.get("specs", {})
    equipment = session.get(Equipment, member.equipment_id)
    if equipment is None:
        raise invalid_reference("The selected setup equipment no longer exists.")
    return equipment.kind, equipment.specs


def resolve_optics(kind: str, specs: dict, accessory_id: str | None) -> dict:
    if kind != "telescope":
        if accessory_id is not None:
            raise invalid_reference("Only telescope members may select an optical accessory.")
        return {"optical_accessory": None, "effective_focal_length_mm": None}
    accessory = None
    if accessory_id is not None:
        accessory = next((item for item in specs.get("optical_accessories", [])
                          if str(item["id"]) == str(accessory_id)), None)
        if accessory is None:
            raise invalid_reference("The selected optical accessory is unavailable on this telescope. Update the setup selection before removing or replacing that accessory.")
    base = specs.get("native_focal_length_mm")
    focal = base * (accessory["factor"] if accessory is not None else 1.0) if base is not None else None
    if focal is not None and (not isfinite(focal) or focal <= 0):
        raise invalid_reference("The effective focal length must be a finite positive number.")
    return {"optical_accessory": accessory, "effective_focal_length_mm": focal}


def validate_setup_members(session: Session, setup: EquipmentSetup) -> None:
    counts = {"camera": 0, "telescope": 0, "mount": 0}
    for member in setup.members:
        kind, _ = member_equipment(session, member)
        if kind in counts:
            counts[kind] += 1
    if any(count > 1 for count in counts.values()):
        raise invalid_reference("A setup may contain at most one camera, one telescope and one mount, including registered and inline equipment.")


def validate_setup_optics(session: Session, setup: EquipmentSetup) -> None:
    validate_setup_members(session, setup)
    for member in setup.members:
        resolve_optics(*member_equipment(session, member), member.optical_accessory_id)


def validate_equipment_optics_change(session: Session, equipment: Equipment, specs: dict) -> None:
    """Reject removals that would leave current member selections dangling."""
    members = session.scalars(select(EquipmentSetupMember).where(
        EquipmentSetupMember.equipment_id == equipment.id)).all()
    for member in members:
        resolve_optics(equipment.kind, specs, member.optical_accessory_id)
