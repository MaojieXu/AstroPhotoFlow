"""Describe capture differences without rejecting user-authored groups."""

from decimal import Decimal

from sqlalchemy import select

from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.datasets.models import DatasetMember
from astrophotoflow.modules.data.library.layout import CAPTURE_FIELDS, capture_identity


def capture_diagnostics(session, asset_ids: list[str]) -> dict:
    equipment_fields = {'camera', 'optical_system', 'filter'}
    columns = [getattr(Asset, field + '_id' if field in equipment_fields else field) for field in CAPTURE_FIELDS]
    rows = session.execute(
        select(Asset.id, *columns, Asset.value_sources, Asset.equipment_snapshot, Asset.scientific_metadata)
        .where(Asset.id.in_(asset_ids))
    )
    assets = {asset.id: asset for asset in rows}
    profiles = [(identity, capture_identity(assets[identity])) for identity in asset_ids if identity in assets]
    warnings, unknown_counts = [], {}
    for field in CAPTURE_FIELDS:
        values = [{"asset_id": identity, "value": profile[field]} for identity, profile in profiles]
        known = [
            item
            for item in values
            if item["value"] is not None
            and not (isinstance(item["value"], dict) and item["value"].get("id") is None and item["value"].get("name") is None)
        ]
        unknown_counts[field] = len(values) - len(known)
        distinct = {str(item["value"]) for item in known}
        differs = len(distinct) > 1
        if field == "sensor_temperature_c" and known:
            temperatures = [Decimal(str(item["value"])) for item in known]
            differs = max(temperatures) - min(temperatures) > Decimal(1)
        if differs:
            warnings.append({"code": "CAPTURE_PARAMETER_DIFFERENCE", "field": field, "severity": "warning", "members": values})
    return {"warnings": warnings, "unknown_counts": unknown_counts}


def dataset_capture_diagnostics(session, dataset_id: str) -> dict:
    identities = session.scalars(
        select(DatasetMember.asset_id).where(DatasetMember.dataset_id == dataset_id).order_by(DatasetMember.position)
    ).all()
    return capture_diagnostics(session, list(identities))


def validate_capture_consistency(session, asset_ids: list[str]) -> dict:
    return capture_diagnostics(session, asset_ids)


def validate_containing_datasets(session, asset_ids: list[str]) -> None:
    from astrophotoflow.modules.data.datasets.dependencies import validate_asset_dependencies

    validate_asset_dependencies(session, asset_ids)
