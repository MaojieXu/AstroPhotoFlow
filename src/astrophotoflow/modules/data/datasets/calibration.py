from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from astrophotoflow.contracts.calibration import CalibrationTargetPage
from astrophotoflow.core.errors import ApiError, invalid_reference, not_found
from astrophotoflow.modules.data.assets.metadata import asset_classification
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetCalibration, DatasetMember
from astrophotoflow.modules.data.trash.models import LibraryEntryRemoval
FRAME_TYPES = {'bias', 'dark', 'flat', 'dark_flat'}

def asset_classification_for_calibration(asset: Asset) -> dict:
    return asset_classification(asset) or {}

def require_subframe(version: Asset) -> None:
    if asset_classification_for_calibration(version).get('frame_class') != 'subframe':
        raise invalid_reference('数据集成员必须是固定的子帧版本。', message_key='dataset_member_requires_subframe')

def validate_dataset_members(session, asset_ids: list[str], dataset_id: str | None = None) -> None:
    from astrophotoflow.modules.data.assets.references import require_referenceable
    for identity in asset_ids:
        require_referenceable(session, 'asset', identity)
    owners = session.execute(select(DatasetMember.asset_id, Dataset.id, Dataset.name).join(
        Dataset, Dataset.id == DatasetMember.dataset_id).where(DatasetMember.asset_id.in_(asset_ids))).all()
    conflicts = [{'path': 'asset_ids.' + identity, 'message': f'Already belongs to dataset {owner_id} ({name}).'}
                 for identity, owner_id, name in owners if owner_id != dataset_id]
    if conflicts:
        raise ApiError(409, 'ASSET_DATASET_OWNERSHIP', 'A material can belong to only one dataset.', conflicts,
                       message_key='asset_dataset_ownership')
    versions = {version.id: version for version in session.scalars(select(Asset).where(Asset.scope == 'shared', Asset.id.in_(asset_ids)))}
    for identity in asset_ids:
        if identity not in versions:
            raise not_found()
        require_subframe(versions[identity])
    from astrophotoflow.modules.data.datasets.consistency import validate_capture_consistency
    validate_capture_consistency(session, asset_ids)

def dataset_frame_type(session, version: Dataset) -> str | None:
    members = session.scalars(select(Asset).join(DatasetMember, DatasetMember.asset_id == Asset.id).where(DatasetMember.dataset_id == version.id)).all()
    types = {asset_classification_for_calibration(version).get('frame_type') for version in members}
    if not members or any((asset.scope != 'shared' for asset in members)) or len(types) != 1:
        return None
    frame_type = next(iter(types))
    return frame_type if frame_type in FRAME_TYPES else None

def validate_bindings(session, bindings: dict, previous: dict) -> None:
    for purpose, target in bindings.items():
        if target is None or target.get('mode') == 'unconfigured':
            continue
        from astrophotoflow.modules.data.assets.references import require_referenceable
        asset = require_referenceable(session, 'asset', target['id']) if target.get('kind') == 'asset' else None
        classification = asset_classification(asset) if asset else {}
        if asset is None or asset.availability != 'available' or asset.scope != 'shared' or classification.get('frame_class') != 'masterframe' or classification.get('frame_type') != purpose:
            raise invalid_reference(f'{purpose} requires an existing Master of the same purpose.')

def validate_consumer_slots(session, asset_ids: list[str], bindings: dict) -> None:
    """Full publication shares purpose rules without requiring science facts."""
    from astrophotoflow.modules.data.calibration.checks import ALLOWED_SLOTS
    if not asset_ids or not any((target is not None and target.get('mode') != 'unconfigured' for target in bindings.values())):
        return
    sources = session.scalars(select(Asset).where(Asset.id.in_(asset_ids)))
    for asset in sources:
        consumer_type = asset_classification_for_calibration(asset).get('frame_type')
        if consumer_type is None:
            continue
        for slot, target in bindings.items():
            if target is None or target.get('mode') == 'unconfigured':
                continue
            if slot not in ALLOWED_SLOTS.get(consumer_type, set()):
                raise invalid_reference(f'{consumer_type} cannot use the {slot} calibration slot.')

def calibration_references(session, asset_ids: set[str], dataset_ids: set[str], excluded_dataset_ids: set[str]=frozenset(), excluded_asset_ids: set[str]=frozenset()) -> list[dict]:
    references = []
    statement = select(DatasetCalibration.dataset_id, DatasetCalibration.frame_type, DatasetCalibration.asset_id, Dataset.name, Dataset.revision).join(Dataset, Dataset.id == DatasetCalibration.dataset_id).where(DatasetCalibration.disabled.is_(False), DatasetCalibration.asset_id.in_(asset_ids))
    if excluded_dataset_ids:
        statement = statement.where(Dataset.id.not_in(excluded_dataset_ids))
    for row in session.execute(statement.order_by(DatasetCalibration.dataset_id, DatasetCalibration.frame_type)):
        identity = f'calibration:{row.dataset_id}:{row.frame_type}:asset:{row.asset_id}'
        references.append({'id': uuid5(NAMESPACE_URL, identity), 'kind': 'calibration', 'name': f'{row.name} · {row.frame_type}'})
    from astrophotoflow.modules.data.assets.image_provenance import master_provenance_references
    from astrophotoflow.modules.data.calibration.service import calibration_references as standalone_references
    references.extend(standalone_references(session, asset_ids, dataset_ids, excluded_asset_ids))
    references.extend(({**reference, 'kind': 'calibration'} for reference in master_provenance_references(session, asset_ids, dataset_ids, excluded_asset_ids)))
    return references

def protect_calibration_targets(session, asset_ids: set[str], dataset_ids: set[str], excluded_dataset_ids: set[str]=frozenset(), excluded_asset_ids: set[str]=frozenset()) -> None:
    if calibration_references(session, asset_ids, dataset_ids, excluded_dataset_ids, excluded_asset_ids):
        raise ApiError(409, 'CALIBRATION_IN_USE', '仍有图像组版本使用所选校准目标；请先移除引用组，再重试清理校准目标。', message_key='image_group_versions_still_reference_the_selected_calibration_target_remove')

def list_calibration_targets(session: Session, limit: int=50, offset: int=0, frame_type: Literal['bias', 'dark', 'flat', 'dark_flat'] | None=None, q: str | None=None) -> CalibrationTargetPage:
    frame = Asset.frame_type
    classification = Asset.frame_class
    removed = select(LibraryEntryRemoval.entry_id).where(LibraryEntryRemoval.entry_type == 'asset', LibraryEntryRemoval.entry_id == Asset.id).exists()
    candidates = select(Asset, frame.label('candidate_frame_type')).where(Asset.scope == 'shared', Asset.status == 'active', ~removed, classification == 'masterframe', frame.in_(FRAME_TYPES))
    if frame_type is not None:
        candidates = candidates.where(frame == frame_type)
    if q:
        candidates = candidates.where(Asset.name_search_key.contains(q.casefold(), autoescape=True))
    total = session.scalar(select(func.count()).select_from(candidates.subquery()))
    rows = session.execute(candidates.order_by(Asset.name, Asset.revision, Asset.id).limit(limit).offset(offset)).all()
    items = [{'target': {'kind': 'asset', 'id': UUID(asset.id)}, 'name': asset.name, 'frame_type': kind, 'member_count': 1} for asset, kind in rows]
    return CalibrationTargetPage.model_validate({'items': items, 'total': total, 'limit': limit, 'offset': offset})
