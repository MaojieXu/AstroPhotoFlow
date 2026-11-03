from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from astrophotoflow.contracts.datasets import (
    DatasetCreate,
    DatasetMemberParametersUpdate,
    DatasetMemberParametersUpdateOut,
    DatasetMembersCreate,
    DatasetOut,
    DatasetPatch,
    DatasetVersionOut,
)
from astrophotoflow.contracts.metadata import AssetClassification, AssetParametersPatch
from astrophotoflow.core.errors import ApiError, invalid_reference, not_found
from astrophotoflow.modules.data.assets.mapping import asset_out
from astrophotoflow.modules.data.assets.metadata import (
    asset_classification,
    asset_parameters,
    set_asset_classification,
    set_asset_parameters,
)
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion
from astrophotoflow.modules.data.assets.references import asset_version_scope
from astrophotoflow.modules.data.datasets.bindings import default_bindings, member_bindings, set_default_bindings, set_member_bindings
from astrophotoflow.modules.data.datasets.calibration import validate_bindings, validate_consumer_slots
from astrophotoflow.modules.data.datasets.mapping import dataset_out, dataset_version_out
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember, DatasetVersion
from astrophotoflow.modules.data.equipment.models import Equipment
from astrophotoflow.modules.data.equipment.references import validate_equipment_reference
from astrophotoflow.modules.data.equipment.snapshots import snapshot_equipment
from astrophotoflow.modules.data.imports.models import AssetTaskItem
from astrophotoflow.modules.data.names import named_changes


def publish_dataset_members(session, dataset: Dataset, submitted_ids: list[str], relative_paths: dict[str, str | None] | None=None, calibration_defaults: dict | None=None, member_overrides: dict[str, dict] | None=None) -> DatasetVersion:
    if len(set(submitted_ids)) != len(submitted_ids):
        raise ApiError(422, 'VALIDATION_ERROR', '数据集成员不能重复。', [{'path': 'asset_version_ids', 'message': '成员版本 ID 不能重复。'}], message_key='dataset_members_must_not_be_duplicated', field_message_keys={'asset_version_ids': 'field_member_duplicate'})
    existing = []
    if dataset.current_version_id:
        existing = session.scalars(select(DatasetMember).where(DatasetMember.dataset_version_id == dataset.current_version_id).order_by(DatasetMember.position)).all()
    old_ids = [member.asset_version_id for member in existing]
    submitted_old = [value for value in submitted_ids if value in set(old_ids)]
    retained_old = [value for value in old_ids if value in set(submitted_ids)]
    if retained_old != submitted_old:
        raise ApiError(422, 'VALIDATION_ERROR', '已有成员必须保留原有相对顺序，新成员只能追加。', [{'path': 'asset_version_ids', 'message': '不得重排已有成员。'}], message_key='retained_members_must_keep_their_relative_order_new_members_may_only_be_app', field_message_keys={'asset_version_ids': 'field_member_order'})
    additions = [value for value in submitted_ids if value not in set(old_ids)]
    if submitted_ids != retained_old + additions:
        raise ApiError(422, 'VALIDATION_ERROR', '新成员必须追加到保留成员之后。', [{'path': 'asset_version_ids', 'message': '新成员只能追加。'}], message_key='new_members_must_follow_the_retained_members', field_message_keys={'asset_version_ids': 'field_member_append'})
    for version_id in additions:
        asset, _ = asset_version_scope(session, None, UUID(version_id))
        if asset.scope != 'shared':
            raise invalid_reference('共享数据集只能包含共享资产。', message_key='shared_datasets_may_contain_only_shared_assets')
    previous_version = session.get(DatasetVersion, dataset.current_version_id) if dataset.current_version_id else None
    previous_defaults = default_bindings(previous_version) if previous_version else {}
    defaults = dict(previous_defaults) if calibration_defaults is None else calibration_defaults
    retained_overrides = {member.asset_version_id: dict(member_bindings(member)) for member in existing}
    overrides = member_overrides or {}
    if set(overrides) - set(submitted_ids):
        raise invalid_reference('成员校准覆盖必须属于本次完整成员列表。', message_key='member_calibration_overrides_must_belong_to_the_full_member_list_in_this_re')
    validate_bindings(session, defaults, previous_defaults)
    for version_id, bindings in overrides.items():
        validate_bindings(session, bindings, retained_overrides.get(version_id, {}))
    next_overrides = {version_id: overrides.get(version_id, retained_overrides.get(version_id, {})) for version_id in submitted_ids}
    validate_consumer_slots(session, submitted_ids, defaults, next_overrides)
    if previous_version and submitted_ids == old_ids and (defaults == previous_defaults) and (next_overrides == retained_overrides):
        return previous_version
    latest_number = session.scalar(select(func.max(DatasetVersion.version_number)).where(DatasetVersion.dataset_id == dataset.id)) or 0
    version = DatasetVersion(id=str(uuid4()), dataset_id=dataset.id, version_number=latest_number + 1)
    set_default_bindings(version, defaults)
    session.add(version)
    session.flush()
    path_map = relative_paths or {}
    retained = {member.asset_version_id: member.relative_path for member in existing}
    for position, asset_version_id in enumerate(submitted_ids):
        relative = retained.get(asset_version_id) if asset_version_id in retained else path_map.get(asset_version_id)
        member = DatasetMember(id=str(uuid4()), dataset_version_id=version.id, asset_version_id=asset_version_id, position=position, relative_path=relative)
        set_member_bindings(member, next_overrides[asset_version_id])
        session.add(member)
    dataset.current_version_id = version.id
    dataset.revision += 1
    dataset.updated_at = datetime.now(UTC)
    session.flush()
    return version

def create_dataset(session: Session, body: DatasetCreate) -> DatasetOut:
    dataset = Dataset(id=str(uuid4()), name=body.name, notes=body.notes, status='active', revision=1)
    session.add(dataset)
    session.flush()
    publish_dataset_members(session, dataset, [str(value) for value in body.asset_version_ids])
    dataset.revision = 1
    session.flush()
    return dataset_out(session, dataset)



def update_dataset(session: Session, dataset_id: UUID, body: DatasetPatch) -> DatasetOut:
    dataset_id_text = str(dataset_id)
    changes = body.model_dump(exclude_unset=True, exclude={'base_revision'})
    fields = [name for name in ("name", "status") if name in changes and changes[name] is None]
    if fields:
        raise ApiError(422, "VALIDATION_ERROR", "These dataset fields cannot be null.",
                       [{"path": field, "message": "Cannot be null."} for field in fields],
                       message_key="invalid_request_fields", field_message_keys={field: "field_not_nullable" for field in fields})
    result = session.execute(update(Dataset).where(Dataset.id == dataset_id_text, Dataset.revision == body.base_revision).values(**named_changes(changes), revision=body.base_revision + 1, updated_at=datetime.now(UTC)))
    if result.rowcount != 1:
        if session.get(Dataset, dataset_id_text) is None:
            raise not_found()
        raise ApiError(409, "REVISION_CONFLICT", "The dataset changed in another window.",
                       message_key="another_window_changed_the_configuration_read_it_again_before_saving")
    session.flush()
    session.expire_all()
    return dataset_out(session, session.get(Dataset, dataset_id_text))



def update_dataset_member_parameters(session: Session, dataset_id: UUID, body: DatasetMemberParametersUpdate) -> DatasetMemberParametersUpdateOut:
    dataset = session.get(Dataset, str(dataset_id))
    if dataset is None:
        raise not_found()
    if dataset.revision != body.base_revision or dataset.current_version_id != str(body.base_version_id):
        raise ApiError(409, 'REVISION_CONFLICT', '数据集成员已变化，请重新读取后保存。', message_key='dataset_membership_has_changed_read_it_again_before_saving')
    members = session.scalars(select(DatasetMember).where(DatasetMember.dataset_version_id == dataset.current_version_id).order_by(DatasetMember.position)).all()
    asset_by_id = {}
    for member in members:
        version = session.get(AssetVersion, member.asset_version_id)
        if version is None:
            raise ApiError(409, 'REVISION_CONFLICT', '数据集成员版本已变化，请重新读取后保存。', message_key='dataset_member_versions_have_changed_read_them_again_before_saving')
        asset_by_id[version.asset_id] = session.get(Asset, version.asset_id)
    submitted = {str(item.asset_id): item.revision for item in body.members}
    if set(submitted) != set(asset_by_id):
        raise ApiError(409, 'REVISION_CONFLICT', '数据集成员已变化，请重新读取后保存。', message_key='dataset_membership_has_changed_read_it_again_before_saving')
    for asset_id, asset in asset_by_id.items():
        if asset is None or asset.revision != submitted[asset_id]:
            raise ApiError(409, 'REVISION_CONFLICT', '素材资料已变化，请重新读取后保存。', message_key='asset_metadata_has_changed_read_it_again_before_saving')
    parameter_patch = body.parameters.model_dump(exclude_unset=True, mode='json') if body.parameters is not None else {}
    classification_patch = body.classification.model_dump(exclude_unset=True, mode='json') if body.classification is not None else {}
    updated = []
    for asset_id, asset in asset_by_id.items():
        if parameter_patch:
            values = dict(asset_parameters(asset) or {})
            previous_values = dict(values)
            values.update(parameter_patch)
            try:
                set_asset_parameters(asset, AssetParametersPatch.model_validate(values))
            except Exception as exc:
                raise ApiError(422, 'VALIDATION_ERROR', '拍摄参数无效。', [{'path': 'parameters', 'message': '请检查参数值及设备 ID。'}], message_key='invalid_capture_parameters', field_message_keys={'parameters': 'field_capture_parameters'}) from exc
            equipment_snapshot = dict(asset.equipment_snapshot or {})
            for key, kind in (('camera_id', 'camera'), ('optical_system_id', 'optical_system'), ('filter_id', 'filter')):
                if key not in parameter_patch:
                    continue
                equipment_id = asset_parameters(asset).get(key)
                if equipment_id is None:
                    equipment_snapshot.pop(key, None)
                else:
                    current_snapshot = equipment_snapshot.get(key)
                    if session.get(Equipment, str(equipment_id)) is None and str(equipment_id) == str(previous_values.get(key)) and current_snapshot and (current_snapshot.get('id') == str(equipment_id)):
                        continue
                    validate_equipment_reference(session, equipment_id, kind, f'parameters.{key}')
                    equipment_snapshot[key] = snapshot_equipment(session, str(equipment_id)).model_dump(mode='json', exclude_unset=True)
            asset.equipment_snapshot = equipment_snapshot
        if classification_patch:
            classification = {**(asset_classification(asset) or {}), **classification_patch}
            if classification.get('frame_class') == 'video':
                classification['frame_type'] = None
            try:
                set_asset_classification(asset, AssetClassification.model_validate(classification))
            except Exception as exc:
                raise ApiError(422, 'VALIDATION_ERROR', '素材分类无效。', [{'path': 'classification', 'message': '请检查素材形态与帧用途。'}], message_key='invalid_asset_classification', field_message_keys={'classification': 'field_asset_classification'}) from exc
            asset.role = 'calibration' if asset_classification(asset).get('frame_type') in {'bias', 'dark', 'flat', 'dark_flat'} else 'raw'
        asset.value_sources = {**(asset.value_sources or {}), **{key: 'manual' for key in parameter_patch}, **{f'classification.{key}': 'manual' for key in classification_patch}}
        asset.revision += 1
        asset.updated_at = datetime.now(UTC)
        updated.append(asset_out(session, asset))
    return DatasetMemberParametersUpdateOut.model_validate({'dataset_id': UUID(dataset.id), 'revision': dataset.revision, 'version_id': UUID(dataset.current_version_id), 'assets': updated})

def publish_dataset_version(session: Session, dataset_id: UUID, body: DatasetMembersCreate) -> DatasetVersionOut:
    dataset_id_text = str(dataset_id)
    dataset = session.get(Dataset, dataset_id_text)
    if dataset is None:
        raise not_found()
    if dataset.revision != body.base_revision:
        raise ApiError(409, 'REVISION_CONFLICT', '数据集已在其他窗口修改，请重新读取后保存。', message_key='another_window_changed_the_dataset_read_it_again_before_saving')
    ids = [str(value) for value in body.asset_version_ids]
    relative_paths = {}
    if ids:
        source_rows = session.execute(select(AssetTaskItem.asset_version_id, AssetTaskItem.source_path).where(AssetTaskItem.asset_version_id.in_(ids)).order_by(AssetTaskItem.created_at, AssetTaskItem.id)).all()
        for version_id, source_path in source_rows:
            relative_paths.setdefault(version_id, source_path)
    maps = body.model_dump(mode='json', exclude_unset=True)
    version = publish_dataset_members(session, dataset, ids, relative_paths, calibration_defaults=maps.get('calibration_defaults'), member_overrides=maps.get('member_calibration_overrides'))
    return dataset_version_out(session, version)
