from sqlalchemy import select
from sqlalchemy.orm import Session
from astrophotoflow.contracts.inputs import AssetInputReference, CanvasDataOut, CanvasDataRequest, CanvasInspectOut, CanvasInspectRequest, DatasetInputReference, ScienceSelection
from astrophotoflow.core.database.db import Database
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.modules.data.assets.metadata import asset_parameters
from astrophotoflow.modules.data.assets.models import Asset, FitsHduMetadata
from astrophotoflow.modules.data.science.inputs import current_dataset_members
from astrophotoflow.modules.data.equipment.models import Equipment
from astrophotoflow.modules.data.formats.layout import rgb_channel_first
from astrophotoflow.modules.data.imports.models import AssetTask, AssetTaskItem
from astrophotoflow.modules.data.media.links import asset_media_base
from astrophotoflow.modules.data.media.models import Preview
from astrophotoflow.modules.data.trash.models import LibraryEntryRemoval

def _available_asset(session: Session, asset_id: str) -> Asset:
    asset = session.get(Asset, asset_id)
    if asset is None or asset.scope != 'shared' or asset.status != 'active':
        raise not_found()
    if asset.availability != 'available' or not asset.content_hash or asset.byte_size is None:
        raise ApiError(409, 'SOURCE_UNAVAILABLE', f'{asset.name} 的原件尚未就绪或已经变化，不能加入画布。', message_key='the_original_for_p0_is_not_ready_or_has_changed_and_cannot_be_added_to_the_', message_params={'p0': asset.name})
    return asset

def prepare_canvas_data(database: Database, body: CanvasDataRequest) -> CanvasDataOut:
    with database.read_session() as session:
        if session.get(LibraryEntryRemoval, (body.entry_type, str(body.id))) is not None:
            raise not_found()
        if body.entry_type == 'asset':
            asset = _available_asset(session, str(body.id))
            return CanvasDataOut(title=asset.name, native_type='APF_FILE_REFERENCE' if (asset.scientific_metadata or {}).get('format') == 'other' else 'APF_DATA_REFERENCE',
                reference=AssetInputReference(kind='asset', asset_id=asset.id, selection=ScienceSelection(kind='whole_file')))
        dataset, members = current_dataset_members(session, body.id, body.asset_ids)
        selected_ids = [member.asset_id for member in members] if body.asset_ids is not None else None
        kinds = {(_available_asset(session, member.asset_id).scientific_metadata or {}).get('format') == 'other' for member in members}
        if len(kinds) != 1:
            raise ApiError(422, 'INVALID_REFERENCE', 'Files and scientific images require their respective input ports.', message_key='files_and_scientific_images_require_their_respective_input_ports')
        return CanvasDataOut(title=dataset.name, native_type='APF_FILE_REFERENCE' if True in kinds else 'APF_DATA_REFERENCE',
            reference=DatasetInputReference(kind='dataset', dataset_id=dataset.id, asset_ids=selected_ids))

def inspect_canvas_data(database: Database, body: CanvasInspectRequest) -> CanvasInspectOut:
    reference = body.reference
    with database.read_session() as session:
        if reference.kind == 'dataset':
            dataset, members = current_dataset_members(session, reference.dataset_id, reference.asset_ids)
            if body.member_index >= len(members):
                raise ApiError(422, 'INVALID_REFERENCE', 'Image index is outside the selected members.', message_key='image_index_is_outside_the_selected_members')
            identity, selection = members[body.member_index].asset_id, reference.selection
            title, total = dataset.name, len(members)
        else:
            if body.member_index != 0:
                raise ApiError(422, 'INVALID_REFERENCE', 'A single asset contains one item.', message_key='a_single_asset_contains_one_item')
            identity, selection = str(reference.asset_id), reference.selection
            title, total = None, 1
        asset = session.get(Asset, identity)
        if asset is None or asset.scope != 'shared':
            raise not_found()
        selected = session.scalar(select(FitsHduMetadata).where(FitsHduMetadata.asset_id == asset.id, FitsHduMetadata.is_selected.is_(True)))
        hdu = selected if selection.kind == 'whole_file' else session.scalar(select(FitsHduMetadata).where(FitsHduMetadata.asset_id == asset.id, FitsHduMetadata.hdu_index == selection.hdu_index))
        metadata = asset.scientific_metadata or {}
        hdu_index = hdu.hdu_index if hdu else 0
        preview = session.scalar(select(Preview).where(Preview.asset_id == asset.id, Preview.hdu_index == hdu_index, Preview.size == 'thumbnail').order_by(Preview.created_at.desc()).limit(1))
        active = session.scalar(select(AssetTaskItem.id).join(AssetTask, AssetTask.id == AssetTaskItem.task_id).where(AssetTaskItem.asset_id == asset.id, AssetTask.status.in_({'queued', 'running', 'cancelling'})).limit(1))
        status = preview.status if preview else 'unsupported' if metadata.get('parse_error') else 'pending' if active else 'not_ready'
        error = preview.error if preview else metadata.get('parse_error')
        if selection.kind == 'fits_hdu' and (hdu is None or selected is None or hdu.hdu_index != selected.hdu_index):
            status, error = ('unsupported', '所选 HDU 暂无可展示的预览。')
        if status == 'generating':
            status = 'pending'
        if status == 'pending' and asset.availability != 'available':
            status = 'not_ready'
        width, height = (None, None)
        shape = hdu.shape if hdu else None
        if shape and len(shape) >= 2:
            header = {card['keyword']: card.get('value') for card in hdu.header_cards}
            if hdu.supported_kind == 'rgb' and len(shape) == 3 and (not rgb_channel_first(header)):
                height, width = (shape[-3], shape[-2])
            else:
                height, width = (shape[-2], shape[-1])
        equipment = {}
        for kind in ('camera', 'filter', 'optical_system'):
            equipment_id = (asset_parameters(asset) or {}).get(kind + '_id')
            registered = session.get(Equipment, equipment_id) if equipment_id else None
            snapshot = (asset.equipment_snapshot or {}).get(kind + '_id') or {}
            equipment[kind] = registered.name if registered else snapshot.get('name')
        return CanvasInspectOut(title=title or asset.name, member_count=total, member_index=body.member_index, asset_id=asset.id, name=asset.name, view_base=asset_media_base(asset.id), availability=asset.availability, parameters=asset_parameters(asset) or {}, equipment=equipment, format=metadata.get('format'), width=width, height=height, bitpix=hdu.bitpix if hdu else None, pixel_type=hdu.pixel_type if hdu else None, preview_status=status, preview_error=error, byte_size=asset.byte_size, content_hash=asset.content_hash, preview_url=f'/astrophotoflow/api/v1/library/assets/{asset.id}/previews/thumbnail' if status == 'available' else None)
