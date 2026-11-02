"""Freeze actual member selections and import defaults at acceptance time."""

from copy import deepcopy
from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from astrophotoflow.contracts.equipment import EquipmentSnapshot
from astrophotoflow.contracts.metadata import AssetParametersPatch
from astrophotoflow.contracts.snapshots import ImportDefaultsSnapshot
from astrophotoflow.core.errors import invalid_reference
from astrophotoflow.modules.data.equipment.mapping import setup_out
from astrophotoflow.modules.data.equipment.members import member_kind
from astrophotoflow.modules.data.equipment.models import CapturePreset, Equipment, EquipmentSetup
from astrophotoflow.modules.data.equipment.optics import resolve_optics, validate_setup_members
from astrophotoflow.modules.data.equipment.presets import effective_preset_parameters, selected_filter

_equipment_snapshot_type = TypeAdapter(EquipmentSnapshot)


def snapshot_equipment(session: Session, equipment_id: str | None) -> EquipmentSnapshot | None:
    row = session.get(Equipment, equipment_id) if equipment_id else None
    if row is None:
        return None
    optics = resolve_optics(row.kind, row.specs, None) if row.kind == "telescope" else {}
    return _equipment_snapshot_type.validate_python({**optics, "id": row.id, "kind": row.kind, "name": row.name, "model": row.model,
            "specs": deepcopy(row.specs), "notes": row.notes})


def capture_defaults_snapshot(session: Session, preset_id: UUID | None, explicit_parameters: AssetParametersPatch) -> ImportDefaultsSnapshot:
    snapshot = {}
    if preset_id is not None:
        preset = session.get(CapturePreset, str(preset_id))
        if preset is None:
            raise invalid_reference("The capture preset does not exist.", message_key="the_capture_preset_does_not_exist")
        setup = session.get(EquipmentSetup, preset.equipment_setup_id)
        if setup is None:
            raise invalid_reference("The preset setup does not exist.", message_key="the_capture_preset_s_equipment_setup_does_not_exist")
        validate_setup_members(session, setup)
        components = setup_out(setup).model_dump(mode="json")["components"]
        for component in components:
            if component["source"] == "registered":
                equipment = session.get(Equipment, component["equipment_id"])
                component["equipment"] = {**snapshot_equipment(session, equipment.id).model_dump(mode="json", exclude_unset=True), "revision": equipment.revision}
            frozen = component["equipment"]
            if frozen["kind"] == "telescope":
                frozen.update(resolve_optics("telescope", frozen["specs"], component["optical_accessory_id"]))
        choices = {choice.kind: choice.member_id for choice in preset.choices}
        parameters = effective_preset_parameters(deepcopy(preset.parameters))
        selected, selected_members = {}, {}
        for kind in ("camera", "optical_system", "filter"):
            candidates = [member for member in setup.members if member_kind(session, member) == kind]
            if kind == "filter":
                chosen = selected_filter(session, setup, preset.choices)
            else:
                chosen = candidates[0] if candidates else None
            if chosen is not None:
                frozen = next(component["equipment"] for component in components if component["id"] == chosen.id)
                frozen = deepcopy(frozen)
                if kind == "optical_system":
                    frozen.update(resolve_optics("telescope", frozen["specs"], chosen.optical_accessory_id))
                selected[kind + "_id"] = frozen
                selected_members[kind] = chosen.id
                parameters[kind + "_id"] = chosen.equipment_id
            elif kind in choices:
                parameters[kind + "_id"] = None
        snapshot = {
            "parameters": parameters, "classification": {},
            "selected_equipment": selected, "selected_members": selected_members,
            "equipment_setup": {"id": setup.id, "revision": setup.revision, "name": setup.name,
                                "notes": setup.notes, "components": components},
            "capture_preset": {"id": preset.id, "revision": preset.revision, "name": preset.name},
        }
    identities = {str(value) for parameters in (explicit_parameters.model_dump(mode="json", exclude_unset=True), snapshot.get("parameters", {}))
                  for key in ("camera_id", "optical_system_id", "filter_id") if (value := parameters.get(key)) is not None}
    identities.update(component["equipment_id"] for component in snapshot.get("equipment_setup", {}).get("components", [])
                      if component["source"] == "registered")
    snapshot["equipment_snapshots"] = {identity: snapshot_equipment(session, identity) for identity in identities}
    return ImportDefaultsSnapshot.model_validate(snapshot)
