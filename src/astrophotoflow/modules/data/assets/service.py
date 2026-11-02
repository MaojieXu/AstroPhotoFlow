from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from astrophotoflow.contracts.assets import (
    AssetOut,
    AssetPatch,
    AssetVersionOut,
    AssetVersionPage,
    FitsHduPage,
    FitsHeaderOut,
    PreviewReference,
)
from astrophotoflow.contracts.metadata import AssetClassification, AssetParametersPatch
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.modules.data.assets.mapping import asset_out, asset_version_out, fits_hdu_out, header_out
from astrophotoflow.modules.data.assets.metadata import asset_classification, asset_parameters, classification_columns, parameter_columns
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion, FitsHduMetadata
from astrophotoflow.modules.data.assets.references import asset_version_scope
from astrophotoflow.modules.data.equipment.models import Equipment
from astrophotoflow.modules.data.equipment.references import validate_equipment_reference
from astrophotoflow.modules.data.equipment.snapshots import snapshot_equipment
from astrophotoflow.modules.data.names import named_changes


def get_asset(session: Session, asset_id: UUID) -> AssetOut:
    row = session.get(Asset, str(asset_id))
    if row is None or row.scope != 'shared':
        raise not_found()
    return asset_out(session, row)

def update_asset(session: Session, asset_id: UUID, body: AssetPatch) -> AssetOut:
    asset_id_text = str(asset_id)
    asset = session.get(Asset, asset_id_text)
    if asset is None or asset.scope != 'shared':
        raise not_found()
    changes = body.model_dump(exclude_unset=True, exclude={'base_revision', 'classification', 'parameters'})
    fields = [key for key in ("name", "status") if key in changes and changes[key] is None]
    if fields:
        raise ApiError(422, "VALIDATION_ERROR", "These asset fields cannot be null.",
                       [{"path": key, "message": "Cannot be null."} for key in fields], message_key="invalid_request_fields",
                       field_message_keys={key: "field_not_nullable" for key in fields})
    classification = dict(asset_classification(asset) or {})
    parameters = dict(asset_parameters(asset) or {})
    equipment_snapshot = dict(asset.equipment_snapshot or {})
    value_sources = dict(asset.value_sources or {})
    if body.classification is not None:
        patch = body.classification.model_dump(exclude_unset=True)
        classification.update(patch)
        if classification.get('frame_class') == 'video':
            classification['frame_type'] = None
        try:
            classification = AssetClassification.model_validate(classification).model_dump(mode='json')
        except Exception as exc:
            raise ApiError(422, 'VALIDATION_ERROR', '分类资料无效。', [{'path': 'classification', 'message': '请同时提供有效的素材形态和帧用途。'}], message_key='invalid_classification_metadata', field_message_keys={'classification': 'field_classification_required'}) from exc
        for key in patch:
            value_sources[f'classification.{key}'] = 'manual'
        changes.update(classification_columns(classification))
        changes['role'] = 'calibration' if classification.get('frame_type') in {'bias', 'dark', 'flat', 'dark_flat'} else 'raw'
    if body.parameters is not None:
        patch = body.parameters.model_dump(exclude_unset=True, mode='json')
        parameters.update(patch)
        try:
            parameters = AssetParametersPatch.model_validate(parameters).model_dump(mode='json')
        except Exception as exc:
            raise ApiError(422, 'VALIDATION_ERROR', '拍摄参数无效。', [{'path': 'parameters', 'message': '请检查参数值及设备 ID。'}], message_key='invalid_capture_parameters', field_message_keys={'parameters': 'field_capture_parameters'}) from exc
        for key in patch:
            value_sources[key] = 'manual'
        for key, kind in (('camera_id', 'camera'), ('optical_system_id', 'optical_system'), ('filter_id', 'filter')):
            if key not in patch:
                continue
            equipment_id = parameters.get(key)
            if equipment_id is None:
                equipment_snapshot.pop(key, None)
            else:
                current_snapshot = equipment_snapshot.get(key)
                if session.get(Equipment, str(equipment_id)) is None and str(parameters.get(key)) == str((asset_parameters(asset) or {}).get(key)) and current_snapshot and (current_snapshot.get('id') == str(equipment_id)):
                    continue
                validate_equipment_reference(session, equipment_id, kind, f'parameters.{key}')
                equipment_snapshot[key] = snapshot_equipment(session, str(equipment_id)).model_dump(mode='json', exclude_unset=True)
        changes.update(parameter_columns(parameters))
        changes['equipment_snapshot'] = equipment_snapshot
    if body.classification is not None or body.parameters is not None:
        changes['value_sources'] = value_sources
    result = session.execute(update(Asset).where(Asset.id == asset_id_text, Asset.revision == body.base_revision).values(**named_changes(changes), revision=body.base_revision + 1))
    if result.rowcount != 1:
        if session.get(Asset, asset_id_text) is None:
            raise not_found()
        raise ApiError(409, "REVISION_CONFLICT", "The asset changed in another window.",
                       message_key="another_window_changed_the_configuration_read_it_again_before_saving")
    session.flush()
    session.expire_all()
    return asset_out(session, session.get(Asset, asset_id_text))

def list_asset_versions(session: Session, asset_id: UUID, limit: int=50, offset: int=0) -> AssetVersionPage:
    asset = session.get(Asset, str(asset_id))
    if asset is None or asset.scope != 'shared':
        raise not_found()
    total = session.scalar(select(func.count()).select_from(AssetVersion).where(AssetVersion.asset_id == asset.id)) or 0
    rows = session.scalars(select(AssetVersion).where(AssetVersion.asset_id == asset.id).order_by(AssetVersion.version_number.desc()).limit(limit).offset(offset)).all()
    return AssetVersionPage(items=[asset_version_out(row) for row in rows], total=total, limit=limit, offset=offset)

def get_asset_version(session: Session, asset_id: UUID, version_id: UUID) -> AssetVersionOut:
    asset, version = asset_version_scope(session, None, version_id)
    if asset.id != str(asset_id):
        raise not_found()
    return asset_version_out(version)

def list_version_hdus(session: Session, asset_id: UUID, version_id: UUID, limit: int=200, offset: int=0) -> FitsHduPage:
    asset, version = asset_version_scope(session, None, version_id)
    if asset.id != str(asset_id):
        raise not_found()
    total = session.scalar(select(func.count()).select_from(FitsHduMetadata).where(FitsHduMetadata.asset_version_id == version.id)) or 0
    rows = session.scalars(select(FitsHduMetadata).where(FitsHduMetadata.asset_version_id == version.id).order_by(FitsHduMetadata.hdu_index).limit(limit).offset(offset)).all()
    return FitsHduPage(items=[fits_hdu_out(row) for row in rows], total=total, limit=limit, offset=offset)

def get_version_header(session: Session, asset_id: UUID, version_id: UUID, hdu_index: int) -> FitsHeaderOut:
    asset, version = asset_version_scope(session, None, version_id)
    if asset.id != str(asset_id):
        raise not_found()
    hdu = session.scalar(select(FitsHduMetadata).where(FitsHduMetadata.asset_version_id == version.id, FitsHduMetadata.hdu_index == hdu_index))
    if hdu is None:
        raise not_found()
    return header_out(version, hdu)


def get_asset_preview_reference(session: Session, asset_id: UUID, version_id: UUID) -> PreviewReference:
    asset, version = asset_version_scope(session, None, version_id)
    if asset.id != str(asset_id):
        raise not_found()
    selected = session.scalar(select(FitsHduMetadata.hdu_index).where(
        FitsHduMetadata.asset_version_id == version.id, FitsHduMetadata.is_selected.is_(True)))
    if selected is None and (version.scientific_metadata or {}).get("format") in {"image", "raw", "xisf", "video"}:
        selected = 0
    return PreviewReference(asset_version_id=UUID(version.id), hdu_index=selected)
