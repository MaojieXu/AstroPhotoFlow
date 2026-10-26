from astrophotoflow.contracts.assets import AssetClassificationPatch, AssetOut, AssetParametersPatch, AssetVersionOut, LibraryAssetItemOut
from astrophotoflow.contracts.calibration import CalibrationBindings
from astrophotoflow.contracts.common import StrictModel, UuidInput, check_name
from datetime import datetime
from pydantic import Field, field_validator, model_validator
from typing import Annotated, Literal
from uuid import UUID


class DatasetOut(StrictModel):
    id: UUID
    name: str
    notes: str | None
    status: Literal["active", "archived"]
    revision: int
    current_version_id: UUID | None
    member_count: int
    created_at: datetime
    updated_at: datetime


class DatasetMemberParametersUpdateOut(StrictModel):
    dataset_id: UUID
    revision: int
    version_id: UUID
    assets: list[AssetOut]


class DatasetPage(StrictModel):
    items: list[DatasetOut]
    total: int
    limit: int
    offset: int


class DatasetMemberOut(StrictModel):
    id: UUID
    dataset_version_id: UUID
    asset_version_id: UUID
    position: int
    relative_path: str | None
    calibration_overrides: CalibrationBindings = Field(default_factory=dict)
    asset: AssetOut
    version: AssetVersionOut


class DatasetVersionOut(StrictModel):
    id: UUID
    dataset_id: UUID
    version_number: int
    created_at: datetime
    calibration_defaults: CalibrationBindings = Field(default_factory=dict)
    members: list[DatasetMemberOut]


class LibraryDatasetItemOut(StrictModel):
    entry_type: Literal["dataset"]
    dataset: DatasetOut
    version: DatasetVersionOut | None
    import_issue: str | None
    matching_member_count: int


LibraryItemOut = Annotated[LibraryAssetItemOut | LibraryDatasetItemOut, Field(discriminator="entry_type")]


class LibraryItemPage(StrictModel):
    items: list[LibraryItemOut]
    total: int
    limit: int
    offset: int


class DatasetVersionPage(StrictModel):
    items: list[DatasetVersionOut]
    total: int
    limit: int
    offset: int


class DatasetMembersCreate(StrictModel):
    base_revision: int = Field(ge=1)
    asset_version_ids: list[UuidInput]
    calibration_defaults: CalibrationBindings | None = None
    member_calibration_overrides: dict[UuidInput, CalibrationBindings] | None = None

    @model_validator(mode="after")
    def maps_are_objects(self):
        for field in ("calibration_defaults", "member_calibration_overrides"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} 必须是对象，清空请传空对象")
        return self


class DatasetCreate(StrictModel):
    name: str
    notes: str | None = None
    asset_version_ids: list[UuidInput]

    _name = field_validator("name")(check_name)


class DatasetPatch(StrictModel):
    base_revision: int = Field(ge=1)
    name: str | None = None
    notes: str | None = None
    status: Literal["active", "archived"] | None = None

    @field_validator("name")
    @classmethod
    def valid_name(cls, value):
        return None if value is None else check_name(value)


class DatasetMemberRevision(StrictModel):
    asset_id: UuidInput
    revision: int = Field(ge=1)


class DatasetMemberParametersUpdate(StrictModel):
    base_revision: int = Field(ge=1)
    base_version_id: UuidInput
    members: list[DatasetMemberRevision]
    parameters: AssetParametersPatch | None = None
    classification: AssetClassificationPatch | None = None

    @model_validator(mode="after")
    def has_changes(self):
        if self.parameters is None and self.classification is None:
            raise ValueError("必须指定要修改的参数或分类")
        return self

    @model_validator(mode="after")
    def unique_members(self):
        ids = [str(item.asset_id) for item in self.members]
        if len(ids) != len(set(ids)):
            raise ValueError("members 中不能包含重复 Asset")
        return self
