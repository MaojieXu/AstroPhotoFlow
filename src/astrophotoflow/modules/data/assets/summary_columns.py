from collections.abc import Iterable

from sqlalchemy import and_, case, func, literal, select
from sqlalchemy.sql.selectable import Select

"""Canonical SQL columns for current capture metadata and fixed file facts."""

from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement

from astrophotoflow.contracts.assets import LibraryParameterSummary
from astrophotoflow.modules.data.assets.models import Asset, AssetVersion


def metadata_columns() -> dict[str, ColumnElement | InstrumentedAttribute]:
    result = {field: getattr(Asset, field) for field in LibraryParameterSummary.model_fields}
    result.update(frame_class=Asset.frame_class, frame_type=Asset.frame_type,
                  storage_mode=AssetVersion.storage_mode, availability=AssetVersion.availability)
    for slot in ("camera", "optical_system", "filter"):
        result[slot + "_id"] = getattr(Asset, slot + "_id")
        result[slot + "_name"] = Asset.equipment_snapshot[slot + "_id"]["name"].as_string()
    return result



def aggregate_values(statement: Select, fields: Iterable[str], name: str, *, grouped: bool) -> Select:
    rows = statement.cte(name)
    minimum = func.min if grouped else lambda value: value
    maximum = func.max if grouped else lambda value: value
    count = func.count() if grouped else literal(1)
    matching = func.sum(rows.c.matched) if grouped else rows.c.matched
    columns = [rows.c.entry_type, rows.c.id, count.label("member_count"), matching.label("matching_member_count"),
               minimum(rows.c.ready).label("all_ready"), minimum(rows.c.file_kind).label("min_kind"), maximum(rows.c.file_kind).label("max_kind")]
    for field in fields:
        column = rows.c[field]
        known = func.count(column) if grouped else case((column.is_(None), 0), else_=1)
        state = case((known == 0, 2), (and_(known == count, minimum(column) == maximum(column)), 0), else_=1)
        columns.extend((state.label(field + "__state"), minimum(column).label(field + "__value")))
    result = select(*columns)
    return result.group_by(rows.c.entry_type, rows.c.id) if grouped else result
