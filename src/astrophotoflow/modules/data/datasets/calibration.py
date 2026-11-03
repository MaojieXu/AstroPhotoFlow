from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from astrophotoflow.contracts.calibration import CalibrationTargetPage
from astrophotoflow.core.errors import ApiError, invalid_reference
from astrophotoflow.modules.data.assets.metadata import asset_classification
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetCalibration, DatasetMember, DatasetVersion, MemberCalibration
from astrophotoflow.modules.data.trash.models import LibraryEntryRemoval

FRAME_TYPES = {'bias', 'dark', 'flat', 'dark_flat'}

def version_classification(asset: Asset, version: AssetVersion) -> dict:
    if asset.current_version_id == version.id:
        return asset_classification(asset) or {}
    return {'frame_type': version.frame_type, 'frame_class': 'masterframe' if version.calibration_level == 'master' else 'subframe'}

def dataset_frame_type(session, version: DatasetVersion) -> str | None:
    members = session.execute(select(Asset, AssetVersion).join(AssetVersion, AssetVersion.asset_id == Asset.id).join(DatasetMember, DatasetMember.asset_version_id == AssetVersion.id).where(DatasetMember.dataset_version_id == version.id)).all()
    types = {version_classification(asset, asset_version).get('frame_type') for asset, asset_version in members}
    if not members or any((asset.scope != 'shared' for asset, _ in members)) or len(types) != 1:
        return None
    frame_type = next(iter(types))
    return frame_type if frame_type in FRAME_TYPES else None

def validate_bindings(session, bindings: dict, previous: dict) -> None:
    for frame_type, target in bindings.items():
        if target is None or target.get('mode') == 'unconfigured' or target == previous.get(frame_type):
            continue
        version = session.get(AssetVersion, target['id']) if target.get('kind') == 'asset_version' else None
        asset = session.get(Asset, version.asset_id) if version else None
        classification = version_classification(asset, version) if asset and version else {}
        valid = asset is not None and asset.scope == 'shared' and classification.get('frame_type') == frame_type and classification.get('frame_class') == 'masterframe'
        if not valid:
            raise invalid_reference(f'{frame_type} 必须引用同用途的固定 Master 校准资产版本。')

def validate_consumer_slots(session, version_ids: list[str], defaults: dict, overrides: dict) -> None:
    """Full publication shares purpose rules without requiring science facts."""
    from astrophotoflow.modules.data.calibration.checks import ALLOWED_SLOTS

    configured = [defaults, *overrides.values()]
    if not version_ids or not any(target is not None and target.get('mode') != 'unconfigured'
                                 for bindings in configured for target in bindings.values()):
        return
    sources = session.execute(select(Asset, AssetVersion).join(AssetVersion, AssetVersion.asset_id == Asset.id)
        .where(AssetVersion.id.in_(version_ids)))
    for asset, version in sources:
        consumer_type = version_classification(asset, version).get('frame_type')
        if consumer_type is None:
            continue
        effective = {**defaults, **overrides.get(version.id, {})}
        for slot, target in effective.items():
            if target is None or target.get('mode') == 'unconfigured':
                continue
            if slot not in ALLOWED_SLOTS.get(consumer_type, set()):
                raise invalid_reference(f'{consumer_type} cannot use the {slot} calibration slot.')


def calibration_references(session, asset_version_ids: set[str], dataset_version_ids: set[str], excluded_dataset_ids: set[str] = frozenset(), excluded_member_versions: set[str] = frozenset()) -> list[dict]:
    references = []
    for model, label in ((DatasetCalibration, "组默认"), (MemberCalibration, "成员覆盖")):
        owner = model.dataset_version_id if model is DatasetCalibration else model.member_id
        statement = select(owner.label("owner_id"), model.frame_type, model.asset_version_id,
                           Dataset.name, DatasetVersion.version_number)
        if model is DatasetCalibration:
            statement = statement.join(DatasetVersion, DatasetVersion.id == model.dataset_version_id)
        else:
            statement = statement.join(DatasetMember, DatasetMember.id == model.member_id).join(DatasetVersion, DatasetVersion.id == DatasetMember.dataset_version_id)
            if excluded_member_versions:
                statement = statement.where(DatasetMember.asset_version_id.not_in(excluded_member_versions))
        statement = statement.join(Dataset, Dataset.id == DatasetVersion.dataset_id).where(
            model.disabled.is_(False), model.asset_version_id.in_(asset_version_ids))
        if excluded_dataset_ids:
            statement = statement.where(Dataset.id.not_in(excluded_dataset_ids))
        for row in session.execute(statement.order_by(owner, model.frame_type)):
            kind = "asset_version"
            target_id = row.asset_version_id
            identity = f"calibration:{row.owner_id}:{row.frame_type}:{kind}:{target_id}"
            references.append({"id": uuid5(NAMESPACE_URL, identity), "kind": "calibration",
                               "name": f"{row.name} · {label} {row.frame_type}", "version": row.version_number})
    from astrophotoflow.modules.data.assets.image_provenance import master_provenance_references
    from astrophotoflow.modules.data.calibration.service import calibration_references as standalone_references

    references.extend(standalone_references(session, asset_version_ids, dataset_version_ids, excluded_member_versions))
    references.extend({**reference, 'kind': 'calibration'} for reference in
                      master_provenance_references(session, asset_version_ids, dataset_version_ids))
    return references


def protect_calibration_targets(session, asset_version_ids: set[str], dataset_version_ids: set[str], excluded_dataset_ids: set[str]=frozenset(), excluded_member_versions: set[str]=frozenset()) -> None:
    if calibration_references(session, asset_version_ids, dataset_version_ids, excluded_dataset_ids, excluded_member_versions):
        raise ApiError(409, 'CALIBRATION_IN_USE', '仍有图像组版本使用所选校准目标；请先移除引用组，再重试清理校准目标。', message_key='image_group_versions_still_reference_the_selected_calibration_target_remove')

def list_calibration_targets(session: Session, limit: int=50, offset: int=0, frame_type: Literal['bias', 'dark', 'flat', 'dark_flat'] | None=None, q: str | None=None) -> CalibrationTargetPage:
    frame = case((Asset.current_version_id == AssetVersion.id, Asset.frame_type), else_=AssetVersion.frame_type)
    classification = case((Asset.current_version_id == AssetVersion.id, Asset.frame_class),
        else_=case((AssetVersion.calibration_level == 'master', 'masterframe'), else_='subframe'))
    removed = select(LibraryEntryRemoval.entry_id).where(
        LibraryEntryRemoval.entry_type == 'asset', LibraryEntryRemoval.entry_id == Asset.id).exists()
    candidates = select(Asset, AssetVersion, frame.label('candidate_frame_type')).join(
        AssetVersion, AssetVersion.asset_id == Asset.id).where(
            Asset.scope == 'shared', Asset.status == 'active', ~removed,
            classification == 'masterframe', frame.in_(FRAME_TYPES))
    if frame_type is not None:
        candidates = candidates.where(frame == frame_type)
    if q:
        candidates = candidates.where(Asset.name_search_key.contains(q.casefold(), autoescape=True))
    total = session.scalar(select(func.count()).select_from(candidates.subquery()))
    rows = session.execute(candidates.order_by(Asset.name, AssetVersion.version_number, AssetVersion.id)
        .limit(limit).offset(offset)).all()
    items = [{'target': {'kind': 'asset_version', 'id': UUID(version.id)}, 'name': asset.name,
              'frame_type': kind, 'version_number': version.version_number, 'member_count': 1}
             for asset, version, kind in rows]
    return CalibrationTargetPage.model_validate({'items': items, 'total': total, 'limit': limit, 'offset': offset})
