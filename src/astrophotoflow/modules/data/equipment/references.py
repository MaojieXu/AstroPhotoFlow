"""Validate a newly assigned registry identity against its scientific role."""
from typing import Any
from uuid import UUID
from sqlalchemy.orm import Session
from astrophotoflow.core.errors import invalid_reference
from astrophotoflow.modules.data.equipment.members import capture_kind
from astrophotoflow.modules.data.equipment.models import Equipment

def validate_equipment_reference(session: Session, value: UUID | str | None, kind: str, path: str) -> None:
    if value is None:
        return
    equipment = session.get(Equipment, str(value))
    if equipment is None or capture_kind(equipment.kind) != kind:
        raise invalid_reference(f'{path} must reference existing {kind} equipment.', message_key='p0_must_reference_an_existing_p1_device', message_params={'p0': path, 'p1': kind})

def _check_equipment(session, value: Any, expected: str) -> None:
    if value is None:
        return
    row = session.get(Equipment, str(value))
    if row is None or capture_kind(row.kind) != expected:
        raise invalid_reference(f'参数中的设备必须是现存的 {expected} 设备。', message_key='the_parameter_must_reference_an_existing_p0_device', message_params={'p0': expected})

def validate_import_equipment(session, parameters: dict) -> None:
    for key, kind in (('camera_id', 'camera'), ('optical_system_id', 'optical_system'), ('filter_id', 'filter')):
        _check_equipment(session, parameters.get(key), kind)
