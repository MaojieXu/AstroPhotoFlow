"""Durable thumbnail requests and asset-scoped cache identities."""

from __future__ import annotations
import hashlib
import json
from uuid import uuid4
from sqlalchemy import func, select
from astrophotoflow.contracts.thumbnails import ThumbnailBatchCreate, ThumbnailBatchOut
from astrophotoflow.core.errors import ApiError, not_found
from astrophotoflow.modules.data.assets.models import Asset, FitsHduMetadata
from astrophotoflow.modules.data.assets.visibility import standalone_asset_ids, visible_dataset, visible_members
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember
from astrophotoflow.modules.data.media.models import Preview, ThumbnailBatch, ThumbnailBatchItem

THUMBNAIL_STANDALONE = "library-thumb-1"
THUMBNAIL_GROUP_PREFIX = "library-group-1:"
THUMBNAIL_FORMATS = {"fits", "xisf", "image", "raw"}


def group_algorithm(reference_id: str) -> str:
    return THUMBNAIL_GROUP_PREFIX + reference_id


def _selected_hdu(session, asset_id: str) -> int:
    index = session.scalar(
        select(FitsHduMetadata.hdu_index).where(FitsHduMetadata.asset_id == asset_id, FitsHduMetadata.is_selected.is_(True)).limit(1)
    )
    return index if index is not None else 0


def _group(session, dataset_id: str) -> list[tuple[str, str | None, str | None]]:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise not_found()
    members = session.scalars(
        select(DatasetMember.asset_id).where(DatasetMember.dataset_id == dataset_id).order_by(DatasetMember.position)
    ).all()
    return [(member, dataset_id, members[0]) for member in members]


def _library(session) -> list[tuple[str, str | None, str | None]]:
    targets = []
    groups = session.scalars(select(Dataset.id).where(visible_dataset()).order_by(Dataset.id)).all()
    for dataset_id in groups:
        targets.extend(_group(session, dataset_id))
    grouped = visible_members()
    standalone = standalone_asset_ids(grouped)
    assets = session.scalars(select(Asset.id).where(Asset.id.in_(standalone), Asset.id.is_not(None)).order_by(Asset.id)).all()
    targets.extend(((asset, None, None) for asset in assets))
    return targets


def _targets(session, target: dict) -> list[tuple[str, str | None, str | None]]:
    if target["kind"] == "library_missing":
        return _library(session)
    if target["kind"] == "dataset":
        return _group(session, target["dataset_id"])
    asset = session.get(Asset, target["asset_id"])
    if asset is None or asset.id != target["asset_id"]:
        raise not_found()
    return [(asset.id, None, None)]


def create_thumbnail_batch(database, body: ThumbnailBatchCreate) -> str:
    request = body.model_dump(mode="json", exclude={"request_id"})
    fingerprint = hashlib.sha256(json.dumps(request, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    batch_id = str(body.request_id)
    with database.write_session() as session:
        old = session.get(ThumbnailBatch, batch_id)
        if old is not None:
            if old.fingerprint != fingerprint:
                raise ApiError(
                    409,
                    "REQUEST_ID_CONFLICT",
                    "Thumbnail request ID already has different content.",
                    message_key="thumbnail_request_id_already_has_different_content",
                )
            return batch_id
        targets = _targets(session, request["target"])
        batch = ThumbnailBatch(id=batch_id, fingerprint=fingerprint, target=request["target"])
        session.add(batch)
        session.flush()
        for position, (asset_id, dataset_id, reference_id) in enumerate(targets):
            asset = session.get(Asset, asset_id)
            if asset is None:
                raise not_found()
            hdu = _selected_hdu(session, asset_id)
            size = "group_thumbnail" if reference_id else "thumbnail"
            algorithm = group_algorithm(reference_id) if reference_id else THUMBNAIL_STANDALONE
            preview = session.scalar(
                select(Preview).where(
                    Preview.asset_id == asset_id, Preview.hdu_index == hdu, Preview.size == size, Preview.algorithm_version == algorithm
                )
            )
            if preview is None:
                preview = Preview(
                    id=str(uuid4()),
                    asset_id=asset_id,
                    hdu_index=hdu,
                    size=size,
                    algorithm_version=algorithm,
                    width=0,
                    height=0,
                    storage_path="",
                    mime_type="image/jpeg",
                    display_parameters={"reference_asset_id": reference_id},
                    status="queued",
                    error=None,
                )
                session.add(preview)
                session.flush()
            elif body.mode == "rebuild" and preview.status != "generating":
                preview.status, preview.error = ("queued", None)
            session.add(
                ThumbnailBatchItem(
                    id=str(uuid4()), batch_id=batch_id, preview_id=preview.id, asset_id=asset_id, dataset_id=dataset_id, position=position
                )
            )
    return batch_id


def thumbnail_batch_status(database, batch_id: str, limit: int = 50, offset: int = 0) -> ThumbnailBatchOut:
    with database.read_session() as session:
        batch = session.get(ThumbnailBatch, batch_id)
        if batch is None:
            raise not_found()
        counts = {key: 0 for key in ("queued", "generating", "available", "failed", "unsupported", "deleted")}
        totals = session.execute(
            select(Preview.status, func.count(ThumbnailBatchItem.id))
            .select_from(ThumbnailBatchItem)
            .outerjoin(Preview, Preview.id == ThumbnailBatchItem.preview_id)
            .where(ThumbnailBatchItem.batch_id == batch_id)
            .group_by(Preview.status)
        ).all()
        for raw_status, count in totals:
            status = raw_status if raw_status is not None else "deleted"
            counts[status if status in counts else "failed"] += count
        rows = session.execute(
            select(ThumbnailBatchItem, Preview)
            .outerjoin(Preview, Preview.id == ThumbnailBatchItem.preview_id)
            .where(ThumbnailBatchItem.batch_id == batch_id)
            .order_by(ThumbnailBatchItem.position)
            .limit(limit)
            .offset(offset)
        ).all()
        items = []
        for item, preview in rows:
            status = preview.status if preview is not None else "deleted"
            if status not in counts:
                status = "failed"
            items.append(
                {
                    "id": item.id,
                    "asset_id": item.asset_id,
                    "dataset_id": item.dataset_id,
                    "position": item.position,
                    "status": status,
                    "error": preview.error if preview is not None else None,
                }
            )
        group_references = session.execute(
            select(ThumbnailBatchItem.dataset_id, Preview.display_parameters["reference_asset_id"].as_string())
            .join(Preview, Preview.id == ThumbnailBatchItem.preview_id)
            .where(ThumbnailBatchItem.batch_id == batch_id, ThumbnailBatchItem.dataset_id.is_not(None))
            .distinct()
            .order_by(ThumbnailBatchItem.dataset_id)
        ).all()
        reference_ids = {reference for _, reference in group_references if reference}
        references = (
            session.execute(
                select(ThumbnailBatchItem.dataset_id, Preview)
                .join(Preview, Preview.id == ThumbnailBatchItem.preview_id)
                .where(ThumbnailBatchItem.batch_id == batch_id, Preview.asset_id.in_(reference_ids), Preview.size == "group_thumbnail")
            ).all()
            if reference_ids
            else []
        )
        by_reference = {
            (dataset_id, row.asset_id): row for dataset_id, row in references if row.algorithm_version == group_algorithm(row.asset_id)
        }
        group_failures = []
        for dataset_id, reference_id in group_references:
            if not reference_id:
                continue
            reference = by_reference.get((dataset_id, reference_id))
            if reference is None or reference.status in {"failed", "unsupported"}:
                group_failures.append(
                    {
                        "dataset_id": dataset_id,
                        "reference_asset_id": reference_id,
                        "code": "FIRST_FRAME_UNAVAILABLE",
                        "error": reference.error
                        if reference is not None and reference.error
                        else "First group member has no usable stretch.",
                    }
                )
        state = (
            "running"
            if counts["queued"] or counts["generating"]
            else "needs_attention"
            if counts["failed"] or counts["unsupported"] or counts["deleted"]
            else "completed"
        )
        return ThumbnailBatchOut.model_validate(
            {
                "request_id": batch.id,
                "target": batch.target,
                "state": state,
                "total": sum(counts.values()),
                **counts,
                "items": items,
                "group_failures": group_failures,
                "limit": limit,
                "offset": offset,
            },
            strict=False,
        )


def retry_thumbnail_items(database, batch_id: str, item_ids: list[str]) -> None:
    if len(item_ids) != len(set(item_ids)):
        raise ApiError(422, "DUPLICATE_ITEM", "Thumbnail items must be unique.", message_key="thumbnail_items_must_be_unique")
    with database.write_session() as session:
        if session.get(ThumbnailBatch, batch_id) is None:
            raise not_found()
        rows = session.execute(
            select(ThumbnailBatchItem, Preview)
            .join(Preview, Preview.id == ThumbnailBatchItem.preview_id)
            .where(ThumbnailBatchItem.batch_id == batch_id, ThumbnailBatchItem.id.in_(item_ids))
        ).all()
        if len(rows) != len(item_ids) or any((preview.status not in {"failed", "unsupported"} for _, preview in rows)):
            raise ApiError(
                409,
                "THUMBNAIL_NOT_RETRYABLE",
                "Selected items are missing or not failed.",
                message_key="selected_items_are_missing_or_not_failed",
            )
        dependencies = {}
        for item, preview in rows:
            reference_id = (preview.display_parameters or {}).get("reference_asset_id")
            if not reference_id or reference_id == preview.asset_id:
                continue
            reference = session.scalar(
                select(Preview)
                .join(ThumbnailBatchItem, ThumbnailBatchItem.preview_id == Preview.id)
                .where(
                    ThumbnailBatchItem.batch_id == batch_id,
                    ThumbnailBatchItem.dataset_id == item.dataset_id,
                    Preview.asset_id == reference_id,
                    Preview.size == "group_thumbnail",
                    Preview.algorithm_version == group_algorithm(reference_id),
                )
            )
            if reference is None:
                raise ApiError(
                    409,
                    "THUMBNAIL_REFERENCE_MISSING",
                    "The first-member thumbnail is missing; generate a new batch for this dataset.",
                    message_key="the_fixed_first_member_thumbnail_is_missing_generate_a_new_batch",
                )
            if reference.status in {"failed", "unsupported"}:
                dependencies[reference.id] = reference
        for reference in dependencies.values():
            reference.status, reference.error = ("queued", None)
        for _, preview in rows:
            preview.status, preview.error = ("queued", None)
