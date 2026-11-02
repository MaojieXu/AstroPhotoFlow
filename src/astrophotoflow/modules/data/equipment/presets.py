"""Setup-owned exposure presets with one optional filter selection."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from astrophotoflow.contracts.setups import CapturePresetCreate, CapturePresetOut, CapturePresetPage, CapturePresetPatch, CapturePresetQuery
from astrophotoflow.core.errors import ApiError, invalid_reference, not_found
from astrophotoflow.modules.data.equipment.members import member_kind
from astrophotoflow.modules.data.equipment.models import (
    CapturePreset,
    CapturePresetSelection,
    Equipment,
    EquipmentSetup,
    EquipmentSetupMember,
)
from astrophotoflow.modules.data.equipment.optics import validate_setup_members
from astrophotoflow.modules.data.names import named_changes


def effective_preset_parameters(parameters: dict) -> dict:
    """Keep inactive numbers in the draft, but never apply them to new inputs."""
    mode = parameters.get("parameter_mode")
    inactive = ({"gain", "offset"} if mode == "iso" else {"iso"} if mode == "gain" else {"iso", "gain", "offset"})
    return {key: value for key, value in parameters.items() if key not in inactive}


def preset_out(row: CapturePreset) -> CapturePresetOut:
    return CapturePresetOut(id=UUID(row.id), equipment_setup_id=UUID(row.equipment_setup_id), name=row.name,
                            parameters=row.parameters,
                            equipment_selection={choice.kind: choice.member_id for choice in row.choices},
                            status=row.status, revision=row.revision,
                            created_at=row.created_at.replace(tzinfo=UTC) if row.created_at.tzinfo is None else row.created_at,
                            updated_at=row.updated_at.replace(tzinfo=UTC) if row.updated_at.tzinfo is None else row.updated_at)


def selected_filter(session: Session, setup: EquipmentSetup, choices: list) -> EquipmentSetupMember | None:
    candidates = [member for member in setup.members if member_kind(session, member) == "filter"]
    choice = next((choice for choice in choices if choice.kind == "filter"), None)
    if choice is None:
        return candidates[0] if candidates else None
    if choice.member_id is None:
        return None
    member = next((member for member in candidates if member.id == choice.member_id), None)
    if member is None:
        raise invalid_reference("Select a filter member of the preset's own setup.")
    return member


def generated_preset_name(session: Session, setup: EquipmentSetup, row: CapturePreset) -> str:
    parts = []
    member = selected_filter(session, setup, row.choices)
    if member is not None:
        equipment = session.get(Equipment, member.equipment_id) if member.equipment_id else None
        parts.append(equipment.name if equipment is not None else member.inline_equipment["name"])
    values = effective_preset_parameters(row.parameters)
    for key, unit in (("exposure_seconds", "s"), ("sensor_temperature_c", "°C")):
        if values.get(key) is not None:
            parts.append(f"{values[key]:g} {unit}")
    mode = values.get("parameter_mode")
    if mode == "iso":
        parts.append(f"ISO {values['iso']:g}" if values.get("iso") is not None else "ISO")
    elif mode == "gain":
        parts.append(f"Gain {values['gain']:g}" if values.get("gain") is not None else "Gain")
        if values.get("offset") is not None:
            parts.append(f"Offset {values['offset']:g}")
    elif mode == "standard":
        parts.append("Standard")
    return setup.name + (" [" + " · ".join(parts) + "]" if parts else "")


def _set_choices(session: Session, row: CapturePreset, selections: dict) -> None:
    for kind, identity in selections.items():
        if kind != "filter":
            raise invalid_reference("A preset may only override its filter.")
        if identity is not None:
            member = session.get(EquipmentSetupMember, str(identity))
            if member is None or member.setup_id != row.equipment_setup_id or member_kind(session, member) != "filter":
                raise invalid_reference("Select a filter member of this setup.")
    current = {choice.kind: choice for choice in row.choices}
    choices = []
    for kind, identity in selections.items():
        choice = current.get(kind)
        if choice is None:
            choice = CapturePresetSelection(preset_id=row.id, setup_id=row.equipment_setup_id, kind=kind)
        choice.member_id = str(identity) if identity is not None else None
        choices.append(choice)
    row.choices = choices


def clear_member_selections(session: Session, identities: set[str]) -> None:
    """A deleted effective filter becomes explicit non-use, never another filter."""
    if not identities:
        return
    setup_ids = set(session.scalars(select(EquipmentSetupMember.setup_id).where(EquipmentSetupMember.id.in_(identities))))
    for preset in session.scalars(select(CapturePreset).where(CapturePreset.equipment_setup_id.in_(setup_ids))):
        setup = session.get(EquipmentSetup, preset.equipment_setup_id)
        chosen = selected_filter(session, setup, preset.choices)
        if chosen is None or chosen.id not in identities:
            continue
        _set_choices(session, preset, {"filter": None})
        preset.name = generated_preset_name(session, setup, preset)
        preset.revision += 1
        preset.updated_at = datetime.now(UTC)
    session.flush()


def create_capture_preset(session: Session, setup_id: UUID, body: CapturePresetCreate) -> CapturePresetOut:
    setup = session.get(EquipmentSetup, str(setup_id))
    if setup is None:
        raise not_found()
    validate_setup_members(session, setup)
    now = datetime.now(UTC)
    row = CapturePreset(id=str(uuid4()), equipment_setup_id=str(setup_id), name=setup.name,
                        parameters=body.parameters.model_dump(mode="json", exclude_unset=True),
                        status="active", revision=1, created_at=now, updated_at=now)
    session.add(row)
    _set_choices(session, row, body.equipment_selection.model_dump(exclude_unset=True))
    row.name = generated_preset_name(session, setup, row)
    session.flush()
    return preset_out(row)


def get_capture_preset(session: Session, preset_id: UUID) -> CapturePresetOut:
    row = session.get(CapturePreset, str(preset_id))
    if row is None:
        raise not_found()
    return preset_out(row)


def update_capture_preset(session: Session, preset_id: UUID, body: CapturePresetPatch) -> CapturePresetOut:
    row = session.get(CapturePreset, str(preset_id))
    if row is None:
        raise not_found()
    setup = session.get(EquipmentSetup, row.equipment_setup_id)
    validate_setup_members(session, setup)
    fields = [key for key in ("status", "parameters", "equipment_selection") if key in body.model_fields_set and getattr(body, key) is None]
    if fields:
        raise ApiError(422, "VALIDATION_ERROR", "These preset fields cannot be null.",
                       [{"path": key, "message": "Cannot be null."} for key in fields],
                       message_key="invalid_request_fields", field_message_keys={key: "field_not_nullable" for key in fields})
    changes = body.model_dump(mode="json", exclude_unset=True, exclude={"base_revision", "equipment_selection"})
    if "parameters" in changes:
        changes["parameters"] = {**row.parameters, **changes["parameters"]}
    changed = session.execute(update(CapturePreset).where(CapturePreset.id == row.id, CapturePreset.revision == body.base_revision)
                              .values(**named_changes(changes), revision=body.base_revision + 1, updated_at=datetime.now(UTC)))
    if changed.rowcount != 1:
        raise ApiError(409, "REVISION_CONFLICT", "The preset changed in another window.",
                       message_key="another_window_changed_the_configuration_read_it_again_before_saving")
    if "equipment_selection" in body.model_fields_set:
        _set_choices(session, row, body.equipment_selection.model_dump(exclude_unset=True))
    row.name = generated_preset_name(session, setup, row)
    session.flush()
    session.refresh(row)
    return preset_out(row)


def list_capture_presets(session: Session, query: CapturePresetQuery) -> CapturePresetPage:
    filters = [] if query.status == "all" else [CapturePreset.status == query.status]
    if query.equipment_setup_id is not None:
        if session.get(EquipmentSetup, str(query.equipment_setup_id)) is None:
            raise not_found()
        filters.append(CapturePreset.equipment_setup_id == str(query.equipment_setup_id))
    if query.q:
        filters.append(CapturePreset.name_search_key.contains(query.q.casefold(), autoescape=True))
    total = session.scalar(select(func.count()).select_from(CapturePreset).where(*filters)) or 0
    column = CapturePreset.name_search_key if query.sort_by == "name" else CapturePreset.created_at
    ordering = column.desc() if query.order == "desc" else column.asc()
    rows = session.scalars(select(CapturePreset).where(*filters).order_by(ordering, CapturePreset.id.asc())
                           .limit(query.limit).offset(query.offset))
    return CapturePresetPage(items=[preset_out(row) for row in rows], total=total, limit=query.limit, offset=query.offset)
