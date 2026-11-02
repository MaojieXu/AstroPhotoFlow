from typing import Literal

from astrophotoflow.contracts.common import PageMetadata, StrictModel, UuidInput


class CalibrationTarget(StrictModel):
    kind: Literal["asset_version", "dataset_version"]
    id: UuidInput


CalibrationBindings = dict[Literal["bias", "dark", "flat", "dark_flat"], CalibrationTarget | None]


class CalibrationTargetOption(StrictModel):
    target: CalibrationTarget
    name: str
    frame_type: Literal["bias", "dark", "flat", "dark_flat"]
    version_number: int
    member_count: int


class CalibrationTargetPage(PageMetadata):
    items: list[CalibrationTargetOption]
