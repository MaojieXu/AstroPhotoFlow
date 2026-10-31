from __future__ import annotations
from fastapi import APIRouter

from astrophotoflow.core.http import ERROR_RESPONSES
from astrophotoflow.modules.data.common import _asset_version_scope, _dataset_out, _dataset_version_out
from astrophotoflow.core import http as deps
from astrophotoflow.modules.data import common as shared
from astrophotoflow.modules.data.calibration import validate_bindings

from typing import Literal
from uuid import UUID, uuid4
from fastapi import Depends
from sqlalchemy import func, select, update
from astrophotoflow.core.errors import ApiError, invalid_reference, not_found
from astrophotoflow.modules.data.models import Asset, AssetTaskItem, AssetVersion, Dataset, DatasetMember, DatasetVersion, Equipment
from astrophotoflow.contracts.datasets import DatasetOut, DatasetPage, DatasetVersionOut, DatasetVersionPage, DatasetMemberParametersUpdateOut
from astrophotoflow.contracts.assets import AssetClassification, AssetParameters
from astrophotoflow.contracts.datasets import DatasetCreate, DatasetPatch, DatasetMemberParametersUpdate, DatasetMembersCreate


router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)


def _publish_dataset_version(session, dataset: Dataset, submitted_ids: list[str], relative_paths: dict[str, str | None] | None = None,
                             calibration_defaults: dict | None = None, member_overrides: dict[str, dict] | None = None) -> DatasetVersion:
    if len(set(submitted_ids)) != len(submitted_ids):
        raise ApiError(422, "VALIDATION_ERROR", "数据集成员不能重复。", [{"path": "asset_version_ids", "message": "成员版本 ID 不能重复。"}], message_key='dataset_members_must_not_be_duplicated', field_message_keys={'asset_version_ids': 'field_member_duplicate'})
    existing = []
    if dataset.current_version_id:
        existing = session.scalars(
            select(DatasetMember).where(DatasetMember.dataset_version_id == dataset.current_version_id)
            .order_by(DatasetMember.position)
        ).all()
    old_ids = [member.asset_version_id for member in existing]
    submitted_old = [value for value in submitted_ids if value in set(old_ids)]
    retained_old = [value for value in old_ids if value in set(submitted_ids)]
    if retained_old != submitted_old:
        raise ApiError(422, "VALIDATION_ERROR", "已有成员必须保留原有相对顺序，新成员只能追加。", [{"path": "asset_version_ids", "message": "不得重排已有成员。"}], message_key='retained_members_must_keep_their_relative_order_new_members_may_only_be_app', field_message_keys={'asset_version_ids': 'field_member_order'})
    additions = [value for value in submitted_ids if value not in set(old_ids)]
    if submitted_ids != retained_old + additions:
        raise ApiError(422, "VALIDATION_ERROR", "新成员必须追加到保留成员之后。", [{"path": "asset_version_ids", "message": "新成员只能追加。"}], message_key='new_members_must_follow_the_retained_members', field_message_keys={'asset_version_ids': 'field_member_append'})
    for version_id in additions:
        asset, _ = _asset_version_scope(session, None, UUID(version_id))
        if asset.scope != "shared":
            raise invalid_reference("共享数据集只能包含共享资产。", message_key='shared_datasets_may_contain_only_shared_assets')
    previous_version = session.get(DatasetVersion, dataset.current_version_id) if dataset.current_version_id else None
    previous_defaults = previous_version.calibration_defaults if previous_version else {}
    defaults = dict(previous_defaults) if calibration_defaults is None else calibration_defaults
    retained_overrides = {member.asset_version_id: dict(member.calibration_overrides) for member in existing}
    overrides = member_overrides or {}
    if set(overrides) - set(submitted_ids):
        raise invalid_reference("成员校准覆盖必须属于本次完整成员列表。", message_key='member_calibration_overrides_must_belong_to_the_full_member_list_in_this_re')
    validate_bindings(session, defaults, previous_defaults)
    for version_id, bindings in overrides.items():
        validate_bindings(session, bindings, retained_overrides.get(version_id, {}))
    next_overrides = {version_id: overrides.get(version_id, retained_overrides.get(version_id, {})) for version_id in submitted_ids}
    if previous_version and submitted_ids == old_ids and defaults == previous_defaults and next_overrides == retained_overrides:
        return previous_version
    latest_number = session.scalar(select(func.max(DatasetVersion.version_number)).where(DatasetVersion.dataset_id == dataset.id)) or 0
    version = DatasetVersion(id=str(uuid4()), dataset_id=dataset.id, version_number=latest_number + 1,
                             calibration_defaults=defaults)
    session.add(version)
    session.flush()
    path_map = relative_paths or {}
    retained = {member.asset_version_id: member.relative_path for member in existing}
    for position, asset_version_id in enumerate(submitted_ids):
        relative = retained.get(asset_version_id) if asset_version_id in retained else path_map.get(asset_version_id)
        session.add(DatasetMember(
            id=str(uuid4()), dataset_version_id=version.id, asset_version_id=asset_version_id,
            position=position, relative_path=relative,
            calibration_overrides=next_overrides[asset_version_id],
        ))
    dataset.current_version_id = version.id
    dataset.revision += 1
    dataset.updated_at = shared._now()
    session.flush()
    return version


@router.post("/datasets", response_model=DatasetOut, status_code=201, dependencies=[Depends(deps.authenticate)])
def create_dataset(body: DatasetCreate, session: deps.WriteSession):
    dataset = Dataset(id=str(uuid4()), name=body.name, notes=body.notes, status="active", revision=1)
    session.add(dataset)
    session.flush()
    _publish_dataset_version(session, dataset, [str(value) for value in body.asset_version_ids])
    dataset.revision = 1
    session.flush()
    return _dataset_out(session, dataset)


@router.get("/datasets", response_model=DatasetPage, dependencies=[Depends(deps.authenticate)])
def list_datasets(
    session: deps.ReadSession, limit: deps.Limit = 50, offset: deps.Offset = 0,
    sort_by: deps.SortBy = "created_at", order: deps.Order = "desc", q: str | None = None,
    status: Literal["active", "archived", "all"] = "active",
):
    filters = [] if status == "all" else [Dataset.status == status]
    if q:
        filters.append(Dataset.name.contains(q, autoescape=True))
    total = session.scalar(select(func.count()).select_from(Dataset).where(*filters)) or 0
    column = Dataset.name if sort_by == "name" else Dataset.created_at
    rows = session.scalars(select(Dataset).where(*filters)
        .order_by(column.desc() if order == "desc" else column.asc(), Dataset.id.asc())
        .limit(limit).offset(offset)).all()
    return shared._page([_dataset_out(session, row) for row in rows], total, limit, offset)


@router.get("/datasets/{dataset_id}", response_model=DatasetOut, dependencies=[Depends(deps.authenticate)])
def get_dataset(dataset_id: UUID, session: deps.ReadSession):
    dataset = session.get(Dataset, shared._id(dataset_id))
    if dataset is None:
        raise not_found()
    return _dataset_out(session, dataset)


@router.patch("/datasets/{dataset_id}", response_model=DatasetOut, dependencies=[Depends(deps.authenticate)])
def patch_dataset(dataset_id: UUID, body: DatasetPatch, session: deps.WriteSession):
    dataset_id_text = shared._id(dataset_id)
    changes = body.model_dump(exclude_unset=True, exclude={"base_revision"})
    shared._assert_patch_values(changes, {"name", "status"})
    result = session.execute(update(Dataset).where(
        Dataset.id == dataset_id_text, Dataset.revision == body.base_revision
    ).values(**changes, revision=body.base_revision + 1, updated_at=shared._now()))
    if result.rowcount != 1:
        shared._conflict_or_missing(session, Dataset, dataset_id_text)
    session.flush()
    session.expire_all()
    return _dataset_out(session, session.get(Dataset, dataset_id_text))


@router.get("/datasets/{dataset_id}/versions", response_model=DatasetVersionPage, dependencies=[Depends(deps.authenticate)])
def list_dataset_versions(dataset_id: UUID, session: deps.ReadSession, limit: deps.Limit = 50, offset: deps.Offset = 0):
    dataset = session.get(Dataset, shared._id(dataset_id))
    if dataset is None:
        raise not_found()
    total = session.scalar(select(func.count()).select_from(DatasetVersion).where(DatasetVersion.dataset_id == dataset.id)) or 0
    rows = session.scalars(select(DatasetVersion).where(DatasetVersion.dataset_id == dataset.id)
        .order_by(DatasetVersion.version_number.desc()).limit(limit).offset(offset)).all()
    return shared._page([_dataset_version_out(session, row) for row in rows], total, limit, offset)


@router.get("/datasets/{dataset_id}/versions/{version_id}", response_model=DatasetVersionOut, dependencies=[Depends(deps.authenticate)])
def get_dataset_version(dataset_id: UUID, version_id: UUID, session: deps.ReadSession):
    dataset = session.get(Dataset, shared._id(dataset_id))
    version = session.get(DatasetVersion, shared._id(version_id))
    if dataset is None or version is None or version.dataset_id != dataset.id:
        raise not_found()
    return _dataset_version_out(session, version)


@router.patch("/datasets/{dataset_id}/member-parameters", response_model=DatasetMemberParametersUpdateOut, dependencies=[Depends(deps.authenticate)])
def update_dataset_member_parameters(
    dataset_id: UUID, body: DatasetMemberParametersUpdate, session: deps.WriteSession,
):
    dataset = session.get(Dataset, shared._id(dataset_id))
    if dataset is None:
        raise not_found()
    if dataset.revision != body.base_revision or dataset.current_version_id != shared._id(body.base_version_id):
        raise ApiError(409, "REVISION_CONFLICT", "数据集成员已变化，请重新读取后保存。", message_key='dataset_membership_has_changed_read_it_again_before_saving')
    members = session.scalars(
        select(DatasetMember).where(DatasetMember.dataset_version_id == dataset.current_version_id)
        .order_by(DatasetMember.position)
    ).all()
    asset_by_id = {}
    for member in members:
        version = session.get(AssetVersion, member.asset_version_id)
        if version is None:
            raise ApiError(409, "REVISION_CONFLICT", "数据集成员版本已变化，请重新读取后保存。", message_key='dataset_member_versions_have_changed_read_them_again_before_saving')
        asset_by_id[version.asset_id] = session.get(Asset, version.asset_id)
    submitted = {shared._id(item.asset_id): item.revision for item in body.members}
    if set(submitted) != set(asset_by_id):
        raise ApiError(409, "REVISION_CONFLICT", "数据集成员已变化，请重新读取后保存。", message_key='dataset_membership_has_changed_read_it_again_before_saving')
    for asset_id, asset in asset_by_id.items():
        if asset is None or asset.revision != submitted[asset_id]:
            raise ApiError(409, "REVISION_CONFLICT", "素材资料已变化，请重新读取后保存。", message_key='asset_metadata_has_changed_read_it_again_before_saving')

    parameter_patch = body.parameters.model_dump(exclude_unset=True, mode="json") if body.parameters is not None else {}
    classification_patch = body.classification.model_dump(exclude_unset=True, mode="json") if body.classification is not None else {}
    updated = []
    for asset_id, asset in asset_by_id.items():
        if parameter_patch:
            values = dict(asset.parameters or {})
            previous_values = dict(values)
            values.update(parameter_patch)
            try:
                asset.parameters = AssetParameters.model_validate(values).model_dump(mode="json")
            except Exception as exc:
                raise ApiError(422, "VALIDATION_ERROR", "拍摄参数无效。", [{"path": "parameters", "message": "请检查参数值及设备 ID。"}], message_key='invalid_capture_parameters', field_message_keys={'parameters': 'field_capture_parameters'}) from exc
            equipment_snapshot = dict(asset.equipment_snapshot or {})
            for key, kind in (("camera_id", "camera"), ("optical_system_id", "optical_system"), ("filter_id", "filter")):
                if key not in parameter_patch:
                    continue
                equipment_id = asset.parameters.get(key)
                if equipment_id is None:
                    equipment_snapshot.pop(key, None)
                else:
                    current_snapshot = equipment_snapshot.get(key)
                    if (session.get(Equipment, str(equipment_id)) is None and
                        str(equipment_id) == str(previous_values.get(key)) and current_snapshot and current_snapshot.get("id") == str(equipment_id)):
                        continue
                    shared._check_equipment_ref(session, equipment_id, kind, f"parameters.{key}")
                    equipment_snapshot[key] = shared._equipment_snapshot(session, str(equipment_id))
            asset.equipment_snapshot = equipment_snapshot
        if classification_patch:
            classification = {**(asset.classification or {}), **classification_patch}
            if classification.get("frame_class") == "video":
                classification["frame_type"] = None
            try:
                asset.classification = AssetClassification.model_validate(classification).model_dump(mode="json")
            except Exception as exc:
                raise ApiError(422, "VALIDATION_ERROR", "素材分类无效。", [{"path": "classification", "message": "请检查素材形态与帧用途。"}], message_key='invalid_asset_classification', field_message_keys={'classification': 'field_asset_classification'}) from exc
            asset.role = "calibration" if asset.classification.get("frame_type") in {"bias", "dark", "flat", "dark_flat"} else "raw"
        asset.value_sources = {
            **(asset.value_sources or {}),
            **{key: "manual" for key in parameter_patch},
            **{f"classification.{key}": "manual" for key in classification_patch},
        }
        asset.revision += 1
        asset.updated_at = shared._now()
        updated.append(shared._asset_out(session, asset))
    return {
        "dataset_id": UUID(dataset.id), "revision": dataset.revision,
        "version_id": UUID(dataset.current_version_id), "assets": updated,
    }


@router.post("/datasets/{dataset_id}/versions", response_model=DatasetVersionOut, status_code=201, dependencies=[Depends(deps.authenticate)])
def create_dataset_version(
    dataset_id: UUID, body: DatasetMembersCreate, session: deps.WriteSession,
):
    dataset_id_text = shared._id(dataset_id)
    dataset = session.get(Dataset, dataset_id_text)
    if dataset is None:
        raise not_found()
    if dataset.revision != body.base_revision:
        raise ApiError(409, "REVISION_CONFLICT", "数据集已在其他窗口修改，请重新读取后保存。", message_key='another_window_changed_the_dataset_read_it_again_before_saving')
    ids = [shared._id(value) for value in body.asset_version_ids]
    relative_paths = {}
    if ids:
        source_rows = session.execute(
            select(AssetTaskItem.asset_version_id, AssetTaskItem.source_path)
            .where(AssetTaskItem.asset_version_id.in_(ids))
            .order_by(AssetTaskItem.created_at, AssetTaskItem.id)
        ).all()
        for version_id, source_path in source_rows:
            relative_paths.setdefault(version_id, source_path)
    maps = body.model_dump(mode="json", exclude_unset=True)
    version = _publish_dataset_version(session, dataset, ids, relative_paths,
        calibration_defaults=maps.get("calibration_defaults"), member_overrides=maps.get("member_calibration_overrides"))
    return _dataset_version_out(session, version)
