from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID
from fastapi import Request
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from .errors import ApiError, invalid_reference, not_found
from .models import Asset, AssetVersion, CaptureProfile, Dataset, DatasetMember, DatasetVersion, Equipment, FitsHduMetadata, Preview, Project, ProjectAssetReference, ProjectCaptureProfile, ProjectDatasetReference
from .schemas import AssetOut, AssetVersionOut, CaptureProfileOut, EquipmentOut, ProjectAssetReferenceOut, ProjectOut, FitsHduOut
from pathlib import Path
from fastapi.responses import Response


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _id(value: UUID | str) -> str:
    return str(value)


def _uuid(value: str | None) -> UUID | None:
    return UUID(value) if value is not None else None


def _page(items, total: int, limit: int, offset: int) -> dict:
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def _order(column, order: str):
    return column.desc() if order == "desc" else column.asc()


def _status_clause(model, status: str):
    return None if status == "all" else model.status == status


def _check_names(values: list[UUID]) -> list[str]:
    ids = [str(value) for value in values]
    if len(ids) != len(set(ids)):
        raise ApiError(422, "VALIDATION_ERROR", "关联 ID 不能重复。", [{"path": "capture_profile_ids", "message": "关联 ID 不能重复。"}])
    return ids


def _check_profile_refs(session: Session, ids: list[str]) -> None:
    if ids and len(session.scalars(select(CaptureProfile.id).where(CaptureProfile.id.in_(ids))).all()) != len(ids):
        raise invalid_reference("一个或多个拍摄配置不存在。")


def _check_equipment_ref(session: Session, value: str | None, kind: str, path: str) -> None:
    if value is None:
        return
    equipment = session.get(Equipment, value)
    if equipment is None or equipment.kind != kind:
        raise invalid_reference(f"{path} 必须引用现存的 {kind} 设备。")


def _check_profile_equipment(session: Session, camera_id: str, optical_id: str | None, filter_id: str | None) -> None:
    _check_equipment_ref(session, camera_id, "camera", "camera_id")
    _check_equipment_ref(session, optical_id, "optical_system", "optical_system_id")
    _check_equipment_ref(session, filter_id, "filter", "filter_id")


def _project_out(session: Session, row: Project) -> dict:
    ids = session.scalars(
        select(ProjectCaptureProfile.capture_profile_id)
        .where(ProjectCaptureProfile.project_id == row.id)
        .order_by(ProjectCaptureProfile.capture_profile_id)
    ).all()
    return ProjectOut(
        id=UUID(row.id), name=row.name, target_name=row.target_name, notes=row.notes,
        capture_profile_ids=[UUID(value) for value in ids], status=row.status, revision=row.revision,
        created_at=_utc(row.created_at), updated_at=_utc(row.updated_at),
    ).model_dump()


def _equipment_out(row: Equipment) -> dict:
    return EquipmentOut(
        id=UUID(row.id), kind=row.kind, name=row.name, model=row.model, serial_number=row.serial_number,
        notes=row.notes, specs=row.specs, status=row.status, revision=row.revision,
        created_at=_utc(row.created_at), updated_at=_utc(row.updated_at),
    ).model_dump()


def _profile_out(row: CaptureProfile) -> dict:
    return CaptureProfileOut(
        id=UUID(row.id), name=row.name, camera_id=UUID(row.camera_id),
        optical_system_id=_uuid(row.optical_system_id), filter_id=_uuid(row.filter_id),
        frame_type=row.frame_type, parameter_mode=row.parameter_mode, iso=row.iso,
        exposure_seconds=row.exposure_seconds, gain=row.gain, offset=row.offset,
        sensor_temperature_c=row.sensor_temperature_c, binning_x=row.binning_x, binning_y=row.binning_y,
        notes=row.notes, status=row.status, revision=row.revision, created_at=_utc(row.created_at), updated_at=_utc(row.updated_at),
    ).model_dump()


def _version_out(row: AssetVersion) -> dict:
    return AssetVersionOut(
        id=UUID(row.id), asset_id=UUID(row.asset_id), version_number=row.version_number,
        storage_mode=row.storage_mode, storage_location=row.storage_location, byte_size=row.byte_size,
        content_hash=row.content_hash, availability=row.availability, camera_id=_uuid(row.camera_id),
        optical_system_id=_uuid(row.optical_system_id), filter_id=_uuid(row.filter_id),
        capture_profile_id=_uuid(row.capture_profile_id), frame_type=row.frame_type,
        calibration_level=row.calibration_level, capture_snapshot=row.capture_snapshot,
        scientific_metadata=row.scientific_metadata, created_at=_utc(row.created_at),
    ).model_dump()


def _current_calibration_level(classification: dict | None, role: str) -> str | None:
    if role != "calibration" or not classification:
        return None
    if classification.get("frame_class") == "masterframe":
        return "master"
    if classification.get("frame_class") == "subframe":
        return "individual"
    return None


def _asset_out(session: Session, row: Asset) -> dict:
    version = None
    if row.current_version_id is not None:
        version_row = session.get(AssetVersion, row.current_version_id)
        if version_row is None or version_row.asset_id != row.id:
            raise RuntimeError("资产当前版本引用不属于该资产。")
        version = _version_out(version_row)
    return AssetOut(
        id=UUID(row.id), name=row.name, scope=row.scope, owner_project_id=_uuid(row.owner_project_id),
        role=row.role, current_version_id=_uuid(row.current_version_id), created_at=_utc(row.created_at),
        classification=row.classification, parameters=row.parameters or {}, value_sources=row.value_sources or {},
        notes=row.notes, status=row.status, revision=row.revision,
        calibration_level=_current_calibration_level(row.classification, row.role),
        current_version=version,
    ).model_dump()


def _reference_out(session: Session, ref: ProjectAssetReference, asset: Asset, version: AssetVersion) -> dict:
    return ProjectAssetReferenceOut(
        id=UUID(ref.id), project_id=UUID(ref.project_id), asset_version_id=UUID(ref.asset_version_id),
        added_at=_utc(ref.added_at), asset=_asset_out(session, asset), version=_version_out(version),
    ).model_dump()


def _conflict_or_missing(session: Session, model, record_id: str) -> None:
    if session.get(model, record_id) is None:
        raise not_found()
    raise ApiError(409, "REVISION_CONFLICT", "配置已被其他窗口修改，请重新读取后保存。")


def _assert_patch_values(changes: dict, non_nullable: set[str], path_prefix: str = "") -> None:
    fields = [{"path": f"{path_prefix}{key}", "message": "此字段不能为 null。"} for key in non_nullable if key in changes and changes[key] is None]
    if fields:
        raise ApiError(422, "VALIDATION_ERROR", "请求字段无效。", fields)


def _update_config(session: Session, model, record_id: str, base_revision: int, changes: dict) -> None:
    now = _now()
    result = session.execute(
        update(model).where(model.id == record_id, model.revision == base_revision)
        .values(**changes, revision=base_revision + 1, updated_at=now)
    )
    if result.rowcount != 1:
        _conflict_or_missing(session, model, record_id)


def _asset_version_scope(session, project_id: UUID | None, version_id: UUID):
    version = session.get(AssetVersion, _id(version_id))
    if version is None:
        raise not_found()
    asset = session.get(Asset, version.asset_id)
    if asset is None:
        raise not_found()
    if project_id is None and asset.scope != "shared":
        raise not_found()
    if project_id is not None and asset.scope != "shared" and not (
        asset.scope == "project" and asset.owner_project_id == _id(project_id)
    ):
        raise not_found()
    return asset, version


def _header_out(version: AssetVersion, hdu: FitsHduMetadata) -> dict:
    cards = [{"keyword": card["keyword"], "value": card.get("value"), "comment": card.get("comment")} for card in hdu.header_cards]
    return {"asset_version_id": UUID(version.id), "hdu_index": hdu.hdu_index, "cards": cards}


def _fits_hdu_out(row: FitsHduMetadata) -> dict:
    return FitsHduOut(
        id=UUID(row.id), asset_version_id=UUID(row.asset_version_id), hdu_index=row.hdu_index,
        name=row.name, hdu_type=row.hdu_type, shape=row.shape, bitpix=row.bitpix,
        pixel_type=row.pixel_type, bscale=row.bscale, bzero=row.bzero, bunit=row.bunit,
        parser_version=row.parser_version, supported_kind=row.supported_kind,
        is_selected=row.is_selected, parse_error=row.parse_error,
    ).model_dump()


def _read_preview(request: Request, version_id: str, hdu_index: int | None, size: str) -> Response:
    if size != "thumbnail" or hdu_index is None:
        raise not_found()
    with request.app.state.database.read_session() as session:
        preview = session.scalar(select(Preview).where(
            Preview.asset_version_id == version_id, Preview.hdu_index == hdu_index,
            Preview.size == size, Preview.status == "available",
        ).order_by(Preview.created_at.desc()).limit(1))
        if preview is None:
            raise not_found()
        relative = Path(preview.storage_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise not_found()
        root = request.app.state.settings.data_dir.resolve()
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
            content = path.read_bytes()
        except (OSError, ValueError) as exc:
            raise not_found() from exc
        return Response(content, media_type=preview.mime_type, headers={"Cache-Control": "private, max-age=0"})


def _dataset_out(session, row: Dataset) -> dict:
    member_count = 0
    if row.current_version_id:
        member_count = session.scalar(select(func.count()).select_from(DatasetMember).where(
            DatasetMember.dataset_version_id == row.current_version_id
        )) or 0
    return {
        "id": UUID(row.id), "name": row.name, "notes": row.notes, "status": row.status,
        "revision": row.revision, "current_version_id": UUID(row.current_version_id) if row.current_version_id else None,
        "member_count": member_count,
        "created_at": _utc(row.created_at), "updated_at": _utc(row.updated_at),
    }


def _dataset_version_out(session, row: DatasetVersion) -> dict:
    members = session.scalars(
        select(DatasetMember).where(DatasetMember.dataset_version_id == row.id).order_by(DatasetMember.position)
    ).all()
    result = []
    for member in members:
        version = session.get(AssetVersion, member.asset_version_id)
        asset = session.get(Asset, version.asset_id) if version else None
        if asset is not None and version is not None:
            result.append({
                "id": UUID(member.id), "dataset_version_id": UUID(row.id), "asset_version_id": UUID(version.id),
                "position": member.position, "relative_path": member.relative_path,
                "calibration_overrides": member.calibration_overrides,
                "asset": _asset_out(session, asset), "version": _version_out(version),
            })
    return {
        "id": UUID(row.id), "dataset_id": UUID(row.dataset_id), "version_number": row.version_number,
        "created_at": _utc(row.created_at), "members": result,
        "calibration_defaults": row.calibration_defaults,
    }


def _dataset_reference_out(session, row: ProjectDatasetReference) -> dict:
    dataset = session.get(Dataset, row.dataset_id)
    version = session.get(DatasetVersion, row.dataset_version_id)
    if dataset is None or version is None or version.dataset_id != dataset.id:
        raise RuntimeError("项目数据集引用指向无效版本。")
    return {
        "id": UUID(row.id), "project_id": UUID(row.project_id), "dataset_id": UUID(row.dataset_id),
        "dataset_version_id": UUID(row.dataset_version_id), "base_revision": row.base_revision,
        "added_at": _utc(row.added_at), "dataset": _dataset_out(session, dataset),
        "version": _dataset_version_out(session, version),
    }
