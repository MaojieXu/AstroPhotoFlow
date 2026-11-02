"""SQL scopes keep single-asset values separate from dataset aggregation."""

from sqlalchemy import Integer, and_, case, func, literal, or_, select, union_all
from sqlalchemy.sql.selectable import CTE, Select

from astrophotoflow.contracts.assets import LibraryQuery
from astrophotoflow.modules.data.assets.filters import member_predicate
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion
from astrophotoflow.modules.data.assets.ordering import compound_states, metadata_order
from astrophotoflow.modules.data.assets.summary_columns import aggregate_values, metadata_columns
from astrophotoflow.modules.data.assets.visibility import standalone_asset_ids, visible_dataset, visible_members
from astrophotoflow.modules.data.datasets.models import Dataset


def member_references(asset_rows: Select, dataset_rows: Select, name: str) -> CTE:
    fields = ("entry_type", "id", "position", "member_asset_id", "member_version_id", "member_name_key", "matched")
    return union_all(*(rows.with_only_columns(*(rows.selected_columns[field] for field in fields), maintain_column_froms=True)
                       for rows in (asset_rows, dataset_rows))).cte(name)


def library_scopes(query: LibraryQuery) -> tuple[CTE, CTE, CTE, bool]:
    grouped = visible_members()
    standalone = standalone_asset_ids(grouped)
    fields = metadata_columns()
    ready = and_(Asset.scope == "shared", Asset.status == "active", AssetVersion.availability == "available",
                 AssetVersion.content_hash.is_not(None), AssetVersion.content_hash != "", AssetVersion.byte_size.is_not(None))

    def member_columns(kind, identity, position):
        return [literal(kind).label("entry_type"), identity.label("id"), position.cast(Integer).label("position"),
                Asset.id.label("member_asset_id"), AssetVersion.id.label("member_version_id"),
                Asset.name_search_key.label("member_name_key"), case((ready, 1), else_=0).label("ready"),
                case((AssetVersion.scientific_metadata["format"].as_string() == "other", 1), else_=0).label("file_kind"),
                case((member_predicate(query), 1), else_=0).label("matched"),
                *(column.label(field) for field, column in fields.items())]

    version_join = and_(AssetVersion.id == Asset.current_version_id, AssetVersion.asset_id == Asset.id)
    asset_rows = select(*member_columns("asset", Asset.id, literal(0))).select_from(Asset).outerjoin(
        AssetVersion, version_join,
    ).where(standalone.whereclause)
    dataset_rows = select(*member_columns("dataset", grouped.c.dataset_id, grouped.c.position)).select_from(grouped).join(
        Asset, Asset.id == grouped.c.asset_id,
    ).join(AssetVersion, AssetVersion.id == grouped.c.version_id)
    references = member_references(asset_rows, dataset_rows, "library_filter_members")
    asset_headers = select(literal("asset").label("entry_type"), Asset.id, Asset.name, Asset.name_search_key,
                           Asset.notes, Asset.status, Asset.revision, Asset.created_at,
                           Asset.current_version_id.label("version_id")).where(standalone.whereclause)
    dataset_headers = select(literal("dataset").label("entry_type"), Dataset.id, Dataset.name, Dataset.name_search_key,
                             Dataset.notes, Dataset.status, Dataset.revision, Dataset.created_at,
                             Dataset.current_version_id.label("version_id")).where(visible_dataset())
    headers = union_all(asset_headers, dataset_headers).cte("library_headers")
    has_filters = any(bool(value) if isinstance(value, list) else value is not None for value in
                      query.model_dump(exclude={"q", "limit", "offset", "sort_by", "order"}).values())
    filtered = select(headers)
    if has_filters:
        matched = select(1).select_from(references).where(references.c.entry_type == headers.c.entry_type,
                    references.c.id == headers.c.id, references.c.matched == 1).exists()
        filtered = filtered.where(matched)
    if query.q:
        member_name = select(1).select_from(references).where(references.c.entry_type == headers.c.entry_type,
                        references.c.id == headers.c.id, references.c.member_name_key.contains(query.q.casefold(), autoescape=True)).exists()
        filtered = filtered.where(or_(headers.c.name_search_key.contains(query.q.casefold(), autoescape=True), member_name))
    eligible_headers = filtered.cte("library_filtered_headers")
    paged_headers = query.sort_by in {"created_at", "name", "status", "notes"}
    headers = select(eligible_headers).order_by(*metadata_order(eligible_headers.c, query.sort_by, query.order)).limit(query.limit).offset(query.offset).cte("library_selected_headers") if paged_headers else eligible_headers
    if paged_headers or has_filters or query.q:
        asset_rows = asset_rows.join(headers, and_(headers.c.entry_type == "asset", headers.c.id == Asset.id))
        dataset_rows = dataset_rows.join(headers, and_(headers.c.entry_type == "dataset", headers.c.id == grouped.c.dataset_id))
    aggregate = union_all(aggregate_values(asset_rows, fields, "library_asset_values", grouped=False),
                          aggregate_values(dataset_rows, fields, "library_dataset_values", grouped=True)).cte("library_aggregates")
    metadata = []
    for field in fields:
        metadata.extend((func.coalesce(aggregate.c[field + "__state"], 2).label(field + "__state"), aggregate.c[field + "__value"]))
    values = select(*headers.c, func.coalesce(aggregate.c.member_count, 0).label("member_count"),
                    func.coalesce(aggregate.c.matching_member_count, 0).label("matching_member_count"),
                    case((and_(aggregate.c.member_count > 0, aggregate.c.all_ready == 1, aggregate.c.min_kind == aggregate.c.max_kind), True), else_=False).label("input_ready"),
                    *metadata).select_from(headers).outerjoin(aggregate, and_(aggregate.c.entry_type == headers.c.entry_type, aggregate.c.id == headers.c.id)).cte("library_entry_values")
    entries = select(*values.c, *(expression.label(name) for name, expression in compound_states(values.c).items())).cte("library_entries")
    return entries, member_references(asset_rows, dataset_rows, "library_thumbnail_members"), eligible_headers, paged_headers
