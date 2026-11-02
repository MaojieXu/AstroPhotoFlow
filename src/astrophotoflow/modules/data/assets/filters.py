"""SQL predicates for current capture metadata; shared by member and library queries."""

from sqlalchemy import and_, func, or_, true
from sqlalchemy.sql.elements import ColumnElement

from astrophotoflow.contracts.assets import LibraryMemberFilters
from astrophotoflow.modules.data.assets.models import Asset


def member_predicate(query: LibraryMemberFilters) -> ColumnElement[bool]:
    conditions = []
    for field in ("role", "frame_class", "frame_type", "parameter_mode"):
        values = getattr(query, field)
        if values:
            conditions.append(getattr(Asset, field).in_(values))
    for field in ("camera_id", "optical_system_id", "filter_id"):
        values = getattr(query, field)
        if values:
            conditions.append(getattr(Asset, field).in_([str(value) for value in values]))
    if query.binning:
        pairs = [tuple(int(part) for part in value.split("x")) for value in query.binning]
        conditions.append(or_(*(and_(Asset.binning_x == x, Asset.binning_y == y) for x, y in pairs)))
    for prefix, column in (
        ("exposure", Asset.exposure_seconds), ("integration", Asset.integration_seconds),
        ("temperature", func.round(Asset.sensor_temperature_c)), ("iso", Asset.iso),
        ("gain", Asset.gain), ("offset", Asset.offset),
    ):
        low, high = getattr(query, prefix + "_min"), getattr(query, prefix + "_max")
        if low is not None:
            conditions.append(column >= low)
        if high is not None:
            conditions.append(column <= high)
    return and_(*conditions) if conditions else true()
