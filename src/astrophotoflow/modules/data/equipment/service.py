"""Equipment operations within the caller's database transaction."""
from datetime import UTC, datetime
from uuid import UUID, uuid4
from sqlalchemy import update
from sqlalchemy.orm import Session
from astrophotoflow.contracts.equipment import EquipmentCreate, EquipmentOut, EquipmentPatch
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.modules.data.equipment.mapping import equipment_out
from astrophotoflow.modules.data.equipment.models import Equipment
from astrophotoflow.modules.data.equipment.optics import validate_equipment_optics_change
from astrophotoflow.modules.data.names import named_changes

def get_equipment(session: Session, equipment_id: UUID) -> EquipmentOut:
    row = session.get(Equipment, str(equipment_id))
    if row is None:
        raise not_found()
    return equipment_out(row)

def create_equipment(session: Session, body: EquipmentCreate) -> EquipmentOut:
    now = datetime.now(UTC)
    row = Equipment(id=str(uuid4()), kind=body.kind, name=body.name, model=body.model, notes=body.notes, specs={} if body.kind == 'mount' else body.specs.model_dump(mode='json'), status='active', revision=1, created_at=now, updated_at=now)
    session.add(row)
    session.flush()
    return equipment_out(row)

def update_equipment(session: Session, equipment_id: UUID, body: EquipmentPatch) -> EquipmentOut:
    key = str(equipment_id)
    row = session.get(Equipment, key)
    if row is None:
        raise not_found()
    if body.kind != row.kind:
        raise ApiError(422, 'VALIDATION_ERROR', 'Equipment kind cannot change after creation.', [{'path': 'kind', 'message': 'Must match the existing equipment kind.'}], message_key='equipment_kind_cannot_be_changed_after_creation', field_message_keys={'kind': 'field_equipment_kind'})
    changes = body.model_dump(mode='json', exclude_unset=True, exclude={'base_revision', 'kind', 'specs'})
    fields = [{'path': name, 'message': 'Cannot be null.'} for name in ('name', 'status') if name in changes and changes[name] is None]
    if fields:
        raise ApiError(422, 'VALIDATION_ERROR', 'Invalid request fields.', fields, message_key='invalid_request_fields', field_message_keys={item['path']: 'field_not_nullable' for item in fields})
    if 'specs' in body.model_fields_set:
        if body.specs is None:
            raise ApiError(422, 'VALIDATION_ERROR', 'specs cannot be null.', [{'path': 'specs', 'message': 'Provide typed specifications.'}], message_key='specs_must_not_be_null', field_message_keys={'specs': 'field_typed_specs'})
        changes['specs'] = {**row.specs, **body.specs.model_dump(mode='json', exclude_unset=True)}
    if 'specs' in changes and row.kind == 'telescope':
        validate_equipment_optics_change(session, row, changes['specs'])
    changed = session.execute(update(Equipment).where(Equipment.id == key, Equipment.revision == body.base_revision).values(**named_changes(changes), revision=body.base_revision + 1, updated_at=datetime.now(UTC)))
    if changed.rowcount != 1:
        raise ApiError(409, 'REVISION_CONFLICT', 'Another window changed this equipment.', message_key='another_window_changed_the_configuration_read_it_again_before_saving')
    session.flush()
    session.refresh(row)
    return equipment_out(row)
