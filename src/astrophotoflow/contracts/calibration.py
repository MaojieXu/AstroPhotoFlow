from astrophotoflow.contracts.common import StrictModel, UuidInput
from typing import Literal


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


class CalibrationTargetPage(StrictModel):
    items: list[CalibrationTargetOption]
    total: int
    limit: int
    offset: int
