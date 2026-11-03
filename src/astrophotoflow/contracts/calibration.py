from typing import Annotated, Literal

from pydantic import Field

from astrophotoflow.contracts.common import PageMetadata, StrictModel, UuidInput


class CalibrationTarget(StrictModel):
    kind: Literal["asset_version"]
    id: UuidInput


class CalibrationUnconfigured(StrictModel):
    mode: Literal["unconfigured"]


CalibrationBindings = dict[Literal["bias", "dark", "flat", "dark_flat"], CalibrationTarget | CalibrationUnconfigured | None]


class CalibrationTargetOption(StrictModel):
    target: CalibrationTarget
    name: str
    frame_type: Literal["bias", "dark", "flat", "dark_flat"]
    version_number: int
    member_count: int


class CalibrationTargetPage(PageMetadata):
    items: list[CalibrationTargetOption]


class LibraryCalibrationTarget(StrictModel):
    target: CalibrationTarget
    asset_id: UuidInput
    name: str
    version_number: int
    target_kind: Literal["master"] = "master"
    master_required: Literal[False] = False


class LibraryCalibrationDisabled(StrictModel):
    mode: Literal["disabled"]


class LibraryCalibrationFixedTarget(StrictModel):
    mode: Literal["target"]
    target: CalibrationTarget


class LibraryCalibrationSlot(StrictModel):
    choice: Annotated[CalibrationUnconfigured | LibraryCalibrationDisabled | LibraryCalibrationFixedTarget, Field(discriminator="mode")] | None
    source: Literal["standalone", "dataset_default", "member_override", "mixed"]
    status: Literal["unconfigured", "disabled", "target", "not_applicable", "mixed"]
    target_detail: LibraryCalibrationTarget | None = None
    check_state: Literal["not_checked"] = "not_checked"


class LibraryCalibrationProjection(StrictModel):
    slots: dict[Literal["bias", "dark", "flat", "dark_flat"], LibraryCalibrationSlot]
    binding_version_id: UuidInput | None = None
