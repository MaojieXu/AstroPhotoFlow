from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from .schemas import StrictModel, UuidInput


ManagementEntryType = Literal["project", "equipment", "equipment_setup", "capture_preset"]


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


class ManagementTrashPage(StrictModel):
    items: list[ManagementTrashItemOut]
    total: int
    limit: int
    offset: int


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
