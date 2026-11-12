"""Read fixed members in SQL pages; never expand the entire dataset."""
from typing import Literal
from uuid import UUID
from sqlalchemy import case, func, literal, select
from sqlalchemy.orm import Session, defer
from astrophotoflow.contracts.datasets import DatasetMemberPage, DatasetMemberQuery, DatasetMemberSummaryPage, DatasetOut, DatasetPage
from astrophotoflow.core.errors import not_found
from astrophotoflow.modules.data.assets.filters import member_predicate
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.assets.ordering import compound_states, metadata_order
from astrophotoflow.modules.data.assets.queries import empty_dataset_summary, summarize_datasets
from astrophotoflow.modules.data.assets.summary_columns import metadata_columns
from astrophotoflow.modules.data.datasets.mapping import dataset_member_out, dataset_out
from astrophotoflow.modules.data.datasets.member_summaries import member_summaries
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember

def list_dataset_members(session: Session, dataset_id: UUID, query: DatasetMemberQuery, *, summaries: bool=False) -> DatasetMemberPage | DatasetMemberSummaryPage:
    fixed_id = session.scalar(select(Dataset.id).where(Dataset.id == str(dataset_id)))
    if fixed_id is None:
        raise not_found()
    scope = DatasetMember.dataset_id == fixed_id
    predicate = member_predicate(query, fixed_dataset=True)
    if query.q:
        predicate = predicate & Asset.name_search_key.contains(query.q.casefold(), autoescape=True)
    total = session.scalar(select(func.count()).select_from(DatasetMember).outerjoin(Asset, Asset.id == DatasetMember.asset_id).where(scope, predicate)) or 0
    statement = select(DatasetMember, Asset).select_from(DatasetMember).outerjoin(Asset, Asset.id == DatasetMember.asset_id)
    if query.sort_by == 'position':
        column = DatasetMember.position
        read = statement.where(scope, predicate).order_by(column.desc() if query.order == 'desc' else column.asc(), DatasetMember.id.asc()).limit(query.limit).offset(query.offset)
    else:
        columns = [DatasetMember.id.label('id'), literal('asset').label('entry_type'), Asset.name_search_key, Asset.created_at, Asset.status, Asset.notes]
        for name, column in metadata_columns(fixed_dataset=True).items():
            columns.extend((case((column.is_(None), 2), else_=0).label(name + '__state'), column.label(name + '__value')))
        values = statement.with_only_columns(*columns, maintain_column_froms=True).where(scope, predicate).cte('member_sort_values')
        keys = select(*values.c, *(expression.label(name) for name, expression in compound_states(values.c).items())).cte('member_sort_keys')
        page = select(keys).order_by(*metadata_order(keys.c, query.sort_by, query.order)).limit(query.limit).offset(query.offset).cte('member_page')
        read = statement.join(page, page.c.id == DatasetMember.id).order_by(*metadata_order(page.c, query.sort_by, query.order))
    if summaries:
        read = read.options(defer(Asset.capture_snapshot, raiseload=True), defer(Asset.scientific_metadata, raiseload=True), defer(Asset.equipment_snapshot, raiseload=True), defer(Asset.value_sources, raiseload=True)).add_columns(*(Asset.equipment_snapshot[slot + '_id']['name'].as_string() for slot in ('camera', 'optical_system', 'filter')))
    rows = session.execute(read).all()
    if summaries:
        return DatasetMemberSummaryPage(items=member_summaries(session, str(dataset_id), rows), total=total, limit=query.limit, offset=query.offset)
    return DatasetMemberPage(items=[dataset_member_out(session, member, asset) for member, asset in rows], total=total, limit=query.limit, offset=query.offset)

def list_datasets(session: Session, limit: int=50, offset: int=0, sort_by: Literal['created_at', 'name']='created_at', order: Literal['asc', 'desc']='desc', q: str | None=None, status: Literal['active', 'archived', 'all']='active') -> DatasetPage:
    from astrophotoflow.modules.data.assets.visibility import not_removed
    filters = [not_removed('dataset', Dataset.id)]
    if status != 'all':
        filters.append(Dataset.status == status)
    if q:
        filters.append(Dataset.name_search_key.contains(q.casefold(), autoescape=True))
    total = session.scalar(select(func.count()).select_from(Dataset).where(*filters)) or 0
    column = Dataset.name_search_key if sort_by == 'name' else Dataset.created_at
    rows = session.scalars(select(Dataset).where(*filters).order_by(column.desc() if order == 'desc' else column.asc(), Dataset.id.asc()).limit(limit).offset(offset)).all()
    facts = summarize_datasets(session, [row.id for row in rows if row.id])
    return DatasetPage(items=[dataset_out(session, row, facts[row.id] if row.id else empty_dataset_summary()) for row in rows], total=total, limit=limit, offset=offset)

def get_dataset(session: Session, dataset_id: UUID) -> DatasetOut:
    dataset = session.get(Dataset, str(dataset_id))
    if dataset is None:
        raise not_found()
    return dataset_out(session, dataset)
