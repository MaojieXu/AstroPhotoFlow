"""SQL filtering, aggregation, deterministic ordering and pagination of library entries."""

import hashlib

from sqlalchemy import and_, case, func, literal, or_, select
from sqlalchemy.orm import Session

from astrophotoflow.contracts.assets import LibraryChangeState, LibraryItemPage, LibraryQuery
from astrophotoflow.modules.data.assets.exposure import summarize_dataset_exposures
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion, FitsHduMetadata
from astrophotoflow.modules.data.assets.ordering import metadata_order
from astrophotoflow.modules.data.calibration.rows import library_calibration_projections
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember, DatasetVersion
from astrophotoflow.modules.data.imports.models import AssetTask, AssetTaskItem
from astrophotoflow.modules.data.library.projection import library_scopes
from astrophotoflow.modules.data.library.summary import item_summary
from astrophotoflow.modules.data.media.models import Preview
from astrophotoflow.modules.data.media.thumbnail_batches import THUMBNAIL_GROUP_PREFIX
from astrophotoflow.modules.data.trash.models import LibraryEntryRemoval


def get_library_change_state(session: Session) -> LibraryChangeState:
    digest = hashlib.sha256()
    thumbnails = hashlib.sha256()
    statements = (
        select(Asset.id, Asset.revision, Asset.current_version_id).order_by(Asset.id),
        select(Dataset.id, Dataset.revision, Dataset.current_version_id).order_by(Dataset.id),
        select(AssetVersion.id, AssetVersion.availability).order_by(AssetVersion.id),
        select(LibraryEntryRemoval.entry_type, LibraryEntryRemoval.entry_id, LibraryEntryRemoval.cleanup_status,
            LibraryEntryRemoval.removed_at).order_by(LibraryEntryRemoval.entry_type, LibraryEntryRemoval.entry_id),
        select(Preview.id, Preview.status, Preview.storage_path).where(Preview.size.in_(('thumbnail', 'group_thumbnail'))).order_by(Preview.id),
        select(AssetTask.id, AssetTask.status).order_by(AssetTask.id),
    )
    for index, statement in enumerate(statements):
        target = thumbnails if index == 4 else digest
        target.update(str(index).encode())
        for row in session.execute(statement).yield_per(200):
            target.update(repr(tuple(row)).encode())
            target.update(b'\n')
    return LibraryChangeState(revision_token=digest.hexdigest(), thumbnail_token=thumbnails.hexdigest())


def search_library(session: Session, query: LibraryQuery) -> LibraryItemPage:
    entries, members, headers, paged_headers = library_scopes(query)
    total = session.scalar(select(func.count()).select_from(headers)) or 0
    selected = select(entries).order_by(*metadata_order(entries.c, query.sort_by, query.order))
    if not paged_headers:
        selected = selected.limit(query.limit).offset(query.offset)
    page = selected.cte("library_page")
    selected_hdu = select(FitsHduMetadata.hdu_index).where(FitsHduMetadata.asset_version_id == Preview.asset_version_id,
                   FitsHduMetadata.is_selected.is_(True)).limit(1).correlate(Preview).scalar_subquery()
    first_member = select(DatasetMember.asset_version_id).where(
        DatasetMember.dataset_version_id == page.c.version_id).order_by(DatasetMember.position).limit(1).correlate(page).scalar_subquery()
    thumbnail = select(func.json_object("asset_id", members.c.member_asset_id, "asset_version_id", members.c.member_version_id,
                                       "hdu_index", Preview.hdu_index)).select_from(members).join(
        Preview, Preview.asset_version_id == members.c.member_version_id,
    ).where(members.c.entry_type == page.c.entry_type, members.c.id == page.c.id,
            or_(and_(page.c.entry_type == "asset", Preview.size == "thumbnail"),
                and_(page.c.entry_type == "dataset", members.c.member_version_id == first_member,
                     Preview.size == "group_thumbnail", Preview.algorithm_version == literal(THUMBNAIL_GROUP_PREFIX) + first_member)),
            Preview.status == "available", Preview.hdu_index == func.coalesce(selected_hdu, 0))
    thumbnail = thumbnail.order_by(members.c.position.asc(), Preview.created_at.desc(), Preview.id.asc()).limit(1).correlate(page).scalar_subquery()
    failed_states = ("failed", "completed_with_errors")
    dataset_issue = select(AssetTask.id).where(AssetTask.dataset_id == page.c.id, AssetTask.status.in_(failed_states)).limit(1).correlate(page).scalar_subquery()
    asset_issue = select(func.coalesce(AssetTaskItem.error["message"].as_string(), "导入完成，但素材存在错误。")).select_from(AssetTaskItem).join(
        AssetTask, AssetTask.id == AssetTaskItem.task_id,
    ).where(AssetTaskItem.asset_id == page.c.id, AssetTask.status.in_(failed_states), AssetTaskItem.status.in_(failed_states))
    asset_issue = asset_issue.order_by(AssetTask.updated_at.desc(), AssetTaskItem.id.asc()).limit(1).correlate(page).scalar_subquery()
    issue = case((and_(page.c.entry_type == "dataset", dataset_issue.is_not(None)), "导入完成，但部分素材或预览存在错误。"),
                 (page.c.entry_type == "asset", asset_issue))
    asset_number = select(AssetVersion.version_number).where(AssetVersion.id == page.c.version_id).correlate(page).scalar_subquery()
    dataset_number = select(DatasetVersion.version_number).where(DatasetVersion.id == page.c.version_id).correlate(page).scalar_subquery()
    number = case((page.c.entry_type == "dataset", dataset_number), else_=asset_number)
    rows = session.execute(select(*page.c, number.label("version_number"), thumbnail.label("thumbnail_ref"), issue.label("import_issue"))
                           .order_by(*metadata_order(page.c, query.sort_by, query.order))).mappings().all()
    exposures = summarize_dataset_exposures(session, [row['version_id'] for row in rows if row['entry_type'] == 'dataset' and row['version_id']])
    items = [item_summary(row, exposures.get(row['version_id'])) for row in rows]
    calibrations = library_calibration_projections(session, items)
    for item in items:
        item.calibration_projection = calibrations.get(str(item.version_id))
    return LibraryItemPage(items=items, total=total, limit=query.limit, offset=query.offset)
