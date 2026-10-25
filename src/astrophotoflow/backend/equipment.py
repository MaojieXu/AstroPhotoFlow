from __future__ import annotations
from fastapi import APIRouter

from .dependencies import ERROR_RESPONSES
from .dependencies import Limit, Offset, Order, ReadSession, SortBy, StatusFilter, WriteSession, authenticate
from .common import _assert_patch_values, _equipment_out, _id, _now, _order, _page, _status_clause, _update_config

from typing import Literal
from uuid import UUID, uuid4
from fastapi import Depends
from sqlalchemy import func, or_, select
from .errors import ApiError, not_found
from .models import Equipment
from .schemas import EquipmentCreate, EquipmentOut, EquipmentPage, EquipmentPatch


router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)


@router.get("/equipment", response_model=EquipmentPage, dependencies=[Depends(authenticate)])
def list_equipment(
    session: ReadSession, limit: Limit = 50, offset: Offset = 0,
    sort_by: SortBy = "created_at", order: Order = "desc", q: str | None = None,
    status: StatusFilter = "active", kind: Literal["camera", "optical_system", "filter"] | None = None,
):
    filters = []
    status_clause = _status_clause(Equipment, status)
    if status_clause is not None:
        filters.append(status_clause)
    if kind:
        filters.append(Equipment.kind == kind)
    if q:
        filters.append(or_(Equipment.name.contains(q, autoescape=True), Equipment.model.contains(q, autoescape=True)))
    total = session.scalar(select(func.count()).select_from(Equipment).where(*filters)) or 0
    column = Equipment.name if sort_by == "name" else Equipment.created_at
    rows = session.scalars(select(Equipment).where(*filters).order_by(_order(column, order), Equipment.id.asc()).limit(limit).offset(offset)).all()
    return _page([_equipment_out(row) for row in rows], total, limit, offset)


@router.post("/equipment", response_model=EquipmentOut, status_code=201, dependencies=[Depends(authenticate)])
def create_equipment(body: EquipmentCreate, session: WriteSession):
    now = _now()
    row = Equipment(
        id=str(uuid4()), kind=body.kind, name=body.name, model=body.model, serial_number=body.serial_number,
        notes=body.notes, specs=body.specs.model_dump(mode="json"), status="active", revision=1,
        created_at=now, updated_at=now,
    )
    session.add(row)
    session.flush()
    return _equipment_out(row)


@router.get("/equipment/{equipment_id}", response_model=EquipmentOut, dependencies=[Depends(authenticate)])
def get_equipment(equipment_id: UUID, session: ReadSession):
    row = session.get(Equipment, _id(equipment_id))
    if row is None:
        raise not_found()
    return _equipment_out(row)


@router.patch("/equipment/{equipment_id}", response_model=EquipmentOut, dependencies=[Depends(authenticate)])
def patch_equipment(equipment_id: UUID, body: EquipmentPatch, session: WriteSession):
    row_id = _id(equipment_id)
    row = session.get(Equipment, row_id)
    if row is None:
        raise not_found()
    if body.kind != row.kind:
        raise ApiError(422, "VALIDATION_ERROR", "設備 kind 创建后不能修改。", [{"path": "kind", "message": "必须与现有设备类型一致。"}])
    changes = body.model_dump(exclude_unset=True, exclude={"base_revision", "kind", "specs"})
    _assert_patch_values(changes, {"name", "status"})
    if "specs" in body.model_fields_set:
        if body.specs is None:
            raise ApiError(422, "VALIDATION_ERROR", "specs 不能为 null。", [{"path": "specs", "message": "请提供类型化参数对象。"}])
        changes["specs"] = {**row.specs, **body.specs.model_dump(exclude_unset=True)}
    _update_config(session, Equipment, row_id, body.base_revision, changes)
    session.flush()
    session.expire_all()
    return _equipment_out(session.get(Equipment, row_id))
