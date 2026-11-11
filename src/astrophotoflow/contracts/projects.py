from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import Field, field_validator
from astrophotoflow.contracts.assets import AssetOut, LibraryMetadataSummary
from astrophotoflow.contracts.common import PageMetadata, StrictModel, UuidInput, check_name
from astrophotoflow.contracts.datasets import DatasetOut

class ProjectCreate(StrictModel):
    name: str
    target_name: str | None = None
    notes: str | None = None
    _name = field_validator('name')(check_name)

class ProjectPatch(StrictModel):
    base_revision: int = Field(ge=1)
    name: str | None = None
    target_name: str | None = None
    notes: str | None = None
    status: Literal['active', 'archived'] | None = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, value):
        return None if value is None else check_name(value)

class ProjectOut(StrictModel):
    id: UUID
    name: str
    target_name: str | None
    notes: str | None
    status: Literal['active', 'archived']
    revision: int
    created_at: datetime
    updated_at: datetime

class ProjectAssetReferenceOut(StrictModel):
    id: UUID
    project_id: UUID
    asset_id: UUID
    view_base: str
    added_at: datetime
    asset: AssetOut

class ProjectPage(PageMetadata):
    items: list[ProjectOut]

class ProjectAssetReferencePage(PageMetadata):
    items: list[ProjectAssetReferenceOut]

class ProjectDatasetReferenceOut(StrictModel):
    summary: LibraryMetadataSummary
    input_ready: bool
    member_count: int
    id: UUID
    project_id: UUID
    dataset_id: UUID
    base_revision: int
    added_at: datetime
    dataset: DatasetOut

class ProjectDatasetReferencePage(PageMetadata):
    items: list[ProjectDatasetReferenceOut]

class ProjectReferenceCreate(StrictModel):
    base_revision: int = Field(ge=1)
    asset_id: UuidInput

class ProjectDatasetReferenceCreate(StrictModel):
    base_revision: int = Field(ge=1)
    dataset_id: UuidInput

class ProjectReferenceDelete(StrictModel):
    base_revision: int = Field(ge=1)

class ProjectReferenceDeleteResult(StrictModel):
    deleted_id: UuidInput
    revision: int = Field(ge=1)

class ProjectQuery(StrictModel):
    limit: int = Field(default=50, ge=1, le=200, strict=False)
    offset: int = Field(default=0, ge=0, strict=False)
    sort_by: Literal['created_at', 'name'] = 'created_at'
    order: Literal['asc', 'desc'] = 'desc'
    q: str | None = None
    status: Literal['active', 'archived', 'all'] = 'active'
    target_name: str | None = None
