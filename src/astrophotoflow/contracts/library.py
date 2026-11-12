"""Physical library locations and database-derived dataset mirrors."""

from typing import Literal

from pydantic import Field

from astrophotoflow.contracts.calibration_status import CalibrationState
from astrophotoflow.contracts.common import JsonObject, StrictModel, UuidInput

LibraryEntryType = Literal['asset', 'dataset']


class LibraryFileLocation(CalibrationState):
    asset_id: UuidInput
    storage_mode: Literal['managed', 'reference']
    availability: Literal['unknown', 'available', 'changed', 'missing']
    path: str
    library_relative_path: str | None
    processing_calibration: JsonObject | None = None
    processing_provenance: JsonObject | None = None


class LibraryLocationOut(StrictModel):
    entry_type: LibraryEntryType
    id: UuidInput
    revision: int
    directory: str | None
    files: list[LibraryFileLocation]
    manifest_path: str | None
    manifest_status: Literal['pending', 'ready', 'failed'] | None
    manifest_error: str | None


class ManifestRebuildRequest(StrictModel):
    base_revision: int = Field(ge=1)


class LibraryOrganizeRequest(ManifestRebuildRequest):
    entry_type: LibraryEntryType
    id: UuidInput


class LibraryFileMove(StrictModel):
    asset_id: UuidInput
    revision: int
    content_hash: str | None
    byte_size: int | None
    source: str
    destination: str
    state: Literal['pending', 'completed', 'failed', 'cleanup_pending'] = 'pending'
    error: str | None = None


class LibraryOrganizePlan(StrictModel):
    entry_type: LibraryEntryType
    id: UuidInput
    base_revision: int
    source_directory: str | None
    destination_directory: str
    moves: list[LibraryFileMove]
    blockers: list[str]
    token: str


class LibraryOrganizeExecute(LibraryOrganizeRequest):
    request_id: UuidInput
    plan_token: str


class LibraryOrganizeReceipt(StrictModel):
    request_id: UuidInput
    operation: Literal['organize_library'] = 'organize_library'
    state: Literal['running', 'completed', 'partial', 'interrupted']
    plan: LibraryOrganizePlan
    error: str | None = None


class LibraryDirectoryOpened(StrictModel):
    directory: str
