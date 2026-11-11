"""Small table rows; full fixed capture and header facts remain detail reads."""
from datetime import UTC
from uuid import UUID
from sqlalchemy import select
from astrophotoflow.contracts.assets import LibraryParameterSummary
from astrophotoflow.contracts.datasets import DatasetMemberSummary
from astrophotoflow.modules.data.assets.calibration_status import single_calibration_summary
from astrophotoflow.modules.data.assets.exposure import exposure_summary
from astrophotoflow.modules.data.assets.models import FitsHduMetadata
from astrophotoflow.modules.data.datasets.models import DatasetMember
from astrophotoflow.modules.data.media.links import asset_media_base
from astrophotoflow.modules.data.media.models import Preview
from astrophotoflow.modules.data.media.thumbnail_batches import group_algorithm

def member_summaries(session, dataset_id, rows):
    reference = session.scalar(select(DatasetMember.asset_id).where(DatasetMember.dataset_id == dataset_id).order_by(DatasetMember.position).limit(1))
    ids = [asset.id for _, asset, *_ in rows]
    selected = dict(session.execute(select(FitsHduMetadata.asset_id, FitsHduMetadata.hdu_index).where(FitsHduMetadata.asset_id.in_(ids), FitsHduMetadata.is_selected.is_(True))).all())
    previews = {preview.asset_id: preview for preview in session.scalars(select(Preview).where(Preview.asset_id.in_(ids), Preview.size == 'group_thumbnail', Preview.algorithm_version == group_algorithm(reference))) if preview.hdu_index == selected.get(preview.asset_id, 0)}

    def value(item):
        return {'state': 'unknown' if item is None else 'consistent', 'value': item}
    result = []
    for member, asset, *names in rows:
        equipment = {}
        for slot, name in zip(('camera', 'optical_system', 'filter'), names, strict=True):
            identity = getattr(asset, slot + '_id')
            equipment[slot] = value({'id': UUID(identity) if identity else None, 'name': name} if name else None)
        known = asset.exposure_seconds is not None
        preview = previews.get(asset.id)
        base = asset_media_base(asset.id)
        result.append(DatasetMemberSummary.model_validate({**single_calibration_summary(asset.calibration_status).model_dump(), 'entry_type': 'asset', 'id': UUID(asset.id), 'name': asset.name, 'notes': asset.notes, 'status': asset.status, 'revision': asset.revision, 'created_at': asset.created_at.replace(tzinfo=UTC), 'member_count': 1, 'matching_member_count': 1, 'input_ready': bool(asset.availability == 'available' and asset.content_hash and (asset.byte_size is not None)), 'view_base': base, 'dataset_id': UUID(dataset_id), 'member_position': member.position, 'summary': {'classification': {'frame_class': value('subframe'), 'frame_type': value(asset.frame_type)}, 'parameters': {field: value(getattr(asset, field)) for field in LibraryParameterSummary.model_fields}, 'storage_mode': value(asset.storage_mode), 'availability': value(asset.availability), **equipment}, 'exposure_summary': exposure_summary(1, int(known), asset.exposure_seconds), 'import_issue': None, 'thumbnail_status': preview.status if preview else None, 'thumbnail': {'asset_id': UUID(asset.id), 'view_base': base, 'hdu_index': preview.hdu_index} if preview and preview.status == 'available' else None}))
    return result
