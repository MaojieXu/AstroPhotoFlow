"""HTTP adaptation for configuration archive and explicit permanent deletion."""
from fastapi import APIRouter, Depends

import astrophotoflow.modules.data.public as data
from astrophotoflow.contracts.trash import (
    EquipmentDelete,
    EquipmentDeleteSelection,
    ManagementArchiveResult,
    ManagementRestoreResult,
    ManagementTrashDelete,
    ManagementTrashDeleteOut,
    ManagementTrashPage,
    ManagementTrashPreviewOut,
    ManagementTrashSelection,
)
from astrophotoflow.interfaces.http.dependencies import ERROR_RESPONSES, Limit, Offset, ReadSession, WriteSession, authenticate

router = APIRouter(prefix="/api/v1/settings/trash", responses=ERROR_RESPONSES)
equipment_router = APIRouter(prefix="/api/v1/equipment-management", responses=ERROR_RESPONSES)


@router.get("", response_model=ManagementTrashPage, dependencies=[Depends(authenticate)], operation_id='list_management_trash_api_v1_settings_trash_get')
def list_management_trash(session: ReadSession, limit: Limit = 50, offset: Offset = 0, q: str | None = None):
    return data.list_management_trash(session, limit=limit, offset=offset, q=q)


@router.post("/archive", response_model=ManagementArchiveResult, dependencies=[Depends(authenticate)], operation_id='archive_management_entries_api_v1_settings_trash_archive_post')
def archive_management_entries(body: ManagementTrashSelection, session: WriteSession):
    return data.archive_management_entries(body, session)


@router.post("/restore", response_model=ManagementRestoreResult, dependencies=[Depends(authenticate)], operation_id='restore_management_entries_api_v1_settings_trash_restore_post')
def restore_management_entries(body: ManagementTrashSelection, session: WriteSession):
    return data.restore_management_entries(body, session)


@router.post("/delete-preview", response_model=ManagementTrashPreviewOut, dependencies=[Depends(authenticate)], operation_id='preview_management_delete_api_v1_settings_trash_delete_preview_post')
def preview_management_delete(body: ManagementTrashSelection, session: ReadSession):
    return data.preview_management_delete(body, session)


@router.post("/delete", response_model=ManagementTrashDeleteOut, dependencies=[Depends(authenticate)], operation_id='delete_management_entries_api_v1_settings_trash_delete_post')
def delete_management_entries(body: ManagementTrashDelete, session: WriteSession):
    return data.delete_management_entries(body, session)


@equipment_router.post("/delete-preview", response_model=ManagementTrashPreviewOut, dependencies=[Depends(authenticate)], operation_id='preview_equipment_delete_api_v1_equipment_management_delete_preview_post')
def preview_equipment_delete(body: EquipmentDeleteSelection, session: ReadSession):
    return data.preview_equipment_delete(body, session)


@equipment_router.post("/delete", response_model=ManagementTrashDeleteOut, dependencies=[Depends(authenticate)], operation_id='delete_equipment_entries_api_v1_equipment_management_delete_post')
def delete_equipment_entries(body: EquipmentDelete, session: WriteSession):
    return data.delete_equipment_entries(body, session)
