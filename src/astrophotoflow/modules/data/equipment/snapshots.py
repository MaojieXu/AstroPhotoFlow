"""Freeze actual member selections and import defaults at acceptance time."""

from copy import deepcopy

from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from astrophotoflow.contracts.equipment import EquipmentSnapshot
from astrophotoflow.contracts.metadata import AssetParametersPatch
from astrophotoflow.contracts.snapshots import ImportDefaultsSnapshot
from astrophotoflow.modules.data.equipment.models import Equipment
from astrophotoflow.modules.data.equipment.optics import resolve_optics

_equipment_snapshot_type = TypeAdapter(EquipmentSnapshot)


def snapshot_equipment(session: Session, equipment_id: str | None) -> EquipmentSnapshot | None:
    row = session.get(Equipment, equipment_id) if equipment_id else None
    if row is None:
        return None
    optics = resolve_optics(row.kind, row.specs, None) if row.kind == "telescope" else {}
    return _equipment_snapshot_type.validate_python({**optics, "id": row.id, "kind": row.kind, "name": row.name, "model": row.model,
            **({} if row.kind == "mount" else {"specs": deepcopy(row.specs)}), "notes": row.notes})


def capture_defaults_snapshot(session: Session, explicit_parameters: AssetParametersPatch, equipment=None) -> ImportDefaultsSnapshot:
    """Freeze explicit equipment choices without supplying capture parameter defaults."""
    if equipment is not None:
        from astrophotoflow.modules.data.assets.image_metadata import freeze_import_equipment
        return ImportDefaultsSnapshot.model_validate(freeze_import_equipment(
            session, equipment, explicit_parameters.model_dump(mode="json", exclude_unset=True)))
    identities = {str(value) for key, value in explicit_parameters.model_dump(mode="json", exclude_unset=True).items()
                  if key in ("camera_id", "optical_system_id", "filter_id") and value is not None}
    return ImportDefaultsSnapshot(equipment_snapshots={identity: snapshot_equipment(session, identity) for identity in identities})
