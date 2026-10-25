"""Freeze import defaults once, independently of live configuration edits."""
from copy import deepcopy
from uuid import UUID

from .errors import invalid_reference
from .models import CapturePreset, Equipment, EquipmentSetup


def capture_defaults_snapshot(session, preset_id: UUID | None) -> dict:
    if preset_id is None:
        return {}
    preset = session.get(CapturePreset, str(preset_id))
    if preset is None:
        raise invalid_reference("拍摄预设不存在。")
    setup = session.get(EquipmentSetup, preset.equipment_setup_id)
    if setup is None:
        raise invalid_reference("拍摄预设的使用组合不存在。")
    components = []
    parameters = {key: deepcopy(value) for key, value in preset.parameters.items() if value is not None}
    for component in setup.components:
        frozen = deepcopy(component)
        if component["source"] == "registered":
            equipment = session.get(Equipment, component["equipment_id"])
            if equipment is None:
                raise invalid_reference("使用组合引用的设备不存在。")
            frozen["equipment"] = {
                "id": equipment.id, "kind": equipment.kind, "name": equipment.name,
                "model": equipment.model, "serial_number": equipment.serial_number,
                "specs": deepcopy(equipment.specs), "revision": equipment.revision,
                "notes": equipment.notes,
            }
            if equipment.kind in {"camera", "optical_system", "filter"}:
                parameters.setdefault(equipment.kind + "_id", equipment.id)
        components.append(frozen)
    return {
        "parameters": parameters,
        "classification": deepcopy(preset.classification),
        "equipment_setup": {"id": setup.id, "revision": setup.revision, "name": setup.name,
                            "notes": setup.notes, "components": components},
        "capture_preset": {"id": preset.id, "revision": preset.revision, "name": preset.name},
    }
