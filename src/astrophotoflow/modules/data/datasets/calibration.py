from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import or_, select
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
        if target is None or target == previous.get(frame_type):
            continue
        if target['kind'] == 'asset_version':
            version = session.get(AssetVersion, target['id'])
            asset = session.get(Asset, version.asset_id) if version else None
            classification = version_classification(asset, version) if asset and version else {}
            valid = asset is not None and asset.scope == 'shared' and (classification.get('frame_type') == frame_type) and (classification.get('frame_class') == 'masterframe')
        else:
            version = session.get(DatasetVersion, target['id'])
            valid = version is not None and dataset_frame_type(session, version) == frame_type
        if not valid:
            raise invalid_reference(f'{frame_type} 必须引用同用途的固定校准数据集版本或 Master 校准资产版本。', message_key='p0_must_reference_a_fixed_calibration_dataset_version_or_a_master_calibrati', message_params={'p0': frame_type})

def calibration_references(session, asset_version_ids: set[str], dataset_version_ids: set[str], excluded_dataset_ids: set[str] = frozenset(), excluded_member_versions: set[str] = frozenset()) -> list[dict]:
    references = []
    for model, label in ((DatasetCalibration, "组默认"), (MemberCalibration, "成员覆盖")):
        owner = model.dataset_version_id if model is DatasetCalibration else model.member_id
        statement = select(owner.label("owner_id"), model.frame_type, model.asset_version_id, model.target_dataset_version_id,
                           Dataset.name, DatasetVersion.version_number)
        if model is DatasetCalibration:
            statement = statement.join(DatasetVersion, DatasetVersion.id == model.dataset_version_id)
        else:
            statement = statement.join(DatasetMember, DatasetMember.id == model.member_id).join(DatasetVersion, DatasetVersion.id == DatasetMember.dataset_version_id)
            if excluded_member_versions:
                statement = statement.where(DatasetMember.asset_version_id.not_in(excluded_member_versions))
        statement = statement.join(Dataset, Dataset.id == DatasetVersion.dataset_id).where(
            model.disabled.is_(False), or_(model.asset_version_id.in_(asset_version_ids), model.target_dataset_version_id.in_(dataset_version_ids)))
        if excluded_dataset_ids:
            statement = statement.where(Dataset.id.not_in(excluded_dataset_ids))
        for row in session.execute(statement.order_by(owner, model.frame_type)):
            kind = "asset_version" if row.asset_version_id else "dataset_version"
            target_id = row.asset_version_id or row.target_dataset_version_id
            identity = f"calibration:{row.owner_id}:{row.frame_type}:{kind}:{target_id}"
            references.append({"id": uuid5(NAMESPACE_URL, identity), "kind": "calibration",
                               "name": f"{row.name} · {label} {row.frame_type}", "version": row.version_number})
    return references


def protect_calibration_targets(session, asset_version_ids: set[str], dataset_version_ids: set[str], excluded_dataset_ids: set[str]=frozenset(), excluded_member_versions: set[str]=frozenset()) -> None:
    if calibration_references(session, asset_version_ids, dataset_version_ids, excluded_dataset_ids, excluded_member_versions):
        raise ApiError(409, 'CALIBRATION_IN_USE', '仍有图像组版本使用所选校准目标；请先移除引用组，再重试清理校准目标。', message_key='image_group_versions_still_reference_the_selected_calibration_target_remove')

def list_calibration_targets(session: Session, limit: int=50, offset: int=0, frame_type: Literal['bias', 'dark', 'flat', 'dark_flat'] | None=None, q: str | None=None) -> CalibrationTargetPage:
    removals = set(session.execute(select(LibraryEntryRemoval.entry_type, LibraryEntryRemoval.entry_id)).all())
    items = []
    for asset, version in session.execute(select(Asset, AssetVersion).join(AssetVersion, AssetVersion.asset_id == Asset.id).where(Asset.scope == 'shared', Asset.status == 'active')).all():
        classification = version_classification(asset, version)
        kind = classification.get('frame_type')
        if ('asset', asset.id) not in removals and kind in FRAME_TYPES and (classification.get('frame_class') == 'masterframe'):
            items.append({'target': {'kind': 'asset_version', 'id': UUID(version.id)}, 'name': asset.name, 'frame_type': kind, 'version_number': version.version_number, 'member_count': 1})
    for dataset, version in session.execute(select(Dataset, DatasetVersion).join(DatasetVersion, DatasetVersion.dataset_id == Dataset.id).where(Dataset.status == 'active')).all():
        kind = dataset_frame_type(session, version)
        if ('dataset', dataset.id) not in removals and kind:
            count = len(session.scalars(select(DatasetMember.id).where(DatasetMember.dataset_version_id == version.id)).all())
            items.append({'target': {'kind': 'dataset_version', 'id': UUID(version.id)}, 'name': dataset.name, 'frame_type': kind, 'version_number': version.version_number, 'member_count': count})
    items = [item for item in items if (not frame_type or item['frame_type'] == frame_type) and (not q or q.casefold() in item['name'].casefold())]
    items.sort(key=lambda item: (item['name'], item['version_number'], str(item['target']['id'])))
    return CalibrationTargetPage.model_validate({'items': items[offset:offset + limit], 'total': len(items), 'limit': limit, 'offset': offset})
