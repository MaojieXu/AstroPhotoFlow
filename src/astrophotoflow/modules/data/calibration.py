"""Fixed calibration targets and references, without matching or image processing."""
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, Depends
from sqlalchemy import select

from astrophotoflow.modules.data import common as shared
from astrophotoflow.core import http as deps
from astrophotoflow.core.errors import ApiError, invalid_reference
from astrophotoflow.modules.data.models import Asset, AssetVersion, Dataset, DatasetMember, DatasetVersion, LibraryEntryRemoval
from astrophotoflow.contracts.calibration import CalibrationTargetPage


router = APIRouter(prefix="/api/v1", responses=deps.ERROR_RESPONSES)
FRAME_TYPES = {"bias", "dark", "flat", "dark_flat"}


def version_classification(asset: Asset, version: AssetVersion) -> dict:
    if asset.current_version_id == version.id:
        return asset.classification or {}
    return {"frame_type": version.frame_type,
            "frame_class": "masterframe" if version.calibration_level == "master" else "subframe"}


def dataset_frame_type(session, version: DatasetVersion) -> str | None:
    members = session.execute(select(Asset, AssetVersion).join(AssetVersion, AssetVersion.asset_id == Asset.id)
        .join(DatasetMember, DatasetMember.asset_version_id == AssetVersion.id)
        .where(DatasetMember.dataset_version_id == version.id)).all()
    types = {version_classification(asset, asset_version).get("frame_type") for asset, asset_version in members}
    if not members or any(asset.scope != "shared" for asset, _ in members) or len(types) != 1:
        return None
    frame_type = next(iter(types))
    return frame_type if frame_type in FRAME_TYPES else None


def validate_bindings(session, bindings: dict, previous: dict) -> None:
    for frame_type, target in bindings.items():
        if target is None or target == previous.get(frame_type):
            continue
        if target["kind"] == "asset_version":
            version = session.get(AssetVersion, target["id"])
            asset = session.get(Asset, version.asset_id) if version else None
            classification = version_classification(asset, version) if asset and version else {}
            valid = asset is not None and asset.scope == "shared" and classification.get("frame_type") == frame_type and classification.get("frame_class") == "masterframe"
        else:
            version = session.get(DatasetVersion, target["id"])
            valid = version is not None and dataset_frame_type(session, version) == frame_type
        if not valid:
            raise invalid_reference(f"{frame_type} 必须引用同用途的固定校准数据集版本或 Master 校准资产版本。")


def calibration_references(session, asset_version_ids: set[str], dataset_version_ids: set[str],
                           excluded_dataset_ids: set[str] = frozenset(), excluded_member_versions: set[str] = frozenset()) -> list[dict]:
    references = []
    for version, dataset in session.execute(select(DatasetVersion, Dataset).join(Dataset, Dataset.id == DatasetVersion.dataset_id)).all():
        if dataset.id in excluded_dataset_ids:
            continue
        maps = [(version.id, "组默认", version.calibration_defaults)]
        for member in session.scalars(select(DatasetMember).where(DatasetMember.dataset_version_id == version.id)).all():
            if member.asset_version_id not in excluded_member_versions:
                maps.append((member.id, "成员覆盖", member.calibration_overrides))
        for owner_id, label, bindings in maps:
            for frame_type, target in bindings.items():
                if target is None:
                    continue
                target_ids = asset_version_ids if target["kind"] == "asset_version" else dataset_version_ids
                if target["id"] in target_ids:
                    identity = f"calibration:{owner_id}:{frame_type}:{target['kind']}:{target['id']}"
                    references.append({"id": uuid5(NAMESPACE_URL, identity), "kind": "calibration",
                                       "name": f"{dataset.name} · {label} {frame_type}", "version": version.version_number})
    return references


def protect_calibration_targets(session, asset_version_ids: set[str], dataset_version_ids: set[str],
                                excluded_dataset_ids: set[str] = frozenset(), excluded_member_versions: set[str] = frozenset()) -> None:
    if calibration_references(session, asset_version_ids, dataset_version_ids, excluded_dataset_ids, excluded_member_versions):
        raise ApiError(409, "CALIBRATION_IN_USE", "仍有图像组版本使用所选校准目标；请先移除引用组，再重试清理校准目标。")


@router.get("/calibration/targets", response_model=CalibrationTargetPage, dependencies=[Depends(deps.authenticate)])
def list_calibration_targets(session: deps.ReadSession, limit: deps.Limit = 50, offset: deps.Offset = 0,
                             frame_type: Literal["bias", "dark", "flat", "dark_flat"] | None = None, q: str | None = None):
    removals = set(session.execute(select(LibraryEntryRemoval.entry_type, LibraryEntryRemoval.entry_id)).all())
    items = []
    for asset, version in session.execute(select(Asset, AssetVersion).join(AssetVersion, AssetVersion.asset_id == Asset.id)
        .where(Asset.scope == "shared", Asset.status == "active")).all():
        classification = version_classification(asset, version)
        kind = classification.get("frame_type")
        if ("asset", asset.id) not in removals and kind in FRAME_TYPES and classification.get("frame_class") == "masterframe":
            items.append({"target": {"kind": "asset_version", "id": UUID(version.id)}, "name": asset.name,
                          "frame_type": kind, "version_number": version.version_number, "member_count": 1})
    for dataset, version in session.execute(select(Dataset, DatasetVersion).join(DatasetVersion, DatasetVersion.dataset_id == Dataset.id)
        .where(Dataset.status == "active")).all():
        kind = dataset_frame_type(session, version)
        if ("dataset", dataset.id) not in removals and kind:
            count = len(session.scalars(select(DatasetMember.id).where(DatasetMember.dataset_version_id == version.id)).all())
            items.append({"target": {"kind": "dataset_version", "id": UUID(version.id)}, "name": dataset.name,
                          "frame_type": kind, "version_number": version.version_number, "member_count": count})
    items = [item for item in items if (not frame_type or item["frame_type"] == frame_type) and (not q or q.casefold() in item["name"].casefold())]
    items.sort(key=lambda item: (item["name"], item["version_number"], str(item["target"]["id"])))
    return shared._page(items[offset:offset + limit], len(items), limit, offset)
