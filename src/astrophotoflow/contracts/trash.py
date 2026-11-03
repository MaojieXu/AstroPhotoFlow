from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from astrophotoflow.contracts.common import PageMetadata, StrictModel, UuidInput


class LibraryEntriesRemoveOut(StrictModel):
    removed_count: int


class LibraryTrashGroupOut(StrictModel):
    id: UUID
    name: str
    in_trash: bool


class LibraryTrashItemOut(StrictModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    entry_type: Literal["asset", "dataset"]
    id: UUID
    name: str
    removed_at: datetime
    revision: int
    current_version_id: UUID | None
    cleanup_status: Literal["trash", "partial", "failed"]
    cleanup_error: str | None
    photo_count: int
    member_asset_ids: list[UUID] = Field(default_factory=list)
    groups: list[LibraryTrashGroupOut] = Field(default_factory=list)
    source_dataset_id: UUID | None = None


class LibraryTrashPage(PageMetadata):
    items: list[LibraryTrashItemOut]


class LibraryTrashReferenceOut(StrictModel):
    id: UUID
    kind: Literal["project_asset", "project_dataset", "dataset_member", "calibration"]
    name: str
    version: int


class LibraryTrashPreviewOut(StrictModel):
    items: list[LibraryTrashItemOut]
    references: list[LibraryTrashReferenceOut]
    tasks: list[str]
    photo_count: int
    managed_file_count: int
    managed_bytes: int
    preview_fingerprint: str


class LibraryTrashFailure(StrictModel):
    id: UuidInput
    error: str


class LibraryTrashRestoreOut(StrictModel):
    restored_count: int = Field(ge=0)


class LibraryTrashDeleteOut(StrictModel):
    deleted_count: int
    deleted_entry_count: int
    deleted_file_count: int
    deleted_bytes: int
    missing_file_count: int
    failed: list[LibraryTrashFailure]


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


class LibraryRemovalScope(StrictModel):
    selection: LibraryEntriesRemove
    asset_version_ids: list[UUID]
    dataset_version_ids: list[UUID]
    asset_ids: list[UUID]
    dataset_ids: list[UUID]
    data_token: str


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


ManagementEntryType = Literal["project", "equipment", "equipment_setup"]


class ManagementTrashSelectionItem(StrictModel):
    entry_type: ManagementEntryType
    id: UuidInput
    revision: int = Field(ge=1)


class ManagementTrashSelection(StrictModel):
    items: list[ManagementTrashSelectionItem] = Field(min_length=1)


class ManagementTrashItemOut(StrictModel):
    entry_type: ManagementEntryType
    id: UUID
    name: str
    revision: int
    updated_at: datetime
    details: dict


class ManagementTrashPage(PageMetadata):
    items: list[ManagementTrashItemOut]


class ManagementTrashDependencyOut(StrictModel):
    entry_type: ManagementEntryType
    id: UUID
    kind: str
    name: str
    count: int
    blocks_delete: bool
    references: list[str] = Field(default_factory=list)


class ManagementTrashPreviewOut(StrictModel):
    items: list[ManagementTrashItemOut]
    dependencies: list[ManagementTrashDependencyOut]
    blocked: bool
    preview_fingerprint: str


class ManagementTrashDelete(ManagementTrashSelection):
    preview_fingerprint: str


class ManagementTrashDeleteOut(StrictModel):
    deleted_count: int
    detached_material_count: int


class EquipmentDeleteSelectionItem(StrictModel):
    entry_type: Literal["equipment", "equipment_setup"]
    id: UuidInput
    revision: int = Field(ge=1)


class EquipmentDeleteSelection(StrictModel):
    items: list[EquipmentDeleteSelectionItem] = Field(min_length=1)


class EquipmentDelete(EquipmentDeleteSelection):
    preview_fingerprint: str


class ManagementArchiveResult(StrictModel):
    archived_count: int = Field(ge=0)


class ManagementRestoreResult(StrictModel):
    restored_count: int = Field(ge=0)
