from __future__ import annotations

import hashlib
import json
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select

from astrophotoflow.modules.data import common as shared
from astrophotoflow.core.http import ERROR_RESPONSES, Limit, Offset, ReadSession, WriteSession, authenticate
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.contracts.trash import ManagementTrashDelete, ManagementTrashDeleteOut, ManagementTrashDependencyOut, ManagementTrashItemOut, ManagementTrashPage, ManagementTrashPreviewOut, ManagementTrashSelection
from astrophotoflow.contracts.trash import EquipmentDelete, EquipmentDeleteSelection
from astrophotoflow.modules.data.models import Asset, AssetVersion, CapturePreset, Dataset, Equipment, EquipmentSetup, Project, ProjectAssetReference, ProjectDatasetReference


router = APIRouter(prefix="/api/v1/settings/trash", responses=ERROR_RESPONSES)
equipment_router = APIRouter(prefix="/api/v1/equipment-management", responses=ERROR_RESPONSES)
_MODELS = {"project": Project, "equipment": Equipment, "equipment_setup": EquipmentSetup, "capture_preset": CapturePreset}


def _item(entry_type: str, row) -> ManagementTrashItemOut:
    if entry_type == "project":
        details = {"target_name": row.target_name, "notes": row.notes}
    elif entry_type == "equipment":
        details = {"kind": row.kind, "model": row.model, "serial_number": row.serial_number,
                   "notes": row.notes, "specs": row.specs}
    elif entry_type == "equipment_setup":
        details = {"notes": row.notes, "component_count": len(row.components or [])}
    else:
        details = {"equipment_setup_id": row.equipment_setup_id, "classification": row.classification}
    return ManagementTrashItemOut(entry_type=entry_type, id=UUID(row.id), name=row.name,
                                  revision=row.revision, updated_at=shared._utc(row.updated_at), details=details)


def _resolve_selection(session, body, expected_status: str | None):
    seen = set()
    resolved = []
    for item in body.items:
        key = (item.entry_type, str(item.id))
        if key in seen:
            raise ApiError(422, "VALIDATION_ERROR", "所选列表包含重复记录。")
        seen.add(key)
        model = _MODELS[item.entry_type]
        row = session.get(model, key[1])
        if row is None:
            raise not_found()
        if (expected_status is not None and row.status != expected_status) or row.revision != item.revision:
            raise ApiError(409, "REVISION_CONFLICT", "记录已变化，请重新读取后重试。")
        resolved.append((item.entry_type, row))
    return resolved


def _dependency(entry_type: str, row, kind: str, name: str, count: int, blocks: bool, references: list[str] | None = None):
    return ManagementTrashDependencyOut(entry_type=entry_type, id=UUID(row.id), kind=kind,
                                        name=name, count=count, blocks_delete=blocks,
                                        references=sorted(references or [], key=str.casefold))


def _equipment_snapshot(row: Equipment) -> dict:
    return {"id": row.id, "kind": row.kind, "name": row.name, "model": row.model,
            "serial_number": row.serial_number, "specs": row.specs or {}, "notes": row.notes}


def _preview(session, body, *, direct: bool = False):
    resolved = _resolve_selection(session, body, None if direct else "archived")
    dependencies = []
    detail = []
    dependency_revisions = []
    for entry_type, row in resolved:
        detail.append(_item(entry_type, row))
        if entry_type == "project":
            owned = session.scalars(select(Asset).where(Asset.owner_project_id == row.id)).all()
            assets = session.execute(select(Asset.name).join(AssetVersion, AssetVersion.asset_id == Asset.id)
                .join(ProjectAssetReference, ProjectAssetReference.asset_version_id == AssetVersion.id)
                .where(ProjectAssetReference.project_id == row.id)).all()
            datasets = session.scalars(select(Dataset).join(ProjectDatasetReference, ProjectDatasetReference.dataset_id == Dataset.id)
                .where(ProjectDatasetReference.project_id == row.id)).all()
            if owned:
                dependencies.append(_dependency(entry_type, row, "owned_assets", "项目内素材（永久删除前需移出项目）", len(owned), True, [item.name for item in owned]))
            if assets:
                dependencies.append(_dependency(entry_type, row, "asset_references", "项目单图关联（删除项目时解除关联，素材保留）", len(assets), False, [item.name for item in assets]))
            if datasets:
                dependencies.append(_dependency(entry_type, row, "dataset_references", "项目数据集关联（删除项目时解除关联，数据集保留）", len(datasets), False, [item.name for item in datasets]))
        elif entry_type == "equipment":
            version_asset_ids = set(session.scalars(select(AssetVersion.asset_id).where(or_(
                AssetVersion.camera_id == row.id, AssetVersion.optical_system_id == row.id, AssetVersion.filter_id == row.id))).all())
            setups = [setup for setup in session.scalars(select(EquipmentSetup)).all()
                      if any(component.get("source") == "registered" and component.get("equipment_id") == row.id
                             for component in setup.components or [])]
            presets = [preset for preset in session.scalars(select(CapturePreset)).all()
                       if any(preset.parameters.get(key) == row.id for key in ("camera_id", "optical_system_id", "filter_id"))]
            material_assets = session.scalars(select(Asset).where(or_(
                Asset.parameters["camera_id"].as_string() == row.id,
                Asset.parameters["optical_system_id"].as_string() == row.id,
                Asset.parameters["filter_id"].as_string() == row.id))).all()
            material_by_id={asset.id:asset.name for asset in material_assets}
            dependency_revisions.extend(("asset", asset.id, asset.revision) for asset in material_assets)
            dependency_revisions.extend(("equipment_setup", setup.id, setup.revision) for setup in setups)
            dependency_revisions.extend(("capture_preset", preset.id, preset.revision) for preset in presets)
            for asset_id in version_asset_ids:
                asset=session.get(Asset,asset_id)
                if asset is not None:material_by_id.setdefault(asset.id,asset.name)
            if material_by_id:
                dependencies.append(_dependency(entry_type, row, "materials", "素材记录中的设备快照（保留）", len(material_by_id), False, list(material_by_id.values())))
            if setups:
                dependencies.append(_dependency(entry_type, row, "equipment_setups", "设备组合中的关联（移除）" if direct else "使用组合中的注册设备（转为组合内快照）", len(setups), False, [setup.name for setup in setups]))
            if presets:
                dependencies.append(_dependency(entry_type, row, "capture_presets", "拍摄预设中的设备默认值（清除）" if direct else "拍摄预设中的设备默认值（保留于组合设备快照）", len(presets), False, [preset.name for preset in presets]))
        elif entry_type == "equipment_setup":
            presets = session.scalars(select(CapturePreset).where(CapturePreset.equipment_setup_id == row.id)).all()
            dependency_revisions.extend(("capture_preset", preset.id, preset.revision) for preset in presets)
            if presets:
                dependencies.append(_dependency(entry_type, row, "capture_presets", "组合内拍摄预设（随组合永久删除）", len(presets), False, [preset.name for preset in presets]))
    fingerprint_data = {
        "items": sorted((item.entry_type, str(item.id), item.revision) for item in body.items),
        "dependencies": sorted((item.entry_type, str(item.id), item.kind, item.count, item.blocks_delete, item.references) for item in dependencies),
    }
    if direct:
        fingerprint_data["dependency_revisions"] = sorted(dependency_revisions)
    fingerprint = hashlib.sha256(json.dumps(fingerprint_data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return resolved, detail, dependencies, fingerprint


@router.get("", response_model=ManagementTrashPage, dependencies=[Depends(authenticate)])
def list_management_trash(session: ReadSession, limit: Limit = 50, offset: Offset = 0, q: str | None = None):
    entries = []
    for entry_type, model in _MODELS.items():
        for row in session.scalars(select(model).where(model.status == "archived")).all():
            if q and q.casefold() not in row.name.casefold():
                continue
            entries.append(_item(entry_type, row))
    entries.sort(key=lambda item: (item.updated_at, item.entry_type, str(item.id)), reverse=True)
    return ManagementTrashPage(items=entries[offset:offset + limit], total=len(entries), limit=limit, offset=offset)


@router.post("/archive", dependencies=[Depends(authenticate)])
def archive_management_entries(body: ManagementTrashSelection, session: WriteSession):
    resolved = _resolve_selection(session, body, "active")
    for item, (_, row) in zip(body.items, resolved):
        shared._update_config(session, _MODELS[item.entry_type], row.id, item.revision, {"status": "archived"})
    session.flush()
    return {"archived_count": len(resolved)}


@router.post("/restore", dependencies=[Depends(authenticate)])
def restore_management_entries(body: ManagementTrashSelection, session: WriteSession):
    resolved = _resolve_selection(session, body, "archived")
    for item, (_, row) in zip(body.items, resolved):
        shared._update_config(session, _MODELS[item.entry_type], row.id, item.revision, {"status": "active"})
    session.flush()
    return {"restored_count": len(resolved)}


@router.post("/delete-preview", response_model=ManagementTrashPreviewOut, dependencies=[Depends(authenticate)])
def preview_management_delete(body: ManagementTrashSelection, session: ReadSession):
    _, items, dependencies, fingerprint = _preview(session, body)
    return ManagementTrashPreviewOut(items=items, dependencies=dependencies,
                                     blocked=any(item.blocks_delete for item in dependencies),
                                     preview_fingerprint=fingerprint)


@router.post("/delete", response_model=ManagementTrashDeleteOut, dependencies=[Depends(authenticate)])
def delete_management_entries(body: ManagementTrashDelete, session: WriteSession):
    resolved, _, dependencies, fingerprint = _preview(session, body)
    if fingerprint != body.preview_fingerprint:
        raise ApiError(409, "PREVIEW_STALE", "引用状态已变化，请重新预览永久删除。")
    if any(item.blocks_delete for item in dependencies):
        raise ApiError(409, "REFERENCES_EXIST", "部分设置仍有项目内素材，请先处理引用。",
                       [{"path": item.kind, "message": f"{item.name}：{item.count} 项"} for item in dependencies if item.blocks_delete])
    return _delete_entries(session, resolved)


def _delete_entries(session, resolved, *, direct: bool = False):
    detached_material_count = 0
    deleted_count = len(resolved)
    selected_preset_ids={row.id for entry_type,row in resolved if entry_type=="capture_preset"}
    for entry_type, row in resolved:
        if entry_type == "equipment":
            snapshot = _equipment_snapshot(row)
            assets = session.scalars(select(Asset).where(or_(
                Asset.parameters["camera_id"].as_string() == row.id,
                Asset.parameters["optical_system_id"].as_string() == row.id,
                Asset.parameters["filter_id"].as_string() == row.id))).all()
            for asset in assets:
                equipment = dict(asset.equipment_snapshot or {})
                for key in ("camera_id", "optical_system_id", "filter_id"):
                    if (asset.parameters or {}).get(key) == row.id:
                        if (equipment.get(key) or {}).get("id") != row.id:
                            equipment[key] = snapshot
                asset.equipment_snapshot = equipment
            versions = session.scalars(select(AssetVersion).where(or_(
                AssetVersion.camera_id == row.id, AssetVersion.optical_system_id == row.id, AssetVersion.filter_id == row.id))).all()
            for version in versions:
                capture = dict(version.capture_snapshot or {})
                equipment = dict(capture.get("equipment_snapshot") or {})
                for key, field in (("camera_id", "camera_id"), ("optical_system_id", "optical_system_id"), ("filter_id", "filter_id")):
                    if getattr(version, field) == row.id:
                        if (equipment.get(key) or {}).get("id") != row.id:
                            equipment[key] = snapshot
                        setattr(version, field, None)
                capture["equipment_snapshot"] = equipment
                version.capture_snapshot = capture
            detached_material_count += len(assets)
            for setup in session.scalars(select(EquipmentSetup)).all():
                changed = False
                components = []
                for component in setup.components or []:
                    if component.get("source") == "registered" and component.get("equipment_id") == row.id:
                        if not direct:
                            components.append({"source": "inline", "equipment": {key: snapshot.get(key) for key in
                                              ("kind", "name", "model", "serial_number", "notes", "specs")}})
                        changed = True
                    else:
                        components.append(component)
                if changed:
                    setup.components = components
                    setup.revision += 1
                    setup.updated_at = shared._now()
            for preset in session.scalars(select(CapturePreset)).all():
                parameters = dict(preset.parameters or {})
                changed = False
                for key in ("camera_id", "optical_system_id", "filter_id"):
                    if parameters.get(key) == row.id:
                        parameters[key] = None
                        changed = True
                if changed and not direct:
                    setup = session.get(EquipmentSetup, preset.equipment_setup_id)
                    components = list(setup.components or [])
                    inline_equipment = {key: snapshot.get(key) for key in ("kind", "name", "model", "serial_number", "notes", "specs")}
                    if not any(component.get("source") == "inline" and component.get("equipment") == inline_equipment
                               for component in components):
                        components.append({"source": "inline", "equipment": inline_equipment})
                        setup.components = components
                        setup.revision += 1
                        setup.updated_at = shared._now()
                if changed:
                    preset.parameters = parameters
                    preset.revision += 1
                    preset.updated_at = shared._now()
        elif entry_type == "equipment_setup":
            presets = session.scalars(select(CapturePreset).where(CapturePreset.equipment_setup_id == row.id)).all()
            deleted_count += sum(preset.id not in selected_preset_ids for preset in presets)
            for preset in presets:
                session.delete(preset)
        session.delete(row)
    session.flush()
    return ManagementTrashDeleteOut(deleted_count=deleted_count, detached_material_count=detached_material_count)


@equipment_router.post("/delete-preview", response_model=ManagementTrashPreviewOut, dependencies=[Depends(authenticate)])
def preview_equipment_delete(body: EquipmentDeleteSelection, session: ReadSession):
    _, items, dependencies, fingerprint = _preview(session, body, direct=True)
    return ManagementTrashPreviewOut(items=items, dependencies=dependencies, blocked=False,
                                     preview_fingerprint=fingerprint)


@equipment_router.post("/delete", response_model=ManagementTrashDeleteOut, dependencies=[Depends(authenticate)])
def delete_equipment_entries(body: EquipmentDelete, session: WriteSession):
    resolved, _, _, fingerprint = _preview(session, body, direct=True)
    if fingerprint != body.preview_fingerprint:
        raise ApiError(409, "PREVIEW_STALE", "关联记录已变化，请重新查看删除影响。")
    return _delete_entries(session, resolved, direct=True)
