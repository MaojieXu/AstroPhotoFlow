"""Registered/inline equipment combinations and their owned capture presets."""
from uuid import UUID, uuid4
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from astrophotoflow.modules.data import common as shared
from astrophotoflow.core.http import ERROR_RESPONSES, Limit, Offset, Order, ReadSession, SortBy, StatusFilter, WriteSession, authenticate
from astrophotoflow.core.errors import invalid_reference, not_found
from astrophotoflow.contracts.assets import AssetClassification
from astrophotoflow.modules.data.models import CapturePreset, Equipment, EquipmentSetup
from astrophotoflow.contracts.common import EquipmentKind
from astrophotoflow.contracts.setups import CapturePresetCreate, CapturePresetOut, CapturePresetPage, CapturePresetPatch, EquipmentSetupCreate, EquipmentSetupOut, EquipmentSetupPage, EquipmentSetupPatch


router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)
SetupSortBy = Annotated[Literal["created_at", "name", "camera", "telescope", "mount", "filter", "accessory"], Query()]


def _setup_out(row: EquipmentSetup) -> dict:
    return EquipmentSetupOut(
        id=UUID(row.id), name=row.name, components=row.components, notes=row.notes,
        status=row.status, revision=row.revision,
        created_at=shared._utc(row.created_at), updated_at=shared._utc(row.updated_at),
    ).model_dump()


def _preset_out(row: CapturePreset) -> dict:
    return CapturePresetOut(
        id=UUID(row.id), equipment_setup_id=UUID(row.equipment_setup_id), name=row.name,
        classification=row.classification, parameters=row.parameters, notes=row.notes,
        status=row.status, revision=row.revision,
        created_at=shared._utc(row.created_at), updated_at=shared._utc(row.updated_at),
    ).model_dump(exclude_unset=True)


def _check_components(session, components: list[dict]) -> None:
    for component in components:
        if component["source"] == "registered" and session.get(Equipment, component["equipment_id"]) is None:
            raise invalid_reference("使用组合必须引用现存的注册设备。", message_key='the_equipment_setup_must_reference_existing_registered_equipment')


@router.get("/equipment-setups", response_model=EquipmentSetupPage, dependencies=[Depends(authenticate)])
def list_setups(session: ReadSession, limit: Limit = 50, offset: Offset = 0,
                sort_by: SetupSortBy = "created_at", order: Order = "desc", q: str | None = None,
                status: StatusFilter = "active", component_kind: EquipmentKind | None = None):
    filters = [] if status == "all" else [EquipmentSetup.status == status]
    if q:
        filters.append(EquipmentSetup.name.contains(q, autoescape=True))
    column = EquipmentSetup.name if sort_by == "name" else EquipmentSetup.created_at
    statement = select(EquipmentSetup).where(*filters).order_by(shared._order(column, order), EquipmentSetup.id.asc())
    if component_kind is None and sort_by in {"created_at", "name"}:
        total = session.scalar(select(func.count()).select_from(EquipmentSetup).where(*filters)) or 0
        rows = session.scalars(statement.limit(limit).offset(offset)).all()
        return shared._page([_setup_out(row) for row in rows], total, limit, offset)
    rows = session.scalars(statement).all()
    registered_ids = {component["equipment_id"] for row in rows for component in (row.components or [])
                      if component.get("source") == "registered"}
    equipment = {item.id: (item.kind, item.name) for item in session.scalars(
        select(Equipment).where(Equipment.id.in_(registered_ids))
    ).all()} if registered_ids else {}
    components: dict[str, list[tuple[str, str]]] = {}
    for row in rows:
        labels = []
        for component in row.components or []:
            if component["source"] == "inline":
                labels.append((component["equipment"]["kind"], component["equipment"]["name"]))
            elif component["equipment_id"] in equipment:
                labels.append(equipment[component["equipment_id"]])
        components[row.id] = labels
    if component_kind is not None:
        rows = [row for row in rows if any(kind == component_kind for kind, _ in components[row.id])]
    if sort_by not in {"created_at", "name"}:
        names = {
            row.id: " / ".join(name for kind, name in components[row.id]
                              if kind == sort_by or (sort_by == "telescope" and kind == "optical_system")).casefold()
            for row in rows
        }
        rows = sorted(rows, key=lambda row: (row.name.casefold(), row.id))
        populated = sorted((row for row in rows if names[row.id]),
                           key=lambda row: names[row.id], reverse=order == "desc")
        rows = populated + [row for row in rows if not names[row.id]]
    return shared._page([_setup_out(row) for row in rows[offset:offset + limit]], len(rows), limit, offset)


@router.post("/equipment-setups", response_model=EquipmentSetupOut, status_code=201, dependencies=[Depends(authenticate)])
def create_setup(body: EquipmentSetupCreate, session: WriteSession):
    components = [component.model_dump(mode="json") for component in body.components]
    _check_components(session, components)
    row = EquipmentSetup(id=str(uuid4()), name=body.name, components=components, notes=body.notes,
                         status="active", revision=1, created_at=shared._now(), updated_at=shared._now())
    session.add(row)
    session.flush()
    return _setup_out(row)


@router.get("/equipment-setups/{setup_id}", response_model=EquipmentSetupOut, dependencies=[Depends(authenticate)])
def get_setup(setup_id: UUID, session: ReadSession):
    row = session.get(EquipmentSetup, str(setup_id))
    if row is None:
        raise not_found()
    return _setup_out(row)


@router.patch("/equipment-setups/{setup_id}", response_model=EquipmentSetupOut, dependencies=[Depends(authenticate)])
def patch_setup(setup_id: UUID, body: EquipmentSetupPatch, session: WriteSession):
    if session.get(EquipmentSetup, str(setup_id)) is None:
        raise not_found()
    changes = body.model_dump(mode="json", exclude_unset=True, exclude={"base_revision"})
    shared._assert_patch_values(changes, {"name", "components", "status"})
    if "components" in changes:
        _check_components(session, changes["components"])
    shared._update_config(session, EquipmentSetup, str(setup_id), body.base_revision, changes)
    session.flush()
    session.expire_all()
    return _setup_out(session.get(EquipmentSetup, str(setup_id)))


def _preset_page(session, setup_id, limit, offset, sort_by, order, q, status):
    filters = [] if status == "all" else [CapturePreset.status == status]
    if setup_id is not None:
        if session.get(EquipmentSetup, str(setup_id)) is None:
            raise not_found()
        filters.append(CapturePreset.equipment_setup_id == str(setup_id))
    if q:
        filters.append(CapturePreset.name.contains(q, autoescape=True))
    total = session.scalar(select(func.count()).select_from(CapturePreset).where(*filters)) or 0
    column = CapturePreset.name if sort_by == "name" else CapturePreset.created_at
    rows = session.scalars(select(CapturePreset).where(*filters)
        .order_by(shared._order(column, order), CapturePreset.id.asc()).limit(limit).offset(offset)).all()
    return shared._page([_preset_out(row) for row in rows], total, limit, offset)


@router.get("/equipment-setups/{setup_id}/presets", response_model=CapturePresetPage,
            response_model_exclude_unset=True, dependencies=[Depends(authenticate)])
def list_setup_presets(setup_id: UUID, session: ReadSession, limit: Limit = 50, offset: Offset = 0,
                       sort_by: SortBy = "created_at", order: Order = "desc", q: str | None = None,
                       status: StatusFilter = "active"):
    return _preset_page(session, setup_id, limit, offset, sort_by, order, q, status)


@router.get("/capture-presets", response_model=CapturePresetPage,
            response_model_exclude_unset=True, dependencies=[Depends(authenticate)])
def list_presets(session: ReadSession, limit: Limit = 50, offset: Offset = 0,
                 sort_by: SortBy = "created_at", order: Order = "desc", q: str | None = None,
                 status: StatusFilter = "active", equipment_setup_id: UUID | None = None):
    return _preset_page(session, equipment_setup_id, limit, offset, sort_by, order, q, status)


@router.post("/equipment-setups/{setup_id}/presets", response_model=CapturePresetOut, status_code=201,
             response_model_exclude_unset=True, dependencies=[Depends(authenticate)])
def create_preset(setup_id: UUID, body: CapturePresetCreate, session: WriteSession):
    if session.get(EquipmentSetup, str(setup_id)) is None:
        raise not_found()
    parameters = body.parameters.model_dump(mode="json", exclude_unset=True)
    for key, kind in (("camera_id", "camera"), ("optical_system_id", "optical_system"), ("filter_id", "filter")):
        shared._check_equipment_ref(session, parameters.get(key), kind, "parameters." + key)
    row = CapturePreset(id=str(uuid4()), equipment_setup_id=str(setup_id), name=body.name,
                        classification=body.classification.model_dump(mode="json", exclude_unset=True),
                        parameters=parameters, notes=body.notes, status="active", revision=1,
                        created_at=shared._now(), updated_at=shared._now())
    session.add(row)
    session.flush()
    return _preset_out(row)


@router.get("/capture-presets/{preset_id}", response_model=CapturePresetOut,
            response_model_exclude_unset=True, dependencies=[Depends(authenticate)])
def get_preset(preset_id: UUID, session: ReadSession):
    row = session.get(CapturePreset, str(preset_id))
    if row is None:
        raise not_found()
    return _preset_out(row)


@router.patch("/capture-presets/{preset_id}", response_model=CapturePresetOut,
              response_model_exclude_unset=True, dependencies=[Depends(authenticate)])
def patch_preset(preset_id: UUID, body: CapturePresetPatch, session: WriteSession):
    row = session.get(CapturePreset, str(preset_id))
    if row is None:
        raise not_found()
    changes = body.model_dump(mode="json", exclude_unset=True, exclude={"base_revision"})
    shared._assert_patch_values(changes, {"name", "classification", "parameters", "status"})
    if "parameters" in changes:
        changes["parameters"] = {**row.parameters, **changes["parameters"]}
        for key, kind in (("camera_id", "camera"), ("optical_system_id", "optical_system"), ("filter_id", "filter")):
            shared._check_equipment_ref(session, changes["parameters"].get(key), kind, "parameters." + key)
    if "classification" in changes:
        changes["classification"] = {**row.classification, **changes["classification"]}
        if changes["classification"].get("frame_class") == "video":
            changes["classification"]["frame_type"] = None
        changes["classification"] = AssetClassification.model_validate(changes["classification"]).model_dump(exclude_unset=True)
    shared._update_config(session, CapturePreset, str(preset_id), body.base_revision, changes)
    session.flush()
    session.expire_all()
    return _preset_out(session.get(CapturePreset, str(preset_id)))
