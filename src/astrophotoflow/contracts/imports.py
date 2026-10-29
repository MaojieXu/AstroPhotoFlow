from astrophotoflow.contracts.assets import AssetClassification, AssetParameters
from astrophotoflow.contracts.common import StrictModel, UuidInput
from datetime import datetime
from pathlib import PurePosixPath, PureWindowsPath
from pydantic import Field, field_validator, model_validator
from typing import Literal
from uuid import UUID


class ImportRootOut(StrictModel):
    id: str
    label: str
    available: bool


class ImportRootEntryOut(StrictModel):
    name: str
    path: str
    kind: Literal["file", "directory"]
    format: str | None
    supported: bool
    size: int | None


class ImportRootEntryPage(StrictModel):
    items: list[ImportRootEntryOut]
    total: int
    limit: int
    offset: int


class ImportAccepted(StrictModel):
    task_id: UUID
    status: Literal["queued"]


class TaskItemOut(StrictModel):
    id: UUID
    task_id: UUID
    root_item_id: UUID
    retry_of_item_id: UUID | None
    root_id: str
    source_path: str
    position: int
    status: str
    content_status: str
    metadata_status: str
    preview_status: str
    asset_id: UUID | None
    asset_version_id: UUID | None
    error: dict | None
    created_at: datetime
    updated_at: datetime


class AssetTaskOut(StrictModel):
    id: UUID
    status: str
    sources: list[dict]
    storage_mode: Literal["reference", "managed"]
    classification: dict
    parameters: dict
    notes: str | None
    dataset_name: str | None
    target_dataset_id: UUID | None
    dataset_base_revision: int | None
    dataset_id: UUID | None
    enumeration_completed: bool
    retry_of_task_id: UUID | None
    report: dict = Field(description="阶段事实。registration为登记判定计数；content包含total/succeeded/failed/skipped/metadata_failed、bytes_total/bytes_copied及completed；preview包含total/available/failed/unsupported及completed。原件就绪与预览完成分别表达，任务status仍遵循既有终态协议。")
    error: dict | None
    created_at: datetime
    updated_at: datetime
    items: list[TaskItemOut]
    items_total: int
    items_completed: int
    items_limit: int
    items_offset: int


class AssetTaskPage(StrictModel):
    items: list[AssetTaskOut]
    total: int
    limit: int
    offset: int


class ImportSource(StrictModel):
    root_id: str | None = Field(default=None, min_length=1)
    path: str

    @model_validator(mode="after")
    def source_path(self):
        if self.root_id is None:
            if not (PurePosixPath(self.path).is_absolute() or PureWindowsPath(self.path).is_absolute()):
                raise ValueError("未指定root_id时必须提供本机绝对路径。")
        elif "\\" in self.path or PurePosixPath(self.path).is_absolute() or ".." in PurePosixPath(self.path).parts:
            raise ValueError("指定root_id时来源必须是根目录内的相对 POSIX 路径。")
        return self


class ImportCreate(StrictModel):
    sources: list[ImportSource] = Field(min_length=1)
    storage_mode: Literal["reference", "managed"]
    classification: AssetClassification = Field(default_factory=AssetClassification)
    parameters: AssetParameters = Field(default_factory=AssetParameters)
    notes: str | None = None
    dataset_name: str | None = None
    capture_preset_id: UuidInput | None = None

    @model_validator(mode="after")
    def direct_paths_are_managed(self):
        if self.storage_mode != "managed" and any(source.root_id is None for source in self.sources):
            raise ValueError("直接路径导入采用托管副本。仅引用模式继续使用root_id来源。")
        return self


class LocalSelectionRequest(StrictModel):
    mode: Literal["files", "folder"]


class LocalSelectionFile(StrictModel):
    path: str
    name: str
    size: int


class LocalSelectionOut(StrictModel):
    cancelled: bool
    files: list[LocalSelectionFile]
    name: str | None
    folder: bool


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


class RetryCreate(StrictModel):
    item_ids: list[UuidInput] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_items(self):
        if len(set(self.item_ids)) != len(self.item_ids):
            raise ValueError("item_ids 不能重复")
        return self


class PhotoImportOptions(StrictModel):
    """Upload metadata; file names and sizes are read from the supplied local paths."""

    classification: AssetClassification = Field(default_factory=AssetClassification)
    parameters: AssetParameters = Field(default_factory=AssetParameters)
    notes: str | None = None
    dataset_name: str | None = None
    create_dataset: bool = False
    capture_preset_id: UuidInput | None = None
