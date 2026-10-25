from __future__ import annotations
from fastapi import APIRouter

from .dependencies import ERROR_RESPONSES
from .dependencies import Limit, Offset, Order, ReadSession, SortBy, StatusFilter, WriteSession, authenticate
from .common import _assert_patch_values, _check_profile_equipment, _id, _now, _order, _page, _profile_out, _status_clause, _update_config

from typing import Literal
from uuid import UUID, uuid4
from fastapi import Depends
from sqlalchemy import func, select
from .errors import not_found
from .models import CaptureProfile
from .schemas import CaptureProfileCreate, CaptureProfileOut, CaptureProfilePage, CaptureProfilePatch


router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)


@router.get("/capture-profiles", response_model=CaptureProfilePage, dependencies=[Depends(authenticate)])
def list_capture_profiles(
    session: ReadSession, limit: Limit = 50, offset: Offset = 0,
    sort_by: SortBy = "created_at", order: Order = "desc", q: str | None = None,
    status: StatusFilter = "active", camera_id: UUID | None = None, optical_system_id: UUID | None = None,
    filter_id: UUID | None = None, frame_type: Literal["light", "bias", "dark", "flat", "dark_flat"] | None = None,
):
    filters = []
    status_clause = _status_clause(CaptureProfile, status)
    if status_clause is not None:
        filters.append(status_clause)
    for column, value in ((CaptureProfile.camera_id, camera_id), (CaptureProfile.optical_system_id, optical_system_id), (CaptureProfile.filter_id, filter_id), (CaptureProfile.frame_type, frame_type)):
        if value is not None:
            filters.append(column == _id(value) if isinstance(value, UUID) else column == value)
    if q:
        filters.append(CaptureProfile.name.contains(q, autoescape=True))
    total = session.scalar(select(func.count()).select_from(CaptureProfile).where(*filters)) or 0
    column = CaptureProfile.name if sort_by == "name" else CaptureProfile.created_at
    rows = session.scalars(select(CaptureProfile).where(*filters).order_by(_order(column, order), CaptureProfile.id.asc()).limit(limit).offset(offset)).all()
    return _page([_profile_out(row) for row in rows], total, limit, offset)


@router.post("/capture-profiles", response_model=CaptureProfileOut, status_code=201, dependencies=[Depends(authenticate)])
def create_capture_profile(body: CaptureProfileCreate, session: WriteSession):
    camera_id, optical_id, filter_id = _id(body.camera_id), _id(body.optical_system_id) if body.optical_system_id else None, _id(body.filter_id) if body.filter_id else None
    _check_profile_equipment(session, camera_id, optical_id, filter_id)
    now = _now()
    row = CaptureProfile(
        id=str(uuid4()), name=body.name, camera_id=camera_id, optical_system_id=optical_id, filter_id=filter_id,
        frame_type=body.frame_type, parameter_mode=body.parameter_mode, iso=body.iso,
        exposure_seconds=body.exposure_seconds, gain=body.gain, offset=body.offset,
        sensor_temperature_c=body.sensor_temperature_c, binning_x=body.binning_x, binning_y=body.binning_y,
        notes=body.notes, status="active", revision=1, created_at=now, updated_at=now,
    )
    session.add(row)
    session.flush()
    return _profile_out(row)


@router.get("/capture-profiles/{profile_id}", response_model=CaptureProfileOut, dependencies=[Depends(authenticate)])
def get_capture_profile(profile_id: UUID, session: ReadSession):
    row = session.get(CaptureProfile, _id(profile_id))
    if row is None:
        raise not_found()
    return _profile_out(row)


@router.patch("/capture-profiles/{profile_id}", response_model=CaptureProfileOut, dependencies=[Depends(authenticate)])
def patch_capture_profile(profile_id: UUID, body: CaptureProfilePatch, session: WriteSession):
    row_id = _id(profile_id)
    row = session.get(CaptureProfile, row_id)
    if row is None:
        raise not_found()
    changes = body.model_dump(exclude_unset=True, exclude={"base_revision"})
    _assert_patch_values(changes, {"name", "camera_id", "frame_type", "status"})
    for key in ("camera_id", "optical_system_id", "filter_id"):
        if key in changes and changes[key] is not None:
            changes[key] = _id(changes[key])
    camera_id = changes.get("camera_id", row.camera_id)
    optical_id = changes.get("optical_system_id", row.optical_system_id)
    filter_id = changes.get("filter_id", row.filter_id)
    _check_profile_equipment(session, camera_id, optical_id, filter_id)
    _update_config(session, CaptureProfile, row_id, body.base_revision, changes)
    session.flush()
    session.expire_all()
    return _profile_out(session.get(CaptureProfile, row_id))
