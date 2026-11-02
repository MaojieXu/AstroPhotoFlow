from astrophotoflow.modules.data.assets.ordering import compound_states
from astrophotoflow.modules.data.assets.summaries import VersionSummaryFacts, metadata_summary
from astrophotoflow.modules.data.assets.summary_columns import aggregate_values, metadata_columns
from astrophotoflow.modules.data.datasets.models import DatasetMember, DatasetVersion

"""SQL metadata projections; no ORM materialization or full-member DTOs."""

from uuid import UUID

from sqlalchemy import and_, case, func, literal, select
from sqlalchemy.orm import Session

from astrophotoflow.contracts.assets import AssetPage, AssetQuery, FilterEquipmentOption, LibraryFilterOptions, NumericRangeOut
from astrophotoflow.modules.data.assets.mapping import asset_out
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion
from astrophotoflow.modules.data.assets.visibility import visible_asset_ids


def get_filter_options(session: Session) -> LibraryFilterOptions:
    visible = visible_asset_ids()
    scope = Asset.id.in_(select(visible.c.asset_id))

    def values(column) -> list[str]:
        return list(session.scalars(select(column).where(scope, column.is_not(None)).distinct().order_by(column.asc())))

    equipment = {}
    for key in ("camera_id", "optical_system_id", "filter_id"):
        identity = getattr(Asset, key)
        snapshot_name = Asset.equipment_snapshot[key]["name"].as_string()
        labels = {}
        rows = session.execute(select(identity, snapshot_name).where(scope, identity.is_not(None)).distinct())
        for record_id, label in rows:
            if label is None:
                raise RuntimeError("Referenced equipment lacks a recorded name")
            labels.setdefault(record_id, set()).add(label)
        options = [FilterEquipmentOption(id=UUID(record_id), name=" / ".join(sorted(names, key=lambda value: (value.casefold(), value))))
                   for record_id, names in labels.items()]
        equipment[key] = sorted(options, key=lambda option: (option.name.casefold(), str(option.id)))

    columns = [Asset.exposure_seconds, Asset.integration_seconds, func.round(Asset.sensor_temperature_c),
               Asset.iso, Asset.gain, Asset.offset]
    extrema = session.execute(select(*(expression for column in columns for expression in (func.min(column), func.max(column))))
                              .where(scope)).one()
    numeric_ranges = {}
    for index, key in enumerate(("exposure_seconds", "integration_seconds", "sensor_temperature_c", "iso", "gain", "offset")):
        low, high = extrema[index * 2:index * 2 + 2]
        if low is not None:
            numeric_ranges[key] = NumericRangeOut(min=low, max=high)
    pairs = session.execute(select(Asset.binning_x, Asset.binning_y).where(
        scope, Asset.binning_x.is_not(None), Asset.binning_y.is_not(None),
    ).distinct())
    return LibraryFilterOptions(
        frame_classes=values(Asset.frame_class), frame_types=values(Asset.frame_type), roles=values(Asset.role),
        parameter_modes=values(Asset.parameter_mode), bin_values=sorted(f"{x}x{y}" for x, y in pairs),
        equipment=equipment, numeric_ranges=numeric_ranges,
    )


def list_assets(session: Session, query: AssetQuery) -> AssetPage:
    conditions = [Asset.scope == "shared"]
    if query.q:
        conditions.append(Asset.name_search_key.contains(query.q.casefold(), autoescape=True))
    if query.status != "all":
        conditions.append(Asset.status == query.status)
    if query.role:
        conditions.append(Asset.role == query.role)
    for field in ("frame_type", "camera_id", "optical_system_id", "filter_id"):
        value = getattr(query, field)
        if value is not None:
            conditions.append(getattr(Asset, field) == (str(value) if isinstance(value, UUID) else value))
    if query.calibration_level is not None:
        conditions.extend((Asset.role == "calibration", Asset.frame_class == ("masterframe" if query.calibration_level == "master" else "subframe")))
    version_join = and_(AssetVersion.id == Asset.current_version_id, AssetVersion.asset_id == Asset.id)
    total = session.scalar(select(func.count()).select_from(Asset).outerjoin(AssetVersion, version_join).where(*conditions)) or 0
    column = Asset.name_search_key if query.sort_by == "name" else Asset.created_at
    rows = session.scalars(select(Asset).outerjoin(AssetVersion, version_join).where(*conditions)
                           .order_by(column.desc() if query.order == "desc" else column.asc(), Asset.id.asc())
                           .limit(query.limit).offset(query.offset))
    return AssetPage(items=[asset_out(session, row) for row in rows], total=total, limit=query.limit, offset=query.offset)


def summarize_dataset_versions(session: Session, version_ids: list[str]) -> dict[str, VersionSummaryFacts]:
    if not version_ids:
        return {}
    fields = metadata_columns()
    ready = and_(Asset.scope == "shared", Asset.status == "active", AssetVersion.availability == "available",
                 AssetVersion.content_hash.is_not(None), AssetVersion.content_hash != "", AssetVersion.byte_size.is_not(None))
    source = select(literal("dataset").label("entry_type"), DatasetMember.dataset_version_id.label("id"),
                    case((ready, 1), else_=0).label("ready"), literal(1).label("matched"),
                    case((AssetVersion.scientific_metadata["format"].as_string() == "other", 1), else_=0).label("file_kind"),
                    *(column.label(name) for name, column in fields.items())).select_from(DatasetMember).join(
        AssetVersion, AssetVersion.id == DatasetMember.asset_version_id,
    ).join(Asset, Asset.id == AssetVersion.asset_id).where(DatasetMember.dataset_version_id.in_(version_ids))
    aggregate = aggregate_values(source, fields, "fixed_member_values", grouped=True).cte("fixed_metadata")
    columns = [DatasetVersion.id, DatasetVersion.version_number, func.coalesce(aggregate.c.member_count, 0).label("member_count"),
               case((and_(aggregate.c.member_count > 0, aggregate.c.all_ready == 1, aggregate.c.min_kind == aggregate.c.max_kind), True), else_=False).label("input_ready")]
    for field in fields:
        columns.extend((func.coalesce(aggregate.c[field + "__state"], 2).label(field + "__state"), aggregate.c[field + "__value"]))
    values = select(*columns).select_from(DatasetVersion).outerjoin(aggregate, aggregate.c.id == DatasetVersion.id).where(
        DatasetVersion.id.in_(version_ids)).cte("fixed_summary_values")
    rows = session.execute(select(*values.c, *(expression.label(name) for name, expression in compound_states(values.c).items()))).mappings()
    return {row["id"]: VersionSummaryFacts(row["member_count"], bool(row["input_ready"]), metadata_summary(row), row["version_number"]) for row in rows}


def empty_version_summary() -> VersionSummaryFacts:
    fields = metadata_columns()
    values = {field + "__state": 2 for field in fields}
    values.update({field + "__value": None for field in fields})
    values.update({slot + "_summary_state": 2 for slot in ("camera", "optical_system", "filter")})
    return VersionSummaryFacts(0, False, metadata_summary(values), None)
