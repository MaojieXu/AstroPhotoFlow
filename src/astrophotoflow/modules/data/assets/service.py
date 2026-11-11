from __future__ import annotations
from uuid import UUID
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from astrophotoflow.contracts.assets import AssetOut, AssetPatch, FitsHduPage, FitsHeaderOut, PreviewReference
from astrophotoflow.contracts.metadata import AssetClassification, AssetParametersPatch
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.modules.data.assets.mapping import asset_out, fits_hdu_out, header_out
from astrophotoflow.modules.data.assets.metadata import asset_classification, asset_parameters, classification_columns, parameter_columns
from astrophotoflow.modules.data.assets.models import Asset, FitsHduMetadata
from astrophotoflow.modules.data.assets.references import asset_scope
from astrophotoflow.modules.data.equipment.models import Equipment
from astrophotoflow.modules.data.equipment.references import validate_equipment_reference
from astrophotoflow.modules.data.equipment.snapshots import snapshot_equipment
from astrophotoflow.modules.data.names import named_changes

def get_asset(session: Session, asset_id: UUID) -> AssetOut:
    asset = asset_scope(session, None, asset_id)
    return asset_out(session, asset)

def update_asset(session: Session, asset_id: UUID, body: AssetPatch, *, validate_datasets: bool = True) -> AssetOut:
    asset_id_text = str(asset_id)
    asset = session.get(Asset, asset_id_text)
    if asset is None or asset.scope != 'shared':
        raise not_found()
    changes = body.model_dump(exclude_unset=True, exclude={'base_revision', 'classification', 'parameters', 'calibration_reason'})
    fields = [key for key in ('name', 'status') if key in changes and changes[key] is None]
    if fields:
        raise ApiError(422, 'VALIDATION_ERROR', 'These asset fields cannot be null.', [{'path': key, 'message': 'Cannot be null.'} for key in fields], message_key='invalid_request_fields', field_message_keys={key: 'field_not_nullable' for key in fields})
    if 'calibration_reason' in body.model_fields_set and 'calibration_status' not in body.model_fields_set:
        raise ApiError(422, 'VALIDATION_ERROR', 'A calibration reason requires a calibration status.', message_key='a_calibration_reason_requires_a_calibration_status')
    if 'calibration_status' in body.model_fields_set:
        changes['calibration_evidence'] = {'source': 'user', 'reason': body.calibration_reason}
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
        from astrophotoflow.modules.data.datasets.models import DatasetMember
        if classification.get('frame_class') != 'subframe' and session.scalar(select(DatasetMember.id).where(DatasetMember.asset_id == asset.id).limit(1)) is not None:
            raise ApiError(409, 'INVALID_REFERENCE', 'Dataset members must remain subframes. Remove this asset from its datasets before changing its class.', message_key='dataset_members_must_remain_subframes_remove_this_asset_from_its_datasets_before_changing_its_class')
        changes.update(classification_columns(classification))
        changes['calibration_level'] = {'masterframe': 'master', 'subframe': 'individual'}.get(classification.get('frame_class'))
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
        raise ApiError(409, 'REVISION_CONFLICT', 'The asset changed in another window.', message_key='another_window_changed_the_configuration_read_it_again_before_saving')
    session.flush()
    session.expire_all()
    if validate_datasets and (body.classification is not None or body.parameters is not None):
        from astrophotoflow.modules.data.datasets.consistency import validate_containing_datasets
        validate_containing_datasets(session, [asset_id_text])
    from astrophotoflow.modules.data.library.manifests import schedule_mirrors
    schedule_mirrors(session, asset_ids={asset_id_text})
    session.flush()
    return asset_out(session, session.get(Asset, asset_id_text))

def list_asset_hdus(session: Session, asset_id: UUID, limit: int=200, offset: int=0) -> FitsHduPage:
    asset_scope(session, None, asset_id)
    condition = FitsHduMetadata.asset_id == str(asset_id)
    total = session.scalar(select(func.count()).select_from(FitsHduMetadata).where(condition)) or 0
    rows = session.scalars(select(FitsHduMetadata).where(condition).order_by(FitsHduMetadata.hdu_index).limit(limit).offset(offset)).all()
    return FitsHduPage(items=[fits_hdu_out(row) for row in rows], total=total, limit=limit, offset=offset)

def get_asset_header(session: Session, asset_id: UUID, hdu_index: int) -> FitsHeaderOut:
    asset = asset_scope(session, None, asset_id)
    hdu = session.scalar(select(FitsHduMetadata).where(FitsHduMetadata.asset_id == asset.id, FitsHduMetadata.hdu_index == hdu_index))
    if hdu is None:
        raise not_found()
    return header_out(asset, hdu)

def get_asset_preview_reference(session: Session, asset_id: UUID) -> PreviewReference:
    asset = asset_scope(session, None, asset_id)
    selected = session.scalar(select(FitsHduMetadata.hdu_index).where(FitsHduMetadata.asset_id == asset.id, FitsHduMetadata.is_selected.is_(True)))
    if selected is None and (asset.scientific_metadata or {}).get('format') in {'image', 'raw', 'xisf', 'video'}:
        selected = 0
    return PreviewReference(asset_id=UUID(asset.id), hdu_index=selected)
