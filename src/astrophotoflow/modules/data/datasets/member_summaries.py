"""Small table rows; full fixed capture and header facts remain detail reads."""
from datetime import UTC
from uuid import UUID

from sqlalchemy import select

from astrophotoflow.contracts.assets import LibraryParameterSummary
from astrophotoflow.contracts.datasets import DatasetMemberSummary
from astrophotoflow.modules.data.assets.exposure import exposure_summary
from astrophotoflow.modules.data.assets.models import FitsHduMetadata
from astrophotoflow.modules.data.datasets.models import DatasetMember
from astrophotoflow.modules.data.media.links import asset_media_base
from astrophotoflow.modules.data.media.models import Preview
from astrophotoflow.modules.data.media.thumbnail_batches import group_algorithm


def member_summaries(session, dataset_id, version_id, rows, calibrations):
    reference = session.scalar(select(DatasetMember.asset_version_id).where(
        DatasetMember.dataset_version_id == version_id).order_by(DatasetMember.position).limit(1))
    ids = [version.id for _, version, _, *_ in rows]
    selected = dict(session.execute(select(FitsHduMetadata.asset_version_id, FitsHduMetadata.hdu_index).where(
        FitsHduMetadata.asset_version_id.in_(ids), FitsHduMetadata.is_selected.is_(True))).all())
    previews = {preview.asset_version_id: preview for preview in session.scalars(select(Preview).where(
        Preview.asset_version_id.in_(ids), Preview.size == 'group_thumbnail',
        Preview.algorithm_version == group_algorithm(reference))) if preview.hdu_index == selected.get(preview.asset_version_id, 0)}

    def value(item):
        return {'state': 'unknown' if item is None else 'consistent', 'value': item}

    result = []
    for member, version, asset, *names in rows:
        equipment = {}
        for slot, name in zip(('camera', 'optical_system', 'filter'), names, strict=True):
            identity = getattr(asset, slot + '_id')
            equipment[slot] = value({'id': UUID(identity) if identity else None, 'name': name} if name else None)
        subframe = asset.frame_class == 'subframe'
        known = subframe and asset.exposure_seconds is not None
        preview = previews.get(version.id)
        base = asset_media_base(asset.id, version.id)
        result.append(DatasetMemberSummary.model_validate({
            'entry_type': 'asset', 'id': UUID(asset.id), 'name': asset.name, 'notes': asset.notes,
            'status': asset.status, 'revision': asset.revision, 'created_at': asset.created_at.replace(tzinfo=UTC),
            'version_id': UUID(version.id), 'version_number': version.version_number,
            'member_count': 1, 'matching_member_count': 1,
            'input_ready': bool(version.availability == 'available' and version.content_hash and version.byte_size is not None),
            'view_base': base, 'dataset_id': UUID(dataset_id), 'dataset_version_id': UUID(version_id), 'member_position': member.position,
            'summary': {'classification': {'frame_class': value(asset.frame_class), 'frame_type': value(asset.frame_type)},
                'parameters': {field: value(getattr(asset, field)) for field in LibraryParameterSummary.model_fields},
                'storage_mode': value(version.storage_mode), 'availability': value(version.availability), **equipment},
            'exposure_summary': exposure_summary(int(subframe), int(known), asset.exposure_seconds),
            'calibration_projection': calibrations[member.id], 'import_issue': None,
            'thumbnail_status': preview.status if preview else None,
            'thumbnail': {'asset_id': UUID(asset.id), 'asset_version_id': UUID(version.id), 'view_base': base,
                'hdu_index': preview.hdu_index} if preview and preview.status == 'available' else None,
        }))
    return result
