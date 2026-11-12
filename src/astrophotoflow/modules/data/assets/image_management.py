"""Image management uses existing assets and preserves fixed content snapshots."""
from copy import deepcopy
from datetime import UTC
from uuid import UUID
from sqlalchemy import literal, func, select
from sqlalchemy.orm import Session
from astrophotoflow.contracts.assets import AssetPatch
from astrophotoflow.contracts.image_management import AssetMetadataChange, AssetRevisionRef, EquipmentApplication, ImageChanges, ImageSearch
from astrophotoflow.core.errors import ApiError, invalid_reference, not_found
from astrophotoflow.modules.data.assets.image_metadata import freeze_equipment_application, merge_image_metadata, record_import_image_metadata
from astrophotoflow.modules.data.assets.image_provenance import get_master_provenance, update_master_provenance  # noqa: F401
from astrophotoflow.modules.data.assets.mapping import asset_out_with_current
from astrophotoflow.modules.data.assets.models import Asset, FitsHduMetadata, ImageMetadataState
from astrophotoflow.modules.data.assets.service import update_asset
from astrophotoflow.modules.data.assets.visibility import not_removed

def image_member_predicates(query: ImageSearch, *, fixed_dataset: bool=False) -> list:
    """One member must satisfy every supplied scientific filter."""
    conditions = []
    if query.target_name is not None:
        conditions.append(ImageMetadataState.target_name.collate('apf_casefold') == query.target_name)
    for field, column in (('calibration_status', Asset.calibration_status), ('frame_class', literal('subframe') if fixed_dataset else Asset.frame_class), ('frame_type', Asset.frame_type if fixed_dataset else Asset.frame_type), ('camera_id', Asset.camera_id), ('telescope_id', Asset.optical_system_id), ('filter_id', Asset.filter_id), ('parameter_mode', Asset.parameter_mode), ('binning_x', Asset.binning_x), ('binning_y', Asset.binning_y)):
        value = getattr(query, field)
        if value is not None:
            conditions.append(column == (str(value) if isinstance(value, UUID) else value))
    for prefix, column in (('exposure', Asset.exposure_seconds), ('temperature', Asset.sensor_temperature_c), ('gain', Asset.gain), ('offset', Asset.offset), ('iso', Asset.iso)):
        low, high = (getattr(query, prefix + '_min'), getattr(query, prefix + '_max'))
        if low is not None:
            conditions.append(column >= low)
        if high is not None:
            conditions.append(column <= high)
    for prefix, column in (('captured', ImageMetadataState.capture_start_utc), ('master_created', ImageMetadataState.master_created_utc)):
        low, high = (getattr(query, prefix + '_from'), getattr(query, prefix + '_to'))
        if low is not None:
            conditions.append(column >= low.astimezone(UTC))
        if high is not None:
            conditions.append(column <= high.astimezone(UTC))
    return conditions

def image_sort(query: ImageSearch, *, created=Asset.created_at, name=Asset.name_search_key, identity=Asset.id):
    column = {'created_at': created, 'name': name, 'capture_start': ImageMetadataState.capture_start_utc, 'master_created_at': ImageMetadataState.master_created_utc}[query.sort_by]
    ordered = column.desc() if query.order == 'desc' else column.asc()
    return (column.is_(None).asc(), ordered, identity.asc())

def _asset(session: Session, asset_id: UUID | str) -> Asset:
    row = session.get(Asset, str(asset_id))
    if row is None or row.scope != 'shared':
        raise not_found()
    return row

def require_asset_revision(session: Session, asset_id: UUID | str, expected_revision: int) -> Asset:
    row = _asset(session, asset_id)
    if row.revision != expected_revision:
        raise ApiError(409, 'REVISION_CONFLICT', 'The image changed; read its current revision before saving.', message_key='the_image_changed_read_its_current_revision_before_saving')
    return row

def _image_detail(row, state) -> dict:
    return {'asset': asset_out_with_current(row).model_dump(mode='json'),
        'metadata': deepcopy(state.metadata_json) if state else {},
        'equipment_context': deepcopy(state.equipment_context) if state else None}


def get_image(session: Session, asset_id: UUID | str) -> dict:
    row = session.get(Asset, str(asset_id))
    if row is None or row.scope != 'shared':
        raise not_found()
    return _image_detail(row, session.get(ImageMetadataState, row.id))

def search_images(session: Session, query: ImageSearch) -> dict:
    conditions = [Asset.scope == 'shared', not_removed('asset', Asset.id), *image_member_predicates(query)]
    if query.status != 'all':
        conditions.append(Asset.status == query.status)
    if query.text:
        conditions.append(Asset.name_search_key.contains(query.text.casefold(), autoescape=True))
    statement = select(Asset).outerjoin(ImageMetadataState, ImageMetadataState.asset_id == Asset.id).where(*conditions)
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = session.scalars(statement.order_by(*image_sort(query)).limit(query.limit).offset(query.offset)).all()
    if not rows:
        return {'items': [], 'total': total, 'limit': query.limit, 'offset': query.offset}
    states = {state.asset_id: state for state in session.scalars(select(ImageMetadataState).where(ImageMetadataState.asset_id.in_([row.id for row in rows])))}
    items = [_image_detail(row, states.get(row.id)) for row in rows]
    return {'items': items, 'total': total, 'limit': query.limit, 'offset': query.offset}

def update_image(session: Session, asset_id: UUID | str, expected_revision: int, changes: ImageChanges, *, validate_datasets: bool = True) -> dict:
    require_asset_revision(session, asset_id, expected_revision)
    patch = changes.model_dump(mode='json', exclude_unset=True)
    state = session.get(ImageMetadataState, str(asset_id))
    merge_image_metadata(state.metadata_json if state else {}, patch)
    native_patch = {key: value for key, value in patch.items() if key in {'name', 'notes', 'status', 'classification', 'parameters', 'calibration_status', 'calibration_reason'}}
    update_asset(session, UUID(str(asset_id)), AssetPatch.model_validate({'base_revision': expected_revision, **native_patch}), validate_datasets=validate_datasets)
    record_import_image_metadata(session, str(asset_id), patch)
    return get_image(session, asset_id)

def update_image_metadata_batch(session: Session, items: list[AssetMetadataChange]) -> dict:
    if not items or len({item.asset_id for item in items}) != len(items):
        raise invalid_reference('Provide a nonempty list of distinct images.')
    for item in items:
        require_asset_revision(session, item.asset_id, item.expected_revision)
    with session.begin_nested():
        output = [update_image(session, item.asset_id, item.expected_revision, item.changes, validate_datasets=False) for item in items]
        from astrophotoflow.modules.data.datasets.consistency import validate_containing_datasets
        validate_containing_datasets(session, [str(item.asset_id) for item in items])
    return {'items': output}

def apply_image_equipment(session: Session, assets: list[AssetRevisionRef], equipment: EquipmentApplication) -> dict:
    if not assets or len({item.asset_id for item in assets}) != len(assets):
        raise invalid_reference('Provide a nonempty list of distinct images.')
    rows = [require_asset_revision(session, item.asset_id, item.expected_revision) for item in assets]
    frozen = freeze_equipment_application(session, equipment)
    output = []
    with session.begin_nested():
        for item, asset in zip(assets, rows, strict=True):
            parameters = dict(frozen.get('parameters', {}))
            selected = deepcopy(frozen.get('selected_equipment', {}))
            telescope = selected.get('optical_system_id')
            old_telescope = (asset.equipment_snapshot or {}).get('optical_system_id')
            if 'optical_accessory' in equipment.fields and 'telescope' not in equipment.fields:
                if not old_telescope or not telescope or old_telescope.get('id') != telescope.get('id'):
                    raise invalid_reference("Changing only an accessory requires the image's existing telescope.")
            elif 'telescope' in equipment.fields and 'optical_accessory' not in equipment.fields and (telescope is not None):
                if old_telescope and old_telescope.get('id') == telescope.get('id'):
                    telescope['optical_accessory'] = deepcopy(old_telescope.get('optical_accessory'))
                    telescope['effective_focal_length_mm'] = old_telescope.get('effective_focal_length_mm')
                else:
                    telescope['optical_accessory'] = None
                    telescope['effective_focal_length_mm'] = telescope.get('specs', {}).get('native_focal_length_mm')
            update_asset(session, item.asset_id, AssetPatch.model_validate({'base_revision': item.expected_revision, 'parameters': parameters}), validate_datasets=False)
            asset = session.get(Asset, str(item.asset_id))
            snapshots = deepcopy(asset.equipment_snapshot or {})
            for key, value in selected.items():
                if value is None:
                    snapshots.pop(key, None)
                else:
                    snapshots[key] = value
            asset.equipment_snapshot = snapshots
            sources = dict(asset.value_sources or {})
            if 'optical_accessory' in equipment.fields:
                sources['optical_accessory'] = 'manual'
            asset.value_sources = sources
            record_import_image_metadata(session, asset.id, {}, frozen)
            output.append(get_image(session, asset.id))
        from astrophotoflow.modules.data.datasets.consistency import validate_containing_datasets
        validate_containing_datasets(session, [asset.id for asset in rows])
    return {'items': output}

def read_image_header(session: Session, asset_id: UUID | str, hdu_index: int=0, keywords: list[str] | None=None, limit: int=100, offset: int=0) -> dict:
    _asset(session, asset_id)
    version = session.get(Asset, str(asset_id))
    if version is None or version.id != str(asset_id):
        raise not_found()
    if hdu_index < 0 or not 1 <= limit <= 200 or offset < 0:
        raise invalid_reference('Invalid header selection or pagination.')
    hdu = session.scalar(select(FitsHduMetadata).where(FitsHduMetadata.asset_id == version.id, FitsHduMetadata.hdu_index == hdu_index))
    if hdu is None:
        raise not_found()
    cards = deepcopy(hdu.header_cards)
    if keywords is not None:
        selected = {value.upper() for value in keywords}
        cards = [card for card in cards if card['keyword'].upper() in selected]
    return {'asset_id': version.id, 'hdu_index': hdu_index, 'cards': cards[offset:offset + limit], 'total': len(cards), 'limit': limit, 'offset': offset}
