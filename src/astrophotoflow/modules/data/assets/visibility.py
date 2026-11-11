"""SQL visibility for library metadata and fixed member grouping."""
from sqlalchemy import exists, func, select, union
from sqlalchemy.sql import ColumnElement
from sqlalchemy.sql.selectable import CTE, Select
from astrophotoflow.modules.data.assets.models import Asset
from astrophotoflow.modules.data.datasets.models import Dataset, DatasetMember
from astrophotoflow.modules.data.trash.models import LibraryEntryRemoval

def not_removed(entry_type: str, identity: ColumnElement) -> ColumnElement[bool]:
    return ~exists(select(1).select_from(LibraryEntryRemoval).where(LibraryEntryRemoval.entry_type == entry_type, LibraryEntryRemoval.entry_id == identity))

def visible_dataset() -> ColumnElement[bool]:
    return (Dataset.status == 'active') & not_removed('dataset', Dataset.id)

def visible_members() -> CTE:
    return select(Dataset.id.label('dataset_id'), Asset.id.label('asset_id'), DatasetMember.position.label('position')).select_from(Dataset).join(DatasetMember, DatasetMember.dataset_id == Dataset.id).join(Asset, Asset.id == DatasetMember.asset_id).where(visible_dataset(), not_removed('asset', Asset.id)).cte('visible_library_members').prefix_with('MATERIALIZED')

def standalone_asset_ids(members: CTE) -> Select:
    frozen_members = func.json_each(LibraryEntryRemoval.member_asset_ids).table_valued('value', joins_implicitly=True)
    frozen_ids = select(frozen_members.c.value).select_from(LibraryEntryRemoval, frozen_members).where(LibraryEntryRemoval.entry_type == 'dataset', frozen_members.c.value.is_not(None))
    return select(Asset.id.label('asset_id')).where(Asset.scope == 'shared', Asset.status == 'active', not_removed('asset', Asset.id), Asset.id.not_in(select(members.c.asset_id)), Asset.id.not_in(frozen_ids))

def visible_asset_ids() -> CTE:
    members = visible_members()
    return union(select(members.c.asset_id), standalone_asset_ids(members)).cte('visible_library_assets')
