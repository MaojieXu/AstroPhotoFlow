"""Asset and FITS DTO assembly, independent of HTTP and other data owners."""

from datetime import UTC
from uuid import UUID

from sqlalchemy.orm import Session

from astrophotoflow.contracts.assets import AssetOut, AssetVersionOut, FitsHduOut, FitsHeaderOut
from astrophotoflow.modules.data.assets.metadata import asset_classification, asset_parameters
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion, FitsHduMetadata
from astrophotoflow.modules.data.media.links import asset_media_base


def asset_version_out(row: AssetVersion) -> AssetVersionOut:
    return AssetVersionOut(
        id=UUID(row.id), asset_id=UUID(row.asset_id), version_number=row.version_number,
        view_base=asset_media_base(row.asset_id, row.id),
        storage_mode=row.storage_mode, storage_location=row.storage_location, byte_size=row.byte_size,
        content_hash=row.content_hash, availability=row.availability,
        camera_id=UUID(row.camera_id) if row.camera_id else None,
        optical_system_id=UUID(row.optical_system_id) if row.optical_system_id else None,
        filter_id=UUID(row.filter_id) if row.filter_id else None,
        frame_type=row.frame_type, calibration_level=row.calibration_level,
        capture_snapshot=row.capture_snapshot, scientific_metadata=row.scientific_metadata,
        created_at=row.created_at.replace(tzinfo=UTC) if row.created_at.tzinfo is None else row.created_at.astimezone(UTC),
    )


def asset_out(session: Session, row: Asset) -> AssetOut:
    version = None
    if row.current_version_id is not None:
        current = session.get(AssetVersion, row.current_version_id)
        if current is None or current.asset_id != row.id:
            raise RuntimeError("The current content version does not belong to this asset.")
        version = asset_version_out(current)
    classification = asset_classification(row)
    level = None
    if row.role == "calibration":
        level = {"masterframe": "master", "subframe": "individual"}.get(classification["frame_class"])
    return AssetOut(
        id=UUID(row.id), name=row.name, scope=row.scope,
        owner_project_id=UUID(row.owner_project_id) if row.owner_project_id else None,
        role=row.role, current_version_id=UUID(row.current_version_id) if row.current_version_id else None,
        classification=classification, parameters=asset_parameters(row),
        equipment_snapshot=row.equipment_snapshot or {}, value_sources=row.value_sources or {},
        notes=row.notes, status=row.status, revision=row.revision, calibration_level=level,
        created_at=row.created_at.replace(tzinfo=UTC) if row.created_at.tzinfo is None else row.created_at.astimezone(UTC),
        current_version=version,
    )


def fits_hdu_out(row: FitsHduMetadata) -> FitsHduOut:
    return FitsHduOut(id=UUID(row.id), asset_version_id=UUID(row.asset_version_id), hdu_index=row.hdu_index,
                      name=row.name, hdu_type=row.hdu_type, shape=row.shape, bitpix=row.bitpix,
                      pixel_type=row.pixel_type, bscale=row.bscale, bzero=row.bzero, bunit=row.bunit,
                      parser_version=row.parser_version, supported_kind=row.supported_kind,
                      is_selected=row.is_selected, parse_error=row.parse_error)


def header_out(version: AssetVersion, hdu: FitsHduMetadata) -> FitsHeaderOut:
    return FitsHeaderOut.model_validate({"asset_version_id": UUID(version.id), "hdu_index": hdu.hdu_index,
                                        "cards": [{"keyword": card["keyword"], "value": card.get("value"),
                                                   "comment": card.get("comment")} for card in hdu.header_cards]})
