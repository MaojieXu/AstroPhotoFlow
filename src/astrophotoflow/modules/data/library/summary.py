"""Only selected scalar rows become strongly typed library summaries."""

import json
from datetime import UTC
from uuid import UUID

from sqlalchemy.engine import RowMapping

from astrophotoflow.contracts.assets import (
    LibraryAssetSummary,
    LibraryDatasetSummary,
    LibraryItemSummary,
    LibraryThumbnailReference,
)
from astrophotoflow.modules.data.assets.exposure import exposure_summary
from astrophotoflow.modules.data.assets.summaries import metadata_summary
from astrophotoflow.modules.data.media.links import asset_media_base


def item_summary(row: RowMapping, exposure=None) -> LibraryItemSummary:
    metadata = metadata_summary(row)
    created = row["created_at"]
    result_type = LibraryAssetSummary if row["entry_type"] == "asset" else LibraryDatasetSummary
    if exposure is None:
        subframe = metadata.classification.frame_class.value == 'subframe'
        known = subframe and metadata.parameters.exposure_seconds.value is not None
        exposure = exposure_summary(int(subframe), int(known), metadata.parameters.exposure_seconds.value)
    links = {"view_base": asset_media_base(row["id"], row["version_id"]) if row["version_id"] else None} if row["entry_type"] == "asset" else {}
    thumbnail = json.loads(row["thumbnail_ref"]) if row["thumbnail_ref"] else None
    if thumbnail:
        thumbnail["view_base"] = asset_media_base(thumbnail["asset_id"], thumbnail["asset_version_id"])
        thumbnail["asset_id"] = UUID(thumbnail["asset_id"])
        thumbnail["asset_version_id"] = UUID(thumbnail["asset_version_id"])
    return result_type(
        entry_type=row["entry_type"], id=UUID(row["id"]), name=row["name"], notes=row["notes"], status=row["status"], revision=row["revision"],
        created_at=created.replace(tzinfo=UTC) if created.tzinfo is None else created.astimezone(UTC),
        version_id=UUID(row["version_id"]) if row["version_id"] else None, version_number=row["version_number"],
        member_count=row["member_count"], matching_member_count=row["matching_member_count"], input_ready=bool(row["input_ready"]),
        summary=metadata, exposure_summary=exposure, import_issue=row["import_issue"],
        thumbnail=LibraryThumbnailReference.model_validate(thumbnail) if thumbnail else None,
        **links,
    )
