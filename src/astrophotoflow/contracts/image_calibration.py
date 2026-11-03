"""Explicit calibration intent, fixed consumers, and safe revision-guarded writes."""

from typing import Annotated, Literal

from pydantic import MISSING, Field, field_validator, model_validator

from astrophotoflow.contracts.calibration import CalibrationTarget, CalibrationUnconfigured
from astrophotoflow.contracts.common import JsonObject, PageMetadata, StrictModel, UuidInput
from astrophotoflow.contracts.image_management import ImageName, PageLimit, PageOffset, Revision

CalibrationSlot = Literal["bias", "dark", "flat", "dark_flat"]


class CalibrationInherit(StrictModel):
    mode: Literal["inherit"]


class CalibrationDisabled(StrictModel):
    mode: Literal["disabled"]


class CalibrationFixedTarget(StrictModel):
    mode: Literal["target"]
    target: CalibrationTarget


CalibrationChoice = Annotated[
    CalibrationInherit | CalibrationUnconfigured | CalibrationDisabled | CalibrationFixedTarget,
    Field(discriminator="mode"),
]


class CalibrationPatch(StrictModel):
    bias: CalibrationChoice | MISSING = MISSING
    dark: CalibrationChoice | MISSING = MISSING
    flat: CalibrationChoice | MISSING = MISSING
    dark_flat: CalibrationChoice | MISSING = MISSING

    def forbid_inherit(self):
        if any(choice.mode == "inherit" for choice in self.model_dump_values()):
            raise ValueError("inherit is available only for a dataset member override.")
        return self

    def model_dump_values(self):
        return [getattr(self, slot) for slot in ("bias", "dark", "flat", "dark_flat")
                if getattr(self, slot) is not MISSING]


class MemberCalibrationChange(StrictModel):
    asset_version_id: UuidInput
    changes: CalibrationPatch


class AssetCalibrationConsumer(StrictModel):
    kind: Literal["asset_version"]
    asset_id: UuidInput
    asset_version_id: UuidInput
    binding_version_id: UuidInput | None = None


class DatasetCalibrationConsumer(StrictModel):
    kind: Literal["dataset_version"]
    dataset_id: UuidInput
    dataset_version_id: UuidInput
    member_asset_version_ids: list[UuidInput] | None = Field(default=None, min_length=1)

    @field_validator("member_asset_version_ids")
    @classmethod
    def unique_members(cls, value):
        if value is not None and len(value) != len(set(value)):
            raise ValueError("Member asset versions must be unique.")
        return value


CalibrationConsumer = Annotated[AssetCalibrationConsumer | DatasetCalibrationConsumer, Field(discriminator="kind")]


class CalibrationCheckProposal(StrictModel):
    changes: CalibrationPatch | MISSING = MISSING
    member_changes: list[MemberCalibrationChange] | MISSING = Field(default=MISSING, min_length=1)

    @field_validator("member_changes")
    @classmethod
    def unique_members(cls, value):
        if value is not MISSING:
            ids = [item.asset_version_id for item in value]
            if len(ids) != len(set(ids)):
                raise ValueError("Member asset versions must be unique.")
        return value


class CalibrationSearch(StrictModel):
    text: str | None = None
    target_kind: Literal["master"] | None = None
    limit: PageLimit = 50
    offset: PageOffset = 0


class CalibrationSearchRequest(StrictModel):
    slot: CalibrationSlot
    consumer: CalibrationConsumer | None = None
    query: CalibrationSearch | None = None


class CalibrationCheckRequest(StrictModel):
    consumer: CalibrationConsumer
    proposal: CalibrationCheckProposal | None = None
    limit: PageLimit = 50
    offset: PageOffset = 0


class ImageCalibrationUpdate(StrictModel):
    request_id: UuidInput
    expected_revision: Revision
    base_binding_version_id: UuidInput | None
    changes: CalibrationPatch
    accept_unknown: bool = False

    @model_validator(mode="after")
    def no_inherit(self):
        self.changes.forbid_inherit()
        return self


class DatasetCalibrationUpdate(StrictModel):
    request_id: UuidInput
    expected_revision: Revision
    base_version_id: UuidInput
    changes: CalibrationPatch
    accept_unknown: bool = False

    @model_validator(mode="after")
    def no_inherit(self):
        self.changes.forbid_inherit()
        return self


class DatasetMemberCalibrationUpdate(StrictModel):
    request_id: UuidInput
    expected_revision: Revision
    base_version_id: UuidInput
    members: list[MemberCalibrationChange] = Field(min_length=1)
    accept_unknown: bool = False

    @field_validator("members")
    @classmethod
    def unique_members(cls, value):
        ids = [item.asset_version_id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("Member asset versions must be unique.")
        return value


class DatasetMemberInput(StrictModel):
    asset_version_id: UuidInput
    calibration: CalibrationPatch | MISSING = MISSING


class ImageDatasetCreate(StrictModel):
    request_id: UuidInput
    name: ImageName
    members: list[DatasetMemberInput] = Field(min_length=1)
    calibration_defaults: CalibrationPatch | MISSING = MISSING
    notes: str | None = None
    accept_unknown: bool = False

    @model_validator(mode="after")
    def valid_members(self):
        ids = [item.asset_version_id for item in self.members]
        if len(ids) != len(set(ids)):
            raise ValueError("Member asset versions must be unique.")
        if self.calibration_defaults is not MISSING:
            self.calibration_defaults.forbid_inherit()
        return self


class ImageDatasetEditMembers(StrictModel):
    request_id: UuidInput
    expected_revision: Revision
    base_version_id: UuidInput
    add: list[DatasetMemberInput] | MISSING = Field(default=MISSING, min_length=1)
    remove: list[UuidInput] | MISSING = Field(default=MISSING, min_length=1)
    accept_unknown: bool = False

    @model_validator(mode="after")
    def valid_edits(self):
        added = [] if self.add is MISSING else [item.asset_version_id for item in self.add]
        removed = [] if self.remove is MISSING else self.remove
        if not added and not removed:
            raise ValueError("Specify at least one member to add or remove.")
        if len(added) != len(set(added)) or len(removed) != len(set(removed)):
            raise ValueError("Member edits must be unique.")
        if set(added) & set(removed):
            raise ValueError("Cannot add and remove the same member.")
        return self


class CalibrationTargetDetail(StrictModel):
    target: CalibrationTarget
    asset_id: UuidInput | None = None
    dataset_id: UuidInput | None = None
    name: str
    version_number: int
    target_kind: Literal["master"]
    master_required: Literal[False]


class CalibrationSlotDetail(StrictModel):
    choice: CalibrationChoice
    source: Literal["standalone", "dataset_default", "member_override"]
    status: Literal["unconfigured", "disabled", "target", "not_applicable"]
    target_detail: CalibrationTargetDetail | None = None
    check_state: Literal["not_checked"] = "not_checked"


class CalibrationCombination(StrictModel):
    key: str
    member_count: int = Field(ge=1)
    effective: dict[CalibrationSlot, CalibrationChoice]
    slots: dict[CalibrationSlot, CalibrationSlotDetail]


class ImageCalibrationOut(StrictModel):
    asset_id: UuidInput
    asset_version_id: UuidInput
    asset_revision: Revision
    binding_version_id: UuidInput | None
    version_number: int | None
    bindings: dict[CalibrationSlot, CalibrationChoice]
    slots: dict[CalibrationSlot, CalibrationSlotDetail]
    message: str


class DatasetMemberCalibrationOut(StrictModel):
    asset_id: UuidInput
    asset_name: str
    asset_version_number: int
    frame_type: str | None
    asset_version_id: UuidInput
    overrides: dict[CalibrationSlot, CalibrationChoice]
    effective: dict[CalibrationSlot, CalibrationChoice]
    slots: dict[CalibrationSlot, CalibrationSlotDetail]


class DatasetCalibrationPage(PageMetadata):
    dataset_id: UuidInput
    dataset_version_id: UuidInput
    revision: Revision
    defaults: dict[CalibrationSlot, CalibrationChoice]
    items: list[DatasetMemberCalibrationOut]
    combinations: list[CalibrationCombination]


CalibrationCheckState = Literal["compatible", "unknown", "conflict"]


class CalibrationCheckItem(StrictModel):
    asset_version_id: UuidInput
    slot: CalibrationSlot
    target: CalibrationTarget
    state: CalibrationCheckState
    master_required: Literal[False]
    diagnostics: list[JsonObject]
    binding_source: Literal["standalone", "dataset_default", "member_override", "proposal", "dependency"] = "proposal"
    dependency_path: list[CalibrationTarget] = Field(default_factory=list)
    source_asset_revision: int | None = None
    source_metadata_basis: Literal["current_metadata", "frozen_capture_snapshot"] | None = None
    source_availability: str | None = None
    target_asset_revision: int | None = None
    target_availability: Literal["available", "missing", "changed", "unknown", "mixed"] = "unknown"
    applicable: bool = False


class CalibrationCheckPage(PageMetadata):
    state: CalibrationCheckState
    checked_bindings: int = Field(ge=0)
    conflict_count: int = Field(ge=0)
    unknown_count: int = Field(ge=0)
    master_required_count: int = Field(ge=0)
    items: list[CalibrationCheckItem]


class CalibrationCandidate(StrictModel):
    target: CalibrationTarget
    name: str
    frame_type: CalibrationSlot
    version_number: int
    member_count: int = Field(ge=0)
    target_kind: Literal["master"]
    check: JsonObject | None = None


class CalibrationCandidatePage(PageMetadata):
    items: list[CalibrationCandidate]


class ImageOperationOut(StrictModel):
    request_id: UuidInput
    operation: str
    result: JsonObject
    message: str
