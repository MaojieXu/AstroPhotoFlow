"""Explicit image-group queries share the same per-image scientific predicates."""

from copy import deepcopy
from uuid import UUID

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from astrophotoflow.contracts.datasets import DatasetPatch
from astrophotoflow.contracts.image_management import DatasetChanges, DatasetMemberSearch, DatasetSearch
from astrophotoflow.core.errors import not_found
from astrophotoflow.modules.data.assets.image_management import image_member_predicates, image_sort
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion, ImageMetadataState
from astrophotoflow.modules.data.assets.queries import empty_version_summary, summarize_dataset_versions
from astrophotoflow.modules.data.assets.visibility import not_removed
from astrophotoflow.modules.data.calibration.rows import member_calibration_projections
from astrophotoflow.modules.data.datasets.mapping import dataset_member_out, dataset_out, dataset_version_summary
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember, DatasetVersion
from astrophotoflow.modules.data.datasets.service import update_dataset


def _dataset(session: Session, dataset_id: UUID | str) -> Dataset:
    row = session.get(Dataset, str(dataset_id))
    if row is None:
        raise not_found()
    return row


def get_image_dataset(session: Session, dataset_id: UUID | str, version_id: UUID | str | None = None) -> dict:
    dataset = _dataset(session, dataset_id)
    identity = str(version_id or dataset.current_version_id) if version_id or dataset.current_version_id else None
    version = session.get(DatasetVersion, identity) if identity else None
    if (version_id is not None and version is None) or (version and version.dataset_id != dataset.id):
        raise not_found()
    return {"dataset": dataset_out(session, dataset).model_dump(mode="json"),
            "version": dataset_version_summary(session, version).model_dump(mode="json") if version else None}


def search_image_datasets(session: Session, query: DatasetSearch) -> dict:
    predicates = image_member_predicates(query)
    matched = case((and_(*predicates), 1), else_=0) if predicates else case((DatasetMember.id.is_not(None), 1), else_=0)
    aggregate = select(Dataset.id.label("dataset_id"), func.count(DatasetMember.id).label("member_count"),
                       func.coalesce(func.sum(matched), 0).label("matching_member_count"),
                       func.min(ImageMetadataState.capture_start_utc).label("capture_start"),
                       func.min(ImageMetadataState.master_created_utc).label("master_created_at")).select_from(Dataset).outerjoin(
        DatasetMember, DatasetMember.dataset_version_id == Dataset.current_version_id).outerjoin(
        AssetVersion, AssetVersion.id == DatasetMember.asset_version_id).outerjoin(
        Asset, Asset.id == AssetVersion.asset_id).outerjoin(
        ImageMetadataState, ImageMetadataState.asset_id == Asset.id).group_by(Dataset.id).subquery()
    conditions = [not_removed("dataset", Dataset.id)]
    if query.status != "all":
        conditions.append(Dataset.status == query.status)
    if query.text:
        conditions.append(Dataset.name_search_key.contains(query.text.casefold(), autoescape=True))
    if predicates:
        if query.match == "all":
            conditions.extend((aggregate.c.member_count > 0, aggregate.c.matching_member_count == aggregate.c.member_count))
        else:
            conditions.append(aggregate.c.matching_member_count > 0)
    statement = select(Dataset, aggregate.c.member_count, aggregate.c.matching_member_count).join(
        aggregate, aggregate.c.dataset_id == Dataset.id).where(*conditions)
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    column = {"created_at": Dataset.created_at, "name": Dataset.name_search_key,
              "capture_start": aggregate.c.capture_start, "master_created_at": aggregate.c.master_created_at}[query.sort_by]
    order = column.desc() if query.order == "desc" else column.asc()
    rows = session.execute(statement.order_by(column.is_(None).asc(), order, Dataset.id.asc()).limit(query.limit).offset(query.offset)).all()
    facts = summarize_dataset_versions(session, [dataset.current_version_id for dataset, _, _ in rows if dataset.current_version_id])
    return {"items": [{"dataset": dataset_out(session, dataset, facts[dataset.current_version_id] if dataset.current_version_id else empty_version_summary()).model_dump(mode="json"),
                       "member_count": count, "matching_member_count": matching, "version_id": dataset.current_version_id}
                      for dataset, count, matching in rows], "total": total, "limit": query.limit, "offset": query.offset}


def list_image_dataset_members(session: Session, dataset_id: UUID | str, version_id: UUID | str,
                                  query: DatasetMemberSearch) -> dict:
    _dataset(session, dataset_id)
    version = session.get(DatasetVersion, str(version_id))
    if version is None or version.dataset_id != str(dataset_id):
        raise not_found()
    conditions = [DatasetMember.dataset_version_id == version.id, *image_member_predicates(query)]
    if query.status != "all":
        conditions.append(Asset.status == query.status)
    if query.text:
        conditions.append(Asset.name_search_key.contains(query.text.casefold(), autoescape=True))
    statement = select(DatasetMember, AssetVersion, Asset, ImageMetadataState).join(
        AssetVersion, AssetVersion.id == DatasetMember.asset_version_id).join(Asset, Asset.id == AssetVersion.asset_id).outerjoin(
        ImageMetadataState, ImageMetadataState.asset_id == Asset.id).where(*conditions)
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    if query.sort_by == "position":
        position = DatasetMember.position.desc() if query.order == "desc" else DatasetMember.position.asc()
        ordering = (position, DatasetMember.id.asc())
    else:
        ordering = image_sort(query, identity=DatasetMember.id)
    rows = session.execute(statement.order_by(*ordering).limit(query.limit).offset(query.offset)).all()
    calibrations = member_calibration_projections(session, [(member, asset_version, asset) for member, asset_version, asset, _ in rows])
    return {"items": [{"member": dataset_member_out(session, member, asset_version, asset, calibration_projection=calibrations[member.id]).model_dump(mode="json"),
                       "metadata": deepcopy(state.metadata_json) if state else {}}
                      for member, asset_version, asset, state in rows], "total": total, "limit": query.limit, "offset": query.offset}


def update_image_dataset(session: Session, dataset_id: UUID | str, expected_revision: int, changes: DatasetChanges) -> dict:
    update_dataset(session, UUID(str(dataset_id)), DatasetPatch.model_validate(
        {"base_revision": expected_revision, **changes.model_dump(mode="json", exclude_unset=True)}))
    return get_image_dataset(session, dataset_id)
