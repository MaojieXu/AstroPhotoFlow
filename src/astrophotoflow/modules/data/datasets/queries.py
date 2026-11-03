"""Read fixed members in SQL pages; never expand the entire dataset."""

from typing import Literal
from uuid import UUID

from sqlalchemy import case, func, literal, select
from sqlalchemy.orm import Session, defer

from astrophotoflow.contracts.datasets import (
    DatasetMemberPage,
    DatasetMemberQuery,
    DatasetMemberSummaryPage,
    DatasetOut,
    DatasetPage,
    DatasetVersionOut,
    DatasetVersionPage,
)
from astrophotoflow.core.errors import not_found
from astrophotoflow.modules.data.assets.exposure import summarize_dataset_exposures
from astrophotoflow.modules.data.assets.filters import member_predicate
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion
from astrophotoflow.modules.data.assets.ordering import compound_states, metadata_order
from astrophotoflow.modules.data.assets.queries import empty_version_summary, summarize_dataset_versions
from astrophotoflow.modules.data.assets.summary_columns import metadata_columns
from astrophotoflow.modules.data.calibration.rows import member_calibration_projections
from astrophotoflow.modules.data.datasets.mapping import dataset_member_out, dataset_out, dataset_version_out, dataset_version_summary
from astrophotoflow.modules.data.datasets.member_summaries import member_summaries
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember, DatasetVersion


def list_dataset_members(
    session: Session,
    dataset_id: UUID,
    version_id: UUID,
    query: DatasetMemberQuery,
    *, summaries: bool = False,
) -> DatasetMemberPage | DatasetMemberSummaryPage:
    fixed_id = session.scalar(select(DatasetVersion.id).join(Dataset, Dataset.id == DatasetVersion.dataset_id)
                              .where(Dataset.id == str(dataset_id), DatasetVersion.id == str(version_id)))
    if fixed_id is None:
        raise not_found()
    scope = DatasetMember.dataset_version_id == fixed_id
    predicate = member_predicate(query)
    if query.q:
        predicate = predicate & Asset.name_search_key.contains(query.q.casefold(), autoescape=True)
    total = session.scalar(select(func.count()).select_from(DatasetMember)
                           .outerjoin(AssetVersion, AssetVersion.id == DatasetMember.asset_version_id)
                           .outerjoin(Asset, Asset.id == AssetVersion.asset_id).where(scope, predicate)) or 0
    statement = select(DatasetMember, AssetVersion, Asset).select_from(DatasetMember).outerjoin(
        AssetVersion, AssetVersion.id == DatasetMember.asset_version_id,
    ).outerjoin(Asset, Asset.id == AssetVersion.asset_id)
    if query.sort_by == "position":
        column = DatasetMember.position
        read = (statement.where(scope, predicate)
                               .order_by(column.desc() if query.order == "desc" else column.asc(), DatasetMember.id.asc())
                               .limit(query.limit).offset(query.offset))
    else:
        columns = [DatasetMember.id.label("id"), literal("asset").label("entry_type"), Asset.name_search_key,
                   Asset.created_at, Asset.status, Asset.notes]
        for name, column in metadata_columns().items():
            columns.extend((case((column.is_(None), 2), else_=0).label(name + "__state"), column.label(name + "__value")))
        values = statement.with_only_columns(*columns, maintain_column_froms=True).where(scope, predicate).cte("member_sort_values")
        keys = select(*values.c, *(expression.label(name) for name, expression in compound_states(values.c).items())).cte("member_sort_keys")
        page = select(keys).order_by(*metadata_order(keys.c, query.sort_by, query.order)).limit(query.limit).offset(query.offset).cte("member_page")
        read = statement.join(page, page.c.id == DatasetMember.id).order_by(*metadata_order(page.c, query.sort_by, query.order))
    if summaries:
        read = read.options(defer(AssetVersion.capture_snapshot, raiseload=True),
            defer(AssetVersion.scientific_metadata, raiseload=True), defer(Asset.equipment_snapshot, raiseload=True),
            defer(Asset.value_sources, raiseload=True)).add_columns(*(
                Asset.equipment_snapshot[slot + '_id']['name'].as_string() for slot in ('camera', 'optical_system', 'filter')))
    rows = session.execute(read).all()
    calibrations = member_calibration_projections(session, [tuple(row[:3]) for row in rows])
    if summaries:
        return DatasetMemberSummaryPage(items=member_summaries(session, str(dataset_id), fixed_id, rows, calibrations),
            total=total, limit=query.limit, offset=query.offset)
    return DatasetMemberPage(
        items=[dataset_member_out(session, member, version, asset, calibration_projection=calibrations[member.id]) for member, version, asset in rows],
        total=total, limit=query.limit, offset=query.offset,
    )


def list_datasets(session: Session, limit: int=50, offset: int=0, sort_by: Literal['created_at', 'name']='created_at', order: Literal['asc', 'desc']='desc', q: str | None=None, status: Literal['active', 'archived', 'all']='active') -> DatasetPage:
    filters = [] if status == 'all' else [Dataset.status == status]
    if q:
        filters.append(Dataset.name_search_key.contains(q.casefold(), autoescape=True))
    total = session.scalar(select(func.count()).select_from(Dataset).where(*filters)) or 0
    column = Dataset.name_search_key if sort_by == 'name' else Dataset.created_at
    rows = session.scalars(select(Dataset).where(*filters).order_by(column.desc() if order == 'desc' else column.asc(), Dataset.id.asc()).limit(limit).offset(offset)).all()
    facts = summarize_dataset_versions(session, [row.current_version_id for row in rows if row.current_version_id])
    return DatasetPage(items=[dataset_out(session, row, facts[row.current_version_id] if row.current_version_id else empty_version_summary()) for row in rows], total=total, limit=limit, offset=offset)

def get_dataset(session: Session, dataset_id: UUID) -> DatasetOut:
    dataset = session.get(Dataset, str(dataset_id))
    if dataset is None:
        raise not_found()
    return dataset_out(session, dataset)

def list_dataset_versions(session: Session, dataset_id: UUID, limit: int=50, offset: int=0) -> DatasetVersionPage:
    dataset = session.get(Dataset, str(dataset_id))
    if dataset is None:
        raise not_found()
    total = session.scalar(select(func.count()).select_from(DatasetVersion).where(DatasetVersion.dataset_id == dataset.id)) or 0
    rows = session.scalars(select(DatasetVersion).where(DatasetVersion.dataset_id == dataset.id).order_by(DatasetVersion.version_number.desc()).limit(limit).offset(offset)).all()
    exposures = summarize_dataset_exposures(session, [row.id for row in rows], frozen=True)
    return DatasetVersionPage(items=[dataset_version_summary(session, row, exposures[row.id]) for row in rows], total=total, limit=limit, offset=offset)

def get_dataset_version(session: Session, dataset_id: UUID, version_id: UUID) -> DatasetVersionOut:
    dataset = session.get(Dataset, str(dataset_id))
    version = session.get(DatasetVersion, str(version_id))
    if dataset is None or version is None or version.dataset_id != dataset.id:
        raise not_found()
    return dataset_version_out(session, version)
