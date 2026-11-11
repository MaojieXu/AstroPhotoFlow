"""Asset and FITS DTO assembly."""
from datetime import UTC
from uuid import UUID
from sqlalchemy.orm import Session
from astrophotoflow.contracts.assets import AssetOut, FitsHduOut, FitsHeaderOut
from astrophotoflow.modules.data.assets.metadata import asset_classification, asset_parameters
from astrophotoflow.modules.data.assets.models import Asset, FitsHduMetadata
from astrophotoflow.modules.data.media.links import asset_media_base

def asset_out(session: Session, row: Asset) -> AssetOut:
    from sqlalchemy import select
    from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember
    from astrophotoflow.modules.data.trash.models import LibraryEntryRemoval
    result = asset_out_with_current(row)
    owner = session.execute(select(Dataset.id, Dataset.name).join(DatasetMember, DatasetMember.dataset_id == Dataset.id).where(DatasetMember.asset_id == row.id)).first()
    result.in_trash = session.get(LibraryEntryRemoval, ('asset', row.id)) is not None
    if owner:
        result.dataset_id, result.dataset_name = UUID(owner.id), owner.name
    return result

def asset_out_with_current(row: Asset) -> AssetOut:
    return AssetOut(calibration_status=row.calibration_status, calibration_evidence=row.calibration_evidence or {}, id=UUID(row.id), name=row.name, scope=row.scope, owner_project_id=UUID(row.owner_project_id) if row.owner_project_id else None, role=row.role, calibration_level=row.calibration_level, classification=asset_classification(row), parameters=asset_parameters(row), equipment_snapshot=row.equipment_snapshot or {}, value_sources=row.value_sources or {}, notes=row.notes, status=row.status, revision=row.revision, view_base=asset_media_base(row.id), storage_mode=row.storage_mode, storage_location=row.storage_location, byte_size=row.byte_size, content_hash=row.content_hash, availability=row.availability, capture_snapshot=row.capture_snapshot, scientific_metadata=row.scientific_metadata, created_at=row.created_at.replace(tzinfo=UTC) if row.created_at.tzinfo is None else row.created_at.astimezone(UTC))

def fits_hdu_out(row: FitsHduMetadata) -> FitsHduOut:
    return FitsHduOut.model_validate({
        column.name: getattr(row, column.name)
        for column in row.__table__.columns
        if column.name in FitsHduOut.model_fields
    }, strict=False)

def header_out(asset: Asset, hdu: FitsHduMetadata) -> FitsHeaderOut:
    return FitsHeaderOut.model_validate({'asset_id': asset.id, 'hdu_index': hdu.hdu_index, 'cards': [{'keyword': card['keyword'], 'value': card.get('value'), 'comment': card.get('comment')} for card in hdu.header_cards]}, strict=False)
