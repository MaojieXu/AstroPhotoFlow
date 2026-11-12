from datetime import datetime
from pathlib import PurePosixPath, PureWindowsPath
from typing import Literal
from uuid import UUID
from pydantic import ConfigDict, Field, JsonValue, field_validator, model_validator
from astrophotoflow.contracts.common import PageMetadata, SnapshotModel, StrictModel, UuidInput
from astrophotoflow.contracts.image_management import EquipmentApplication
from astrophotoflow.contracts.metadata import AssetClassification, AssetParameters
TaskStatus = Literal['queued', 'running', 'cancelling', 'completed', 'completed_with_errors', 'failed', 'cancelled', 'interrupted']

class ImportTaskStateOut(StrictModel):
    task_id: UUID
    status: TaskStatus

class UploadReceipt(StrictModel):
    received: int = Field(ge=0)

class ImportRootOut(StrictModel):
    id: str
    label: str
    available: bool

class ImportRootEntryOut(StrictModel):
    name: str
    path: str
    kind: Literal['file', 'directory']
    format: str | None
    supported: bool
    size: int | None

class ImportRootEntryPage(PageMetadata):
    items: list[ImportRootEntryOut]

class ImportAccepted(StrictModel):
    task_id: UUID
    status: Literal['queued']

class TaskItemOut(StrictModel):
    dataset_id: UUID | None = None
    dataset_name: str | None = None
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
    error: dict | None
    created_at: datetime
    updated_at: datetime

class ImportRegistrationProgress(StrictModel):
    total: int = Field(ge=0)
    registered: int = Field(ge=0)
    completed: bool

class ImportContentProgress(StrictModel):
    total: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    skipped: int = Field(ge=0)
    metadata_failed: int = Field(ge=0)
    bytes_total: int = Field(ge=0)
    bytes_copied: int = Field(ge=0)
    completed: bool

class ImportPreviewProgress(StrictModel):
    total: int = Field(ge=0)
    available: int = Field(ge=0)
    failed: int = Field(ge=0)
    unsupported: int = Field(ge=0)
    completed: bool

class DatasetImportExclusion(StrictModel):
    asset_id: UuidInput
    name: str
    code: str
    message: str

class DatasetPublicationError(SnapshotModel):
    model_config = ConfigDict(extra='allow')
    __pydantic_extra__: dict[str, JsonValue] = Field(init=False)
    code: str
    message: str | None = None
    fields: list[dict[str, str]] = Field(default_factory=list)

class ImportProjectLink(StrictModel):
    state: Literal['not_requested', 'pending', 'linked', 'failed']
    code: str | None = None
    message: str | None = None
    fields: list[dict[str, str]] = Field(default_factory=list)
    reference_ids: list[str] = Field(default_factory=list)
    project_revision: int | None = None


class ImportDestinationReport(StrictModel):
    mode: Literal['standalone', 'new_dataset', 'append_dataset']
    project_id: str | None = None
    project_base_revision: int | None = None
    project_name: str | None = None
    project_link: ImportProjectLink


class ImportReport(SnapshotModel):
    destination: ImportDestinationReport | None = None
    model_config = ConfigDict(extra='allow')
    __pydantic_extra__: dict[str, JsonValue] = Field(init=False)
    dataset_publish_error: DatasetPublicationError | None = None
    registration: ImportRegistrationProgress | None = None
    content: ImportContentProgress | None = None
    preview: ImportPreviewProgress | None = None
    dataset_exclusions: list[DatasetImportExclusion] = Field(default_factory=list)

class AssetTaskOut(StrictModel):
    id: UUID
    status: TaskStatus
    sources: list[dict]
    storage_mode: Literal['reference', 'managed']
    classification: dict
    parameters: dict
    notes: str | None
    dataset_name: str | None
    target_dataset_id: UUID | None
    dataset_base_revision: int | None
    dataset_id: UUID | None
    enumeration_completed: bool
    retry_of_task_id: UUID | None
    report: ImportReport
    error: dict | None
    created_at: datetime
    updated_at: datetime
    items: list[TaskItemOut]
    items_total: int
    items_completed: int
    items_limit: int
    items_offset: int

class ImportProgressSummary(StrictModel):
    destination: ImportDestinationReport | None = None
    dataset_publish_error: DatasetPublicationError | None = None
    dataset_exclusions: list[DatasetImportExclusion] = Field(default_factory=list)
    registration: ImportRegistrationProgress | None = None
    content: ImportContentProgress | None = None
    preview: ImportPreviewProgress | None = None

class AssetTaskSummary(StrictModel):
    id: UUID
    status: TaskStatus
    dataset_name: str | None
    target_dataset_id: UUID | None
    dataset_id: UUID | None
    enumeration_completed: bool
    report: ImportProgressSummary
    error: dict | None
    created_at: datetime
    updated_at: datetime
    items_total: int = Field(ge=0)
    items_completed: int = Field(ge=0)

class AssetTaskPage(PageMetadata):
    items: list[AssetTaskSummary]

class ImportSource(StrictModel):
    root_id: str | None = Field(default=None, min_length=1)
    path: str

    @model_validator(mode='after')
    def source_path(self):
        if self.root_id is None:
            if not (PurePosixPath(self.path).is_absolute() or PureWindowsPath(self.path).is_absolute()):
                raise ValueError('未指定root_id时必须提供本机绝对路径。')
        elif '\\' in self.path or PurePosixPath(self.path).is_absolute() or '..' in PurePosixPath(self.path).parts:
            raise ValueError('指定root_id时来源必须是根目录内的相对 POSIX 路径。')
        return self

from astrophotoflow.contracts.calibration_status import CalibrationDeclaration

class ImportOptions(CalibrationDeclaration):
    request_id: UuidInput | None = None
    mode: Literal['standalone', 'new_dataset', 'append_dataset'] = 'standalone'
    target_dataset_id: UuidInput | None = None
    dataset_base_revision: int | None = Field(default=None, ge=1)
    project_id: UuidInput | None = None
    project_base_revision: int | None = Field(default=None, ge=1)

    @model_validator(mode='after')
    def valid_destination(self):
        if (self.project_id is None) != (self.project_base_revision is None):
            raise ValueError('Project ID and revision must be supplied together.')
        if self.mode == 'append_dataset':
            if self.target_dataset_id is None or self.dataset_base_revision is None:
                raise ValueError('Appending requires a dataset ID and revision.')
        elif self.target_dataset_id is not None or self.dataset_base_revision is not None:
            raise ValueError('Dataset ID and revision are available only for append_dataset.')
        return self


class ImportCreate(ImportOptions):
    sources: list[ImportSource] = Field(min_length=1)
    storage_mode: Literal['managed']
    classification: AssetClassification = Field(default_factory=AssetClassification)
    parameters: AssetParameters = Field(default_factory=AssetParameters)
    notes: str | None = None
    dataset_name: str | None = None
    equipment: EquipmentApplication | None = None


class LocalSelectionRequest(StrictModel):
    mode: Literal['files', 'folder']

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

    @field_validator('name')
    @classmethod
    def filename_only(cls, value):
        if PurePosixPath(value).name != value or '\\' in value or value in {'.', '..'}:
            raise ValueError('文件名无效')
        return value

class UploadImportCreate(ImportOptions):
    files: list[UploadFile] = Field(min_length=1)
    classification: AssetClassification = Field(default_factory=AssetClassification)
    parameters: AssetParameters = Field(default_factory=AssetParameters)
    notes: str | None = None
    dataset_name: str | None = None
    equipment: EquipmentApplication | None = None

class RetryCreate(StrictModel):
    item_ids: list[UuidInput] = Field(min_length=1)

    @model_validator(mode='after')
    def unique_items(self):
        if len(set(self.item_ids)) != len(self.item_ids):
            raise ValueError('item_ids 不能重复')
        return self

class PhotoImportOptions(ImportOptions):
    """Upload metadata; file names and sizes are read from the supplied local paths."""
    classification: AssetClassification = Field(default_factory=AssetClassification)
    parameters: AssetParameters = Field(default_factory=AssetParameters)
    notes: str | None = None
    dataset_name: str | None = None
    equipment: EquipmentApplication | None = None


class ImportRecovery(StrictModel):
    accept_unknown: bool = False
    request_id: UuidInput
    mode: Literal['new_dataset', 'append_dataset', 'link_project']
    asset_ids: list[UuidInput] = Field(default_factory=list)
    name: str | None = None
    dataset_id: UuidInput | None = None
    expected_revision: int | None = Field(default=None, ge=1)
    project_id: UuidInput | None = None
    project_base_revision: int | None = Field(default=None, ge=1)

    @model_validator(mode='after')
    def valid_recovery(self):
        if len(self.asset_ids) != len(set(self.asset_ids)):
            raise ValueError('Member IDs must be unique.')
        if self.mode == 'new_dataset' and (not self.asset_ids or not self.name or not self.name.strip()):
            raise ValueError('A new dataset requires a name and members.')
        if self.mode == 'append_dataset' and (not self.asset_ids or self.dataset_id is None or self.expected_revision is None):
            raise ValueError('Appending requires members, a dataset and its revision.')
        if (self.project_id is None) != (self.project_base_revision is None):
            raise ValueError('Project ID and revision must be supplied together.')
        if self.mode == 'link_project' and self.project_id is None:
            raise ValueError('Select a project and its current revision.')
        return self
