from datetime import datetime
from math import isfinite
from pathlib import PurePosixPath
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .schemas import CfaPattern, StrictModel, UuidInput, check_name


FrameClass = Literal["subframe", "masterframe", "video"]
FrameType = Literal["light", "bias", "dark", "flat", "dark_flat"]
ParameterMode = Literal["iso", "gain", "standard"]
class AssetClassification(StrictModel):
    frame_class: FrameClass | None = None
    frame_type: FrameType | None = None

    @model_validator(mode="after")
    def frame_class_has_valid_type(self):
        if self.frame_class == "video" and self.frame_type is not None:
            raise ValueError("Video 不设置帧用途")
        return self


class AssetClassificationPatch(StrictModel):
    frame_class: FrameClass | None = None
    frame_type: FrameType | None = None

    @model_validator(mode="after")
    def video_has_no_frame_type(self):
        if self.frame_class == "video" and self.frame_type is not None:
            raise ValueError("Video 不设置帧用途")
        return self


class AssetParameters(StrictModel):
    camera_id: UuidInput | None = None
    optical_system_id: UuidInput | None = None
    filter_id: UuidInput | None = None
    parameter_mode: ParameterMode = "standard"
    iso: int | None = Field(default=None, gt=0)
    gain: float | None = None
    offset: float | None = None
    exposure_seconds: float | None = Field(default=None, ge=0)
    integration_seconds: float | None = Field(default=None, ge=0)
    sensor_temperature_c: float | None = None
    binning_x: int | None = Field(default=None, gt=0)
    binning_y: int | None = Field(default=None, gt=0)
    cfa_pattern: CfaPattern | None = None

    @field_validator("gain", "offset", "exposure_seconds", "integration_seconds", "sensor_temperature_c")
    @classmethod
    def finite_values(cls, value):
        if value is not None and not isfinite(value):
            raise ValueError("数值必须是有限值")
        return value


class AssetParametersPatch(StrictModel):
    camera_id: UuidInput | None = None
    optical_system_id: UuidInput | None = None
    filter_id: UuidInput | None = None
    parameter_mode: ParameterMode | None = None
    iso: int | None = Field(default=None, gt=0)
    gain: float | None = None
    offset: float | None = None
    exposure_seconds: float | None = Field(default=None, ge=0)
    integration_seconds: float | None = Field(default=None, ge=0)
    sensor_temperature_c: float | None = None
    binning_x: int | None = Field(default=None, gt=0)
    binning_y: int | None = Field(default=None, gt=0)
    cfa_pattern: CfaPattern | None = None

    @field_validator("gain", "offset", "exposure_seconds", "integration_seconds", "sensor_temperature_c")
    @classmethod
    def finite_values(cls, value):
        if value is not None and not isfinite(value):
            raise ValueError("数值必须是有限值")
        return value


class ImportSource(StrictModel):
    root_id: str = Field(min_length=1)
    path: str

    @field_validator("path")
    @classmethod
    def relative_posix_path(cls, value):
        if "\\" in value or PurePosixPath(value).is_absolute() or ".." in PurePosixPath(value).parts:
            raise ValueError("来源路径必须是素材根目录内的相对 POSIX 路径")
        return value


class ImportCreate(StrictModel):
    sources: list[ImportSource] = Field(min_length=1)
    storage_mode: Literal["reference", "managed"]
    classification: AssetClassification = Field(default_factory=AssetClassification)
    parameters: AssetParameters = Field(default_factory=AssetParameters)
    notes: str | None = None
    dataset_name: str | None = None
    capture_preset_id: UuidInput | None = None


class UploadFile(StrictModel):
    name: str = Field(min_length=1)
    size: int = Field(ge=0)

    @field_validator("name")
    @classmethod
    def filename_only(cls, value):
        if PurePosixPath(value).name != value or "\\" in value or value in {".", ".."}:
            raise ValueError("文件名无效")
        return value


class UploadImportCreate(StrictModel):
    files: list[UploadFile] = Field(min_length=1)
    classification: AssetClassification = Field(default_factory=AssetClassification)
    parameters: AssetParameters = Field(default_factory=AssetParameters)
    notes: str | None = None
    dataset_name: str | None = None
    create_dataset: bool = False
    capture_preset_id: UuidInput | None = None


class AssetPatch(StrictModel):
    base_revision: int = Field(ge=1)
    name: str | None = None
    notes: str | None = None
    classification: AssetClassificationPatch | None = None
    parameters: AssetParametersPatch | None = None
    status: Literal["active", "archived"] | None = None

    @field_validator("name")
    @classmethod
    def valid_name(cls, value):
        return None if value is None else check_name(value)

    @model_validator(mode="after")
    def reject_null_objects(self):
        for field in ("classification", "parameters"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} 不能为 null，请传对象")
        return self


class DatasetMembersCreate(StrictModel):
    base_revision: int = Field(ge=1)
    asset_version_ids: list[UuidInput]


class DatasetPatch(StrictModel):
    base_revision: int = Field(ge=1)
    name: str | None = None
    notes: str | None = None
    status: Literal["active", "archived"] | None = None

    @field_validator("name")
    @classmethod
    def valid_name(cls, value):
        return None if value is None else check_name(value)


class ProjectReferenceCreate(StrictModel):
    base_revision: int = Field(ge=1)
    asset_version_id: UuidInput


class ProjectDatasetReferenceCreate(StrictModel):
    base_revision: int = Field(ge=1)
    dataset_id: UuidInput
    dataset_version_id: UuidInput


class ProjectReferenceDelete(StrictModel):
    base_revision: int = Field(ge=1)


class LibraryEntryRemove(StrictModel):
    entry_type: Literal["asset", "dataset"]
    id: UuidInput
    revision: int = Field(ge=1)
    current_version_id: UuidInput | None


class LibraryEntriesRemove(StrictModel):
    items: list[LibraryEntryRemove] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_entries(self):
        identities = [(item.entry_type, item.id) for item in self.items]
        if len(set(identities)) != len(identities):
            raise ValueError("素材库记录不能重复")
        return self


class LibraryTrashSelectionItem(StrictModel):
    entry_type: Literal["asset", "dataset"]
    id: UuidInput
    removed_at: datetime = Field(strict=False)
    revision: int = Field(ge=1)
    current_version_id: UuidInput | None
    source_dataset_id: UuidInput | None = None


class LibraryTrashSelection(StrictModel):
    items: list[LibraryTrashSelectionItem] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_entries(self):
        identities = [(item.entry_type, item.id) for item in self.items]
        if len(set(identities)) != len(self.items):
            raise ValueError("垃圾桶记录不能重复")
        return self


class LibraryTrashDelete(StrictModel):
    items: list[LibraryTrashSelectionItem] = Field(min_length=1)
    preview_fingerprint: str

    @model_validator(mode="after")
    def unique_entries(self):
        identities = [(item.entry_type, item.id) for item in self.items]
        if len(set(identities)) != len(self.items):
            raise ValueError("垃圾桶记录不能重复")
        return self


class RetryCreate(StrictModel):
    item_ids: list[UuidInput] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_items(self):
        if len(set(self.item_ids)) != len(self.item_ids):
            raise ValueError("item_ids 不能重复")
        return self


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
