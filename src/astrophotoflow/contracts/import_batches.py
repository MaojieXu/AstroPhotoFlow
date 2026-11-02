from astrophotoflow.contracts.common import PageMetadata

"""Agent source inspection and explicitly confirmed batch imports."""
from typing import Literal

from pydantic import Field, field_validator, model_validator

from astrophotoflow.contracts.common import StrictModel, UuidInput, check_name
from astrophotoflow.contracts.metadata import AssetClassification, AssetParameters


class ConfirmedImportOptions(StrictModel):
    classification: AssetClassification = Field(default_factory=AssetClassification)
    parameters: AssetParameters = Field(default_factory=AssetParameters)
    notes: str | None = None
    capture_preset_id: UuidInput | None = None


class SourceInspection(StrictModel):
    paths: list[str] = Field(min_length=1)
    recursive: bool = True


class ConfirmedImportGroup(StrictModel):
    name: str
    _name = field_validator('name')(check_name)
    group_id: UuidInput | None = None
    member_ids: list[UuidInput] | None = Field(default=None, min_length=1)
    # Same import semantics, without accepting another set of sources.
    options: ConfirmedImportOptions = Field(default_factory=ConfirmedImportOptions)

    @model_validator(mode='after')
    def one_selection(self):
        if (self.group_id is None) == (self.member_ids is None):
            raise ValueError('Choose group_id or an explicit member_ids list, exclusively.')
        return self


class ImportBatchSubmit(StrictModel):
    scan_id: UuidInput
    request_id: UuidInput
    groups: list[ConfirmedImportGroup] = Field(min_length=1)
    project_id: UuidInput | None = None
    project_revision: int | None = Field(default=None, ge=1)

    @model_validator(mode='after')
    def project_revision_required(self):
        if (self.project_id is None) != (self.project_revision is None):
            raise ValueError('project_id and project_revision must be supplied together.')
        return self


class ImportBatchWait(StrictModel):
    request_id: UuidInput
    wait_seconds: float = Field(default=20, ge=0, le=20)


class ImportBatchProjectRetry(StrictModel):
    base_revision: int = Field(ge=1)


class InspectionPage(PageMetadata):
    items: list[dict]


class InspectionOut(StrictModel):
    scan_id: UuidInput
    recursive: bool
    roots: list[str]
    file_count: int
    excluded_count: int
    groups: list[dict]
    groups_total: int
    issues: list[dict]
    issues_total: int


class BatchOut(StrictModel):
    request_id: UuidInput
    state: Literal['running', 'completed', 'needs_attention']
    groups: list[dict]
    errors: list[dict]
    errors_total: int
    next_poll_seconds: int | None
