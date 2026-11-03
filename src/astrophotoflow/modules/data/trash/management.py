from __future__ import annotations

import hashlib
import json
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from astrophotoflow.contracts.trash import (
    EquipmentDelete,
    EquipmentDeleteSelection,
    ManagementTrashDelete,
    ManagementTrashDeleteOut,
    ManagementTrashDependencyOut,
    ManagementTrashItemOut,
    ManagementTrashPage,
    ManagementTrashPreviewOut,
    ManagementTrashSelection,
)
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.modules.data import common as shared
from astrophotoflow.modules.data.assets.metadata import asset_parameters
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion
from astrophotoflow.modules.data.datasets.models import Dataset
from astrophotoflow.modules.data.equipment.models import (
    Equipment,
    EquipmentSetup,
    EquipmentSetupMember,
)
from astrophotoflow.modules.data.projects.models import Project, ProjectAssetReference, ProjectDatasetReference

_MODELS = {"project": Project, "equipment": Equipment, "equipment_setup": EquipmentSetup}


def _item(entry_type: str, row) -> ManagementTrashItemOut:
    if entry_type == "project":
        details = {"target_name": row.target_name, "notes": row.notes}
    elif entry_type == "equipment":
        details = {"kind": row.kind, "model": row.model,
                   "notes": row.notes, "specs": row.specs}
    elif entry_type == "equipment_setup":
        details = {"notes": row.notes, "component_count": len(row.members)}
    return ManagementTrashItemOut(entry_type=entry_type, id=UUID(row.id), name=row.name,
                                  revision=row.revision, updated_at=shared.utc_datetime(row.updated_at), details=details)


def _resolve_selection(session, body, expected_status: str | None):
    seen = set()
    resolved = []
    for item in body.items:
        key = (item.entry_type, str(item.id))
        if key in seen:
            raise ApiError(422, "VALIDATION_ERROR", "所选列表包含重复记录。", message_key='the_selection_contains_duplicate_records')
        seen.add(key)
        model = _MODELS[item.entry_type]
        row = session.get(model, key[1])
        if row is None:
            raise not_found()
        if (expected_status is not None and row.status != expected_status) or row.revision != item.revision:
            raise ApiError(409, "REVISION_CONFLICT", "记录已变化，请重新读取后重试。", message_key='the_record_has_changed_read_it_again_before_retrying')
        resolved.append((item.entry_type, row))
    return resolved


def _dependency(entry_type: str, row, kind: str, name: str, count: int, blocks: bool, references: list[str] | None = None):
    return ManagementTrashDependencyOut(entry_type=entry_type, id=UUID(row.id), kind=kind,
                                        name=name, count=count, blocks_delete=blocks,
                                        references=sorted(references or [], key=str.casefold))


def _equipment_snapshot(row: Equipment) -> dict:
    return {"id": row.id, "kind": row.kind, "name": row.name, "model": row.model,
            **({} if row.kind == "mount" else {"specs": row.specs or {}}), "notes": row.notes}


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
                AssetVersion.camera_id == row.id, AssetVersion.optical_system_id == row.id, AssetVersion.filter_id == row.id,
                AssetVersion.capture_snapshot["equipment_snapshot"]["mount_id"]["id"].as_string() == row.id))).all())
            setups = session.scalars(select(EquipmentSetup).join(EquipmentSetupMember)
                                     .where(EquipmentSetupMember.equipment_id == row.id).distinct()).all()
            material_assets = session.scalars(select(Asset).where(or_(
                Asset.camera_id == row.id,
                Asset.optical_system_id == row.id,
                Asset.filter_id == row.id,
                Asset.equipment_snapshot["mount_id"]["id"].as_string() == row.id))).all()
            material_by_id={asset.id:asset.name for asset in material_assets}
            dependency_revisions.extend(("asset", asset.id, asset.revision) for asset in material_assets)
            dependency_revisions.extend(("equipment_setup", setup.id, setup.revision) for setup in setups)
            for asset_id in version_asset_ids:
                asset=session.get(Asset,asset_id)
                if asset is not None:material_by_id.setdefault(asset.id,asset.name)
            if material_by_id:
                dependencies.append(_dependency(entry_type, row, "materials", "素材记录中的设备快照（保留）", len(material_by_id), False, list(material_by_id.values())))
            if setups:
                dependencies.append(_dependency(entry_type, row, "equipment_setups", "设备组合中的关联（移除）", len(setups), False, [setup.name for setup in setups]))
    fingerprint_data = {
        "items": sorted((item.entry_type, str(item.id), item.revision) for item in body.items),
        "dependencies": sorted((item.entry_type, str(item.id), item.kind, item.count, item.blocks_delete, item.references) for item in dependencies),
    }
    if direct:
        fingerprint_data["dependency_revisions"] = sorted(dependency_revisions)
    fingerprint = hashlib.sha256(json.dumps(fingerprint_data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return resolved, detail, dependencies, fingerprint


def list_management_trash(session: Session, limit: int = 50, offset: int = 0, q: str | None = None):
    entries = []
    for entry_type, model in _MODELS.items():
        for row in session.scalars(select(model).where(model.status == "archived")).all():
            if q and q.casefold() not in row.name.casefold():
                continue
            entries.append(_item(entry_type, row))
    entries.sort(key=lambda item: (item.updated_at, item.entry_type, str(item.id)), reverse=True)
    return ManagementTrashPage(items=entries[offset:offset + limit], total=len(entries), limit=limit, offset=offset)


def archive_management_entries(body: ManagementTrashSelection, session: Session):
    resolved = _resolve_selection(session, body, "active")
    for item, (_, row) in zip(body.items, resolved):
        shared.update_record(session, _MODELS[item.entry_type], row.id, item.revision, {"status": "archived"})
    session.flush()
    return {"archived_count": len(resolved)}


def restore_management_entries(body: ManagementTrashSelection, session: Session):
    resolved = _resolve_selection(session, body, "archived")
    for item, (_, row) in zip(body.items, resolved):
        shared.update_record(session, _MODELS[item.entry_type], row.id, item.revision, {"status": "active"})
    session.flush()
    return {"restored_count": len(resolved)}


def preview_management_delete(body: ManagementTrashSelection, session: Session):
    _, items, dependencies, fingerprint = _preview(session, body)
    return ManagementTrashPreviewOut(items=items, dependencies=dependencies,
                                     blocked=any(item.blocks_delete for item in dependencies),
                                     preview_fingerprint=fingerprint)


def delete_management_entries(body: ManagementTrashDelete, session: Session):
    resolved, _, dependencies, fingerprint = _preview(session, body)
    if fingerprint != body.preview_fingerprint:
        raise ApiError(409, "PREVIEW_STALE", "引用状态已变化，请重新预览永久删除。", message_key='references_have_changed_preview_permanent_deletion_again')
    if any(item.blocks_delete for item in dependencies):
        raise ApiError(409, "REFERENCES_EXIST", "部分设置仍有项目内素材，请先处理引用。",
                       [{"path": item.kind, "message": f"{item.name}：{item.count} 项"} for item in dependencies if item.blocks_delete], message_key='some_settings_still_have_project_assets_resolve_their_references_first')
    return _delete_entries(session, resolved)


def _delete_entries(session, resolved, *, direct: bool = False):
    detached_material_count = 0
    deleted_count = len(resolved)
    for entry_type, row in resolved:
        if entry_type == "equipment":
            snapshot = _equipment_snapshot(row)
            assets = session.scalars(select(Asset).where(or_(
                Asset.camera_id == row.id,
                Asset.optical_system_id == row.id,
                Asset.filter_id == row.id))).all()
            for asset in assets:
                equipment = dict(asset.equipment_snapshot or {})
                for key in ("camera_id", "optical_system_id", "filter_id"):
                    if (asset_parameters(asset) or {}).get(key) == row.id and (equipment.get(key) or {}).get("id") != row.id:
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
            for setup in session.scalars(select(EquipmentSetup).join(EquipmentSetupMember)
                                          .where(EquipmentSetupMember.equipment_id == row.id).distinct()).all():
                setup.members = [member for member in setup.members if member.equipment_id != row.id]
                setup.revision += 1
                setup.updated_at = shared.now_utc()
            # Members and version links must be removed before deleting the
            # registry row; these are separate ORM ownership relationships.
            session.flush()
        session.delete(row)
    session.flush()
    return ManagementTrashDeleteOut(deleted_count=deleted_count, detached_material_count=detached_material_count)


def preview_equipment_delete(body: EquipmentDeleteSelection, session: Session):
    _, items, dependencies, fingerprint = _preview(session, body, direct=True)
    return ManagementTrashPreviewOut(items=items, dependencies=dependencies, blocked=False,
                                     preview_fingerprint=fingerprint)


def delete_equipment_entries(body: EquipmentDelete, session: Session):
    resolved, _, _, fingerprint = _preview(session, body, direct=True)
    if fingerprint != body.preview_fingerprint:
        raise ApiError(409, "PREVIEW_STALE", "关联记录已变化，请重新查看删除影响。", message_key='linked_records_have_changed_review_deletion_impact_again')
    return _delete_entries(session, resolved, direct=True)
