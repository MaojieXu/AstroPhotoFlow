from astrophotoflow.contracts.assets import AssetOut, AssetVersionOut
from astrophotoflow.contracts.common import StrictModel, UuidInput, check_name
from astrophotoflow.contracts.datasets import DatasetOut, DatasetVersionOut
from datetime import datetime
from pydantic import Field, field_validator
from typing import Literal
from uuid import UUID


class ProjectCreate(StrictModel):
    name: str
    target_name: str | None = None
    notes: str | None = None

    _name = field_validator("name")(check_name)


class ProjectPatch(StrictModel):
    base_revision: int = Field(ge=1)
    name: str | None = None
    target_name: str | None = None
    notes: str | None = None
    status: Literal["active", "archived"] | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        return None if value is None else check_name(value)


class ProjectOut(StrictModel):
    id: UUID
    name: str
    target_name: str | None
    notes: str | None
    status: Literal["active", "archived"]
    revision: int
    created_at: datetime
    updated_at: datetime


class ProjectAssetReferenceOut(StrictModel):
    id: UUID
    project_id: UUID
    asset_version_id: UUID
    added_at: datetime
    asset: AssetOut
    version: AssetVersionOut


class ProjectPage(StrictModel):
    items: list[ProjectOut]
    total: int
    limit: int
    offset: int


class ProjectAssetReferencePage(StrictModel):
    items: list[ProjectAssetReferenceOut]
    total: int
    limit: int
    offset: int


class ProjectDatasetReferenceOut(StrictModel):
    id: UUID
    project_id: UUID
    dataset_id: UUID
    dataset_version_id: UUID
    base_revision: int
    added_at: datetime
    dataset: DatasetOut
    version: DatasetVersionOut


class ProjectDatasetReferencePage(StrictModel):
    items: list[ProjectDatasetReferenceOut]
    total: int
    limit: int
    offset: int


class ProjectReferenceCreate(StrictModel):
    base_revision: int = Field(ge=1)
    asset_version_id: UuidInput


class ProjectDatasetReferenceCreate(StrictModel):
    base_revision: int = Field(ge=1)
    dataset_id: UuidInput
    dataset_version_id: UuidInput


class ProjectReferenceDelete(StrictModel):
    base_revision: int = Field(ge=1)
