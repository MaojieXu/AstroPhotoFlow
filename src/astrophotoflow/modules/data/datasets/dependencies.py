"""Keep current classification and calibration relationships structurally valid."""

from sqlalchemy import select
from sqlalchemy.orm import load_only

from astrophotoflow.core.errors import ApiError
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.calibration.checks import ALLOWED_SLOTS
from astrophotoflow.modules.data.datasets.bindings import dataset_bindings
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetCalibration, DatasetMember


def validate_asset_dependencies(session, asset_ids: list[str]) -> None:
    changed = set(asset_ids)
    issues = []

    def check(consumer_id, consumer_type, bindings):
        for slot, target in bindings.items():
            if not target or target.get("mode") == "unconfigured":
                continue
            master = session.get(Asset, str(target["id"])) if target.get("kind") == "asset" else None
            if (
                slot not in ALLOWED_SLOTS.get(consumer_type, set())
                or master is None
                or master.frame_class != "masterframe"
                or master.frame_type != slot
            ):
                issues.append(
                    {
                        "path": f"{consumer_id}.{slot}",
                        "message": f"Consumer {consumer_id}, slot {slot}, target {target.get('id')}: classification would invalidate this binding.",
                    }
                )

    dataset_ids = set(session.scalars(select(DatasetMember.dataset_id).where(DatasetMember.asset_id.in_(changed))))
    dataset_ids.update(session.scalars(select(DatasetCalibration.dataset_id).where(DatasetCalibration.asset_id.in_(changed))))
    for identity in dataset_ids:
        dataset = session.get(Dataset, identity)
        purposes = session.scalars(
            select(Asset.frame_type)
            .join(DatasetMember, DatasetMember.asset_id == Asset.id)
            .where(DatasetMember.dataset_id == identity)
            .distinct()
        )
        for purpose in purposes:
            check(identity, purpose, dataset_bindings(dataset))
    for asset in session.scalars(
        select(Asset).options(load_only(Asset.id, Asset.frame_class, Asset.frame_type, Asset.calibration, Asset.master_provenance))
    ):
        bindings = asset.calibration or {}
        if asset.id in changed or any(target and str(target.get("id")) in changed for target in bindings.values()):
            check(asset.id, asset.frame_type, bindings)
        applied = ((asset.master_provenance or {}).get("declaration") or {}).get("applied_calibrations") or {}
        if asset.id in changed or any(target and str(target.get("id")) in changed for target in applied.values()):
            check(asset.id, asset.frame_type, applied)
    if issues:
        raise ApiError(
            409, "CALIBRATION_DEPENDENCY_CONFLICT", "Adjust the affected calibration relationships before changing classification.", issues
        )
