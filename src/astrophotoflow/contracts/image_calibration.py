"""Explicit calibration intent, fixed consumers, and safe revision-guarded writes."""
from typing import Annotated, Literal
from pydantic import MISSING, Field, field_validator, model_validator
from astrophotoflow.contracts.calibration import CalibrationTarget, CalibrationUnconfigured
from astrophotoflow.contracts.common import JsonObject, PageMetadata, StrictModel, UuidInput
from astrophotoflow.contracts.image_management import ImageName, PageLimit, PageOffset, Revision
CalibrationSlot = Literal['bias', 'dark', 'flat', 'dark_flat']

class CalibrationDisabled(StrictModel):
    mode: Literal['disabled']

class CalibrationFixedTarget(StrictModel):
    mode: Literal['target']
    target: CalibrationTarget
CalibrationChoice = Annotated[CalibrationUnconfigured | CalibrationDisabled | CalibrationFixedTarget, Field(discriminator='mode')]

class CalibrationPatch(StrictModel):
    bias: CalibrationChoice | MISSING = MISSING
    dark: CalibrationChoice | MISSING = MISSING
    flat: CalibrationChoice | MISSING = MISSING
    dark_flat: CalibrationChoice | MISSING = MISSING

class AssetCalibrationConsumer(StrictModel):
    kind: Literal['asset']
    asset_id: UuidInput

class DatasetCalibrationConsumer(StrictModel):
    kind: Literal['dataset']
    dataset_id: UuidInput
    member_asset_ids: list[UuidInput] | None = Field(default=None, min_length=1)

    @field_validator('member_asset_ids')
    @classmethod
    def unique_members(cls, value):
        if value is not None and len(value) != len(set(value)):
            raise ValueError('Member asset IDs must be unique.')
        return value
CalibrationConsumer = Annotated[AssetCalibrationConsumer | DatasetCalibrationConsumer, Field(discriminator='kind')]

class CalibrationCheckProposal(StrictModel):
    changes: CalibrationPatch | MISSING = MISSING

class CalibrationSearch(StrictModel):
    text: str | None = None
    target_kind: Literal['master'] | None = None
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
    changes: CalibrationPatch
    accept_unknown: bool = False

class DatasetCalibrationUpdate(StrictModel):
    request_id: UuidInput
    expected_revision: Revision
    changes: CalibrationPatch
    accept_unknown: bool = False

class DatasetMemberInput(StrictModel):
    asset_id: UuidInput

class ImageDatasetCreate(StrictModel):
    project_id: UuidInput | None = None
    project_base_revision: Revision | None = None
    request_id: UuidInput
    name: ImageName
    members: list[DatasetMemberInput] = Field(min_length=1)
    calibration: CalibrationPatch | MISSING = MISSING
    notes: str | None = None
    accept_unknown: bool = False

    @model_validator(mode='after')
    def valid_members(self):
        if (self.project_id is None) != (self.project_base_revision is None):
            raise ValueError('Project association requires both project_id and project_base_revision.')
        ids = [item.asset_id for item in self.members]
        if len(ids) != len(set(ids)):
            raise ValueError('Member asset IDs must be unique.')
        return self

class ImageDatasetEditMembers(StrictModel):
    request_id: UuidInput
    expected_revision: Revision
    add: list[DatasetMemberInput] | MISSING = Field(default=MISSING, min_length=1)
    remove: list[UuidInput] | MISSING = Field(default=MISSING, min_length=1)
    accept_unknown: bool = False

    @model_validator(mode='after')
    def valid_edits(self):
        added = [] if self.add is MISSING else [item.asset_id for item in self.add]
        removed = [] if self.remove is MISSING else self.remove
        if not added and (not removed):
            raise ValueError('Specify at least one member to add or remove.')
        if len(added) != len(set(added)) or len(removed) != len(set(removed)):
            raise ValueError('Member edits must be unique.')
        if set(added) & set(removed):
            raise ValueError('Cannot add and remove the same member.')
        return self

class CalibrationTargetDetail(StrictModel):
    in_trash: bool = False
    target: CalibrationTarget
    asset_id: UuidInput | None = None
    dataset_id: UuidInput | None = None
    name: str
    target_kind: Literal['master']
    master_required: Literal[False]

class CalibrationSlotDetail(StrictModel):
    choice: CalibrationChoice
    source: Literal['standalone', 'dataset']
    status: Literal['unconfigured', 'disabled', 'target', 'not_applicable']
    target_detail: CalibrationTargetDetail | None = None
    check_state: Literal['not_checked'] = 'not_checked'

class ImageCalibrationOut(StrictModel):
    diagnostics: list[JsonObject] = Field(default_factory=list)
    asset_id: UuidInput
    asset_revision: Revision
    bindings: dict[CalibrationSlot, CalibrationChoice]
    slots: dict[CalibrationSlot, CalibrationSlotDetail]
    message: str

class DatasetCalibrationOut(StrictModel):
    diagnostics: list[JsonObject] = Field(default_factory=list)
    dataset_id: UuidInput
    revision: Revision
    calibration: dict[CalibrationSlot, CalibrationChoice]
    slots: dict[CalibrationSlot, CalibrationSlotDetail]
CalibrationCheckState = Literal['compatible', 'warning', 'unknown', 'conflict']

class CalibrationCheckItem(StrictModel):
    asset_id: UuidInput
    slot: CalibrationSlot
    target: CalibrationTarget
    state: CalibrationCheckState
    master_required: Literal[False]
    diagnostics: list[JsonObject]
    binding_source: Literal['standalone', 'dataset', 'proposal', 'dependency'] = 'proposal'
    dependency_path: list[CalibrationTarget] = Field(default_factory=list)
    source_asset_revision: int | None = None
    source_metadata_basis: Literal['current_metadata', 'frozen_capture_snapshot'] | None = None
    source_availability: str | None = None
    target_asset_revision: int | None = None
    target_availability: Literal['available', 'missing', 'changed', 'unknown', 'mixed'] = 'unknown'
    applicable: bool = False

class CalibrationCheckPage(PageMetadata):
    state: CalibrationCheckState
    checked_bindings: int = Field(ge=0)
    conflict_count: int = Field(ge=0)
    unknown_count: int = Field(ge=0)
    warning_count: int = Field(default=0, ge=0)
    master_required_count: int = Field(ge=0)
    items: list[CalibrationCheckItem]

class CalibrationCandidate(StrictModel):
    target: CalibrationTarget
    name: str
    frame_type: CalibrationSlot
    member_count: int = Field(ge=0)
    target_kind: Literal['master']
    check: JsonObject | None = None

class CalibrationCandidatePage(PageMetadata):
    items: list[CalibrationCandidate]

class ImageOperationOut(StrictModel):
    request_id: UuidInput
    operation: str
    result: JsonObject
    message: str
