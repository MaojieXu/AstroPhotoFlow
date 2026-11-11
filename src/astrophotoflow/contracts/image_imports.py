"""Explicit scanned-file imports: the Agent owns grouping and confirmation."""
from typing import Annotated, Literal
from pydantic import MISSING, ConfigDict, Field, field_validator, model_validator
from astrophotoflow.contracts.calibration import CalibrationTarget
from astrophotoflow.contracts.common import JsonObject, JsonValue, PageMetadata, StrictModel, UuidInput
from astrophotoflow.contracts.image_calibration import CalibrationCheckState, CalibrationPatch, CalibrationSlot
from astrophotoflow.contracts.image_management import EquipmentApplication, ImageMetadata, ImageName, PageLimit, PageOffset, Revision
from astrophotoflow.contracts.imports import ImportDestinationReport, TaskStatus
from astrophotoflow.contracts.metadata import FrameClass, FrameType

class InspectionQuery(StrictModel):
    model_config = ConfigDict(extra='forbid', strict=False)
    text: str | None = None
    frame_class: FrameClass | None = None
    frame_type: FrameType | None = None
    target_name: str | None = None
    supported: bool | None = None
    limit: PageLimit = 50
    offset: PageOffset = 0

class ImageInspectionRequest(StrictModel):
    paths: list[str] = Field(min_length=1)
    recursive: bool = True

from astrophotoflow.contracts.calibration_status import CalibrationDeclaration, CalibrationState

class ConfirmedFile(CalibrationDeclaration):
    file_id: UuidInput
    name: ImageName | MISSING = MISSING
    metadata: ImageMetadata | MISSING = MISSING
    equipment: EquipmentApplication | MISSING = MISSING
    calibration: CalibrationPatch | MISSING = MISSING
    notes: str | None | MISSING = MISSING

class ImportDefaults(CalibrationDeclaration):
    metadata: ImageMetadata | MISSING = MISSING
    equipment: EquipmentApplication | MISSING = MISSING
    notes: str | None | MISSING = MISSING

class StandaloneDestination(StrictModel):
    mode: Literal['standalone']

class NewDatasetDestination(StrictModel):
    mode: Literal['new_dataset']
    name: ImageName
    notes: str | None = None

class AppendDatasetDestination(StrictModel):
    mode: Literal['append_dataset']
    dataset_id: UuidInput
    expected_revision: Revision
ImportDestination = Annotated[StandaloneDestination | NewDatasetDestination | AppendDatasetDestination, Field(discriminator='mode')]

class ExplicitImportRequest(StrictModel):
    project_id: UuidInput | None = None
    project_base_revision: Revision | None = None
    request_id: UuidInput
    scan_id: UuidInput
    files: list[ConfirmedFile] = Field(min_length=1)
    destination: ImportDestination
    defaults: ImportDefaults | MISSING = MISSING
    calibration: CalibrationPatch | MISSING = MISSING
    storage_mode: Literal['managed'] = 'managed'
    accept_unknown: bool = False

    @field_validator('files')
    @classmethod
    def unique_files(cls, value):
        ids = [item.file_id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError('Scanned files must be unique within a submission.')
        return value

    @model_validator(mode='after')
    def destination_options(self):
        if (self.project_id is None) != (self.project_base_revision is None):
            raise ValueError('Project ID and revision must be supplied together.')
        if self.calibration is not MISSING and self.destination.mode != 'new_dataset':
            raise ValueError('calibration is available only for a new dataset.')
        if self.destination.mode != 'standalone' and any((file.calibration is not MISSING for file in self.files)):
            raise ValueError('Individual calibration is available only for standalone imports.')
        return self

class ImagePublicationRetry(StrictModel):
    request_id: UuidInput
    task_id: UuidInput
    expected_revision: Revision

class ImageRequestWait(StrictModel):
    request_id: UuidInput
    wait_seconds: float = Field(default=20, ge=0, le=20, allow_inf_nan=False)

class ImageInspectionOut(StrictModel):
    scan_id: UuidInput
    recursive: bool
    roots: list[str]
    file_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)
    issues: list[JsonObject]
    issues_total: int = Field(ge=0)

class InspectedImageFile(StrictModel):
    file_id: UuidInput
    path: str
    relative_path: str
    format: str | None
    source_stamp: JsonObject
    observed: JsonObject
    issues: list[JsonValue]
    metadata_status: str
    supported: bool

class ImageInspectionPage(PageMetadata):
    items: list[InspectedImageFile | JsonObject]

class ImportRegistrationStage(StrictModel):
    total: int = Field(ge=0)
    registered: int = Field(ge=0)

class ImportAvailabilityStage(StrictModel):
    available: int = Field(ge=0)
    total: int = Field(ge=0)

class ImagePublicationStage(StrictModel):
    state: Literal['pending', 'published', 'blocked', 'conflict']
    dataset_id: UuidInput | None = None
    dataset_revision: int | None = None
    binding: JsonObject | None = None
    bindings: list[JsonObject] = Field(default_factory=list)
    errors: list[JsonObject] | None = None
    calibration: JsonObject | None = None
    published_file_ids: list[UuidInput] | None = None

class ImageImportStages(StrictModel):
    registration: ImportRegistrationStage
    originals: ImportAvailabilityStage
    metadata: ImportAvailabilityStage
    publication: ImagePublicationStage
    calibration: JsonObject
    previews: ImportAvailabilityStage

class ImageImportItem(CalibrationState):
    file_id: UuidInput | None
    task_item_id: UuidInput
    asset_id: UuidInput | None
    status: str
    originals: str
    metadata: str
    previews: str
    publication_status: Literal['published', 'conflict', 'excluded', 'not_ready', 'pending']
    calibration_binding_status: Literal['saved', 'pending', 'blocked', 'not_checked']
    errors: list[JsonObject]
    member_position: int | None
    error: JsonObject | None

class ImageImportReceipt(StrictModel):
    organization_recovery: JsonObject | None = None
    destination: ImportDestinationReport | None = None
    request_id: UuidInput
    task_id: UuidInput
    status: TaskStatus
    state: Literal['running', 'needs_attention', 'completed']
    stages: ImageImportStages
    items: list[ImageImportItem]
    items_total: int = Field(ge=0)
    items_limit: int = Field(ge=1)
    items_offset: int = Field(ge=0)
    next_poll_seconds: int | None
    error: JsonObject | None

class ScannedCalibrationCheckRequest(StrictModel):
    scan_id: UuidInput
    files: list[ConfirmedFile] = Field(min_length=1)
    defaults: ImportDefaults | None = None
    calibration: CalibrationPatch | None = None
    destination: ImportDestination | None = None
    limit: PageLimit = 50
    offset: PageOffset = 0

    @model_validator(mode='after')
    def valid_selection(self):
        ids = [item.file_id for item in self.files]
        if len(ids) != len(set(ids)):
            raise ValueError('Scanned files must be unique.')
        mode = self.destination.mode if self.destination else None
        if self.calibration is not None and mode not in {None, 'new_dataset'}:
            raise ValueError('calibration is available only for a new dataset.')
        if (mode in {'new_dataset', 'append_dataset'} or self.calibration is not None) and any((file.calibration is not MISSING for file in self.files)):
            raise ValueError('Individual calibration is available only for standalone imports.')
        return self

class ScannedCalibrationCheckItem(StrictModel):
    file_id: UuidInput
    dependency_asset_id: UuidInput | None = None
    slot: CalibrationSlot
    target: CalibrationTarget
    state: CalibrationCheckState
    master_required: bool
    diagnostics: list[JsonObject]
    dependency_path: list[CalibrationTarget]

class ScannedCalibrationCheckPage(PageMetadata):
    warning_count: int = Field(default=0, ge=0)
    state: CalibrationCheckState
    checked_files: int = Field(ge=0)
    checked_bindings: int = Field(ge=0)
    conflict_count: int = Field(ge=0)
    unknown_count: int = Field(ge=0)
    master_required_count: int = Field(ge=0)
    items: list[ScannedCalibrationCheckItem]
