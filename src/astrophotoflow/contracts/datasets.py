from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import Field, field_validator, model_validator
from astrophotoflow.contracts.assets import AssetOut, ExposureSummary, LibraryAssetSummary, LibraryMemberFilters, LibraryMetadataSummary, LibrarySortKey
from astrophotoflow.contracts.calibration import CalibrationBindings
from astrophotoflow.contracts.common import PageMetadata, StrictModel, UuidInput, check_name
from astrophotoflow.contracts.metadata import AssetClassification, AssetParametersPatch

from astrophotoflow.contracts.calibration_status import CalibrationSummary

class CaptureEquipmentIdentity(StrictModel):
    id: str | None = None
    name: str | None = None
    optical_accessory_id: str | None = None
    effective_focal_length_mm: float | None = None


class CaptureDifferenceMember(StrictModel):
    asset_id: UuidInput
    value: str | float | int | None | CaptureEquipmentIdentity


class CaptureWarning(StrictModel):
    code: str
    field: str
    severity: Literal['warning']
    members: list[CaptureDifferenceMember]


class CaptureDiagnostics(StrictModel):
    warnings: list[CaptureWarning] = Field(default_factory=list)
    unknown_counts: dict[str, int] = Field(default_factory=dict)


class ReferencingProject(StrictModel):
    id: UuidInput
    name: str


class DatasetOut(CalibrationSummary):
    in_trash: bool = False
    capture_diagnostics: CaptureDiagnostics = Field(default_factory=CaptureDiagnostics)
    referencing_projects: list[ReferencingProject] = Field(default_factory=list)
    summary: LibraryMetadataSummary
    exposure_summary: ExposureSummary
    input_ready: bool
    id: UUID
    name: str
    notes: str | None
    status: Literal['active', 'archived']
    revision: int
    member_count: int
    library_directory: str | None = None
    manifest_status: Literal['pending', 'ready', 'failed'] = 'pending'
    manifest_error: str | None = None
    created_at: datetime
    calibration: CalibrationBindings = Field(default_factory=dict)
    updated_at: datetime

class DatasetMemberParametersUpdateOut(StrictModel):
    dataset_id: UUID
    revision: int
    assets: list[AssetOut]

class DatasetPage(PageMetadata):
    items: list[DatasetOut]

class DatasetMemberOut(StrictModel):
    id: UUID
    dataset_id: UUID
    asset_id: UUID
    position: int
    relative_path: str | None
    asset: AssetOut

class DatasetMemberSummary(LibraryAssetSummary):
    dataset_id: UUID
    member_position: int = Field(ge=0)
    thumbnail_status: Literal['queued', 'generating', 'available', 'failed', 'unsupported'] | None

class DatasetMemberSummaryPage(PageMetadata):
    items: list[DatasetMemberSummary]

class DatasetMemberQuery(LibraryMemberFilters):
    q: str | None = None
    sort_by: LibrarySortKey | Literal['position'] = 'position'
    order: Literal['asc', 'desc'] = 'asc'
    limit: int = Field(default=50, ge=1, le=200, strict=False)
    offset: int = Field(default=0, ge=0, strict=False)

class DatasetMemberPage(PageMetadata):
    items: list[DatasetMemberOut]

class DatasetMembersCreate(StrictModel):
    base_revision: int = Field(ge=1)
    asset_ids: list[UuidInput]
    calibration: CalibrationBindings | None = None
    accept_unknown: bool = False

    @model_validator(mode='after')
    def maps_are_objects(self):
        if 'calibration' in self.model_fields_set and self.calibration is None:
            raise ValueError('calibration 必须是对象，清空请传空对象')
        return self

class DatasetCreate(StrictModel):
    name: str
    notes: str | None = None
    asset_ids: list[UuidInput]
    _name = field_validator('name')(check_name)

class DatasetPatch(StrictModel):
    base_revision: int = Field(ge=1)
    name: str | None = None
    notes: str | None = None
    status: Literal['active', 'archived'] | None = None

    @field_validator('name')
    @classmethod
    def valid_name(cls, value):
        return None if value is None else check_name(value)

class DatasetMemberRevision(StrictModel):
    asset_id: UuidInput
    revision: int = Field(ge=1)

class DatasetMemberParametersUpdate(StrictModel):
    base_revision: int = Field(ge=1)
    members: list[DatasetMemberRevision]
    parameters: AssetParametersPatch | None = None
    classification: AssetClassification | None = None

    @model_validator(mode='after')
    def has_changes(self):
        if self.parameters is None and self.classification is None:
            raise ValueError('必须指定要修改的参数或分类')
        return self

    @model_validator(mode='after')
    def unique_members(self):
        ids = [str(item.asset_id) for item in self.members]
        if len(ids) != len(set(ids)):
            raise ValueError('members 中不能包含重复 Asset')
        return self

class DatasetQuery(StrictModel):
    limit: int = Field(default=50, ge=1, le=200, strict=False)
    offset: int = Field(default=0, ge=0, strict=False)
    sort_by: Literal['created_at', 'name'] = 'created_at'
    order: Literal['asc', 'desc'] = 'desc'
    q: str | None = None
    status: Literal['active', 'archived', 'all'] = 'active'
