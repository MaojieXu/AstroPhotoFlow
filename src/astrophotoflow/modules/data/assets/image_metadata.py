"""Current image facts and equipment selections frozen for explicit imports."""

import json
from copy import deepcopy
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from astrophotoflow.contracts.image_management import EquipmentApplication, ImageMetadata
from astrophotoflow.contracts.snapshots import ImportDefaultsSnapshot
from astrophotoflow.core.errors import ApiError, invalid_reference
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion, ImageMetadataState, MasterProvenanceRevision
from astrophotoflow.modules.data.equipment.mapping import setup_out
from astrophotoflow.modules.data.equipment.models import Equipment, EquipmentSetup
from astrophotoflow.modules.data.equipment.optics import resolve_optics, validate_setup_members
from astrophotoflow.modules.data.equipment.snapshots import snapshot_equipment


def _revision(row, expected: int) -> None:
    if row is None or row.status != "active":
        raise invalid_reference("The selected equipment or setup is unavailable.")
    if row.revision != expected:
        raise ApiError(409, "REVISION_CONFLICT", "The selected equipment changed; review the current revision.")


def _setup_snapshot(session: Session, choice: dict, fields: list[str]) -> dict:
    setup = session.get(EquipmentSetup, choice["setup_id"])
    _revision(setup, choice["expected_revision"])
    validate_setup_members(session, setup)
    components = setup_out(setup).model_dump(mode="json")["components"]
    selected, selected_members, parameters, registry = {}, {}, {}, {}
    for component in components:
        if component["source"] == "registered":
            row = session.get(Equipment, component["equipment_id"])
            if row is None or row.status != "active":
                raise invalid_reference("The selected setup contains unavailable equipment.")
            frozen = snapshot_equipment(session, row.id).model_dump(mode="json", exclude_unset=True)
            frozen["revision"] = row.revision
            component["equipment"] = frozen
            registry[row.id] = deepcopy(frozen)
        frozen = component["equipment"]
        if frozen["kind"] == "telescope":
            frozen.update(resolve_optics("telescope", frozen["specs"], component["optical_accessory_id"]))
    filters = [item for item in components if item["equipment"]["kind"] == "filter"]
    filter_choice = choice.get("filter", {"mode": "inherit"})
    if filter_choice["mode"] == "inherit" and len(filters) > 1 and "filter" in fields:
        raise invalid_reference("This setup has multiple filters; select the actual filter member explicitly.")
    chosen_filter = filters[0] if filters else None
    if filter_choice["mode"] == "none":
        chosen_filter = None
    elif filter_choice["mode"] == "member":
        chosen_filter = next((item for item in filters if item["id"] == filter_choice["member_id"]), None)
        if chosen_filter is None:
            raise invalid_reference("Select a filter member of the selected setup.")
    for public_kind, stored_kind in (("camera", "camera"), ("telescope", "optical_system"), ("filter", "filter"), ("mount", "mount")):
        component = chosen_filter if public_kind == "filter" else next(
            (item for item in components if item["equipment"]["kind"] == public_kind), None)
        key = stored_kind + "_id"
        if public_kind != "mount":
            parameters[key] = component.get("equipment_id") if component else None
        selected[key] = deepcopy(component["equipment"]) if component else None
        if component:
            selected_members[stored_kind] = component["id"]
    return {"parameters": parameters, "selected_equipment": selected, "selected_members": selected_members,
            "equipment_setup": {"id": setup.id, "revision": setup.revision, "name": setup.name,
                                "notes": setup.notes, "components": components}, "equipment_snapshots": registry}


def freeze_equipment_application(session: Session, equipment: EquipmentApplication) -> dict:
    """Resolve a checked choice once; only the explicitly requested fields apply."""
    choice = equipment.choice.model_dump(mode="json", exclude_unset=True)
    source = choice["source"]
    if source == "setup":
        resolved = _setup_snapshot(session, choice, equipment.fields)
        selected_parameters = {}
    else:
        if "optical_accessory" in equipment.fields and "optical_accessory_id" not in choice:
            raise invalid_reference("Provide optical_accessory_id explicitly; null means no accessory.")
        resolved = {"parameters": {}, "selected_equipment": {}, "equipment_snapshots": {}}
        selected_parameters = {}
        for field, stored in (("camera", "camera"), ("telescope", "optical_system"), ("filter", "filter"), ("mount", "mount")):
            if field not in equipment.fields and not (field == "telescope" and "optical_accessory" in equipment.fields):
                continue
            if field not in choice:
                raise invalid_reference(f"An explicit {field} selection is required for this field.")
            selection = choice[field]
            key = stored + "_id"
            if selection is None:
                if field != "mount":
                    resolved["parameters"][key] = None
                resolved["selected_equipment"][key] = None
                continue
            row = session.get(Equipment, selection["equipment_id"])
            _revision(row, selection["expected_revision"])
            if row.kind != field:
                raise invalid_reference(f"The selected {field} has the wrong equipment type.")
            frozen = snapshot_equipment(session, row.id).model_dump(mode="json", exclude_unset=True)
            frozen["revision"] = row.revision
            if field == "telescope":
                frozen.update(resolve_optics("telescope", row.specs, choice.get("optical_accessory_id")))
            if field != "mount":
                resolved["parameters"][key] = row.id
            resolved["selected_equipment"][key] = frozen
            resolved["equipment_snapshots"][row.id] = deepcopy(frozen)
    source_parameters = resolved.get("parameters", {})
    selected = resolved.get("selected_equipment", {})
    applied_parameters = dict(selected_parameters)
    applied_snapshots = {}
    for field, stored in (("camera", "camera"), ("telescope", "optical_system"), ("filter", "filter"), ("mount", "mount")):
        if field in equipment.fields:
            key = stored + "_id"
            if field != "mount":
                applied_parameters[key] = source_parameters.get(key)
            applied_snapshots[key] = deepcopy(selected.get(key))
            if field == "telescope" and "optical_accessory" not in equipment.fields and applied_snapshots[key] is not None:
                applied_snapshots[key].update(resolve_optics("telescope", applied_snapshots[key]["specs"], None))
    if "optical_accessory" in equipment.fields:
        frozen = selected.get("optical_system_id")
        if frozen is None:
            raise invalid_reference("An optical accessory selection requires a telescope.")
        applied_snapshots["optical_system_id"] = deepcopy(frozen)
    resolved["parameters"] = applied_parameters
    resolved["selected_equipment"] = applied_snapshots
    # Keep the full frozen setup context for provenance, while limiting application.
    return ImportDefaultsSnapshot.model_validate(resolved).model_dump(mode="json", exclude_unset=True)


def freeze_import_equipment(session: Session, equipment: EquipmentApplication, explicit_parameters: dict) -> dict:
    if "optical_accessory" in equipment.fields and "telescope" not in equipment.fields:
        raise invalid_reference("A new image requires an explicit telescope selection when applying an accessory.")
    frozen = freeze_equipment_application(session, equipment)
    frozen["parameters"] = {**frozen.get("parameters", {}), **explicit_parameters}
    for key in ("camera_id", "optical_system_id", "filter_id"):
        if key not in explicit_parameters:
            continue
        identity = explicit_parameters[key]
        if identity is None:
            frozen.setdefault("selected_equipment", {})[key] = None
        elif (frozen.get("selected_equipment", {}).get(key) or {}).get("id") != str(identity):
            raise invalid_reference("Explicit equipment parameters conflict with the confirmed equipment choice.")
    return ImportDefaultsSnapshot.model_validate(frozen).model_dump(mode="json", exclude_unset=True)


def merge_image_metadata(previous: dict, changes: dict) -> dict:
    merged = deepcopy(previous)
    for key in ("target_name", "times"):
        if key in changes:
            merged[key] = ({**merged.get("times", {}), **changes[key]} if key == "times" else changes[key])
    return ImageMetadata.model_validate_json(json.dumps(merged)).model_dump(mode="json", exclude_unset=True)


def record_import_image_metadata(session: Session, asset_id: str, metadata: dict,
                                 equipment_snapshot: dict | None = None, *, value_sources: dict | None = None,
                                 freeze_capture: bool = False) -> None:
    row = session.get(ImageMetadataState, str(asset_id))
    if row is None:
        row = ImageMetadataState(asset_id=str(asset_id), metadata_json={})
        session.add(row)
    row.metadata_json = merge_image_metadata(row.metadata_json or {}, metadata)
    row.target_name = row.metadata_json.get("target_name")
    times = row.metadata_json.get("times", {})
    for slot, column in (("capture_start", "capture_start_utc"), ("capture_end", "capture_end_utc"),
                         ("master_created_at", "master_created_utc")):
        value = (times.get(slot) or {}).get("utc")
        setattr(row, column, datetime.fromisoformat(value) if value else None)
    if equipment_snapshot is not None:
        row.equipment_context = deepcopy(equipment_snapshot)
    asset = session.get(Asset, str(asset_id))
    sources = dict(asset.value_sources or {})
    changed = (["target_name"] if "target_name" in metadata else []) + [
        f"times.{slot}" for slot in metadata.get("times", {})]
    for field in changed:
        source = (value_sources or {}).get(field, "manual")
        if source not in {"manual", "file", "unknown"}:
            raise invalid_reference("Image metadata value sources must identify their real origin.")
        sources[field] = source
    asset.value_sources = sources
    if freeze_capture:
        version = session.get(AssetVersion, asset.current_version_id)
        if asset.revision != 1 or version is None or (version.capture_snapshot or {}).get("image_metadata") is not None:
            raise ApiError(409, "SNAPSHOT_ALREADY_FIXED", "Image capture metadata can only be fixed during its initial registration.")
        snapshot = deepcopy(version.capture_snapshot or {})
        snapshot["image_metadata"] = deepcopy(row.metadata_json)
        if "import_provenance" in snapshot:
            snapshot["import_provenance"]["value_sources"] = deepcopy(sources)
        version.capture_snapshot = snapshot
    session.flush()


def get_master_declaration(session: Session, asset_version_id: str) -> dict:
    row = session.scalar(select(MasterProvenanceRevision).where(
        MasterProvenanceRevision.asset_version_id == str(asset_version_id)).order_by(MasterProvenanceRevision.revision.desc()).limit(1))
    return deepcopy(row.data) if row else {}
