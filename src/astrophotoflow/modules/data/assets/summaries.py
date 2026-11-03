"""Typed capture summaries shared by library rows and fixed dataset references."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.engine import RowMapping

from astrophotoflow.contracts.assets import ExposureSummary, LibraryEquipmentLabel, LibraryMetadataSummary, LibraryParameterSummary

STATES = ("consistent", "mixed", "unknown")


def value_summary(row: RowMapping, field: str) -> dict[str, object]:
    state = row[field + "__state"]
    return {"state": STATES[state], "value": row[field + "__value"] if state == 0 else None}


def metadata_summary(row: RowMapping) -> LibraryMetadataSummary:
    equipment = {}
    for slot in ("camera", "optical_system", "filter"):
        state = row[slot + "_summary_state"]
        identity = row[slot + "_id__value"]
        label = LibraryEquipmentLabel(id=UUID(identity) if identity else None, name=row[slot + "_name__value"]) if state == 0 else None
        equipment[slot] = {"state": STATES[state], "value": label}
    return LibraryMetadataSummary(
        classification={"frame_class": value_summary(row, "frame_class"), "frame_type": value_summary(row, "frame_type")},
        parameters=LibraryParameterSummary(**{field: value_summary(row, field) for field in LibraryParameterSummary.model_fields}),
        storage_mode=value_summary(row, "storage_mode"), availability=value_summary(row, "availability"), **equipment,
    )


@dataclass(frozen=True)
class VersionSummaryFacts:
    member_count: int
    input_ready: bool
    summary: LibraryMetadataSummary
    version_number: int | None
    exposure_summary: ExposureSummary
