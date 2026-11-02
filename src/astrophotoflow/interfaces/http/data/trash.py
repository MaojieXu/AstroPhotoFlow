from uuid import UUID

from fastapi import APIRouter, Depends, Request

import astrophotoflow.interfaces.http.dependencies as deps
import astrophotoflow.modules.data.public as data
from astrophotoflow.contracts.trash import (
    LibraryEntriesRemove,
    LibraryEntriesRemoveOut,
    LibraryTrashDelete,
    LibraryTrashDeleteOut,
    LibraryTrashPage,
    LibraryTrashPreviewOut,
    LibraryTrashRestoreOut,
    LibraryTrashSelection,
)

router = APIRouter(prefix="/api/v1", responses=deps.ERROR_RESPONSES)

@router.delete('/library/items', dependencies=[Depends(deps.authenticate)], response_model=LibraryEntriesRemoveOut, operation_id='remove_library_entries_api_v1_library_items_delete')
def remove_library_entries(body: LibraryEntriesRemove, session: deps.WriteSession) -> LibraryEntriesRemoveOut:
    return data.remove_library_entries(session=session, body=body)

@router.get('/library/trash', dependencies=[Depends(deps.authenticate)], response_model=LibraryTrashPage, operation_id='library_trash_api_v1_library_trash_get')
def library_trash(session: deps.ReadSession, limit: deps.Limit=50, offset: deps.Offset=0, group_id: UUID | None=None) -> LibraryTrashPage:
    return data.library_trash(session=session, limit=limit, offset=offset, group_id=group_id)

@router.post('/library/trash/restore', dependencies=[Depends(deps.authenticate)], response_model=LibraryTrashRestoreOut, operation_id='restore_library_trash_api_v1_library_trash_restore_post')
def restore_library_trash(body: LibraryTrashSelection, session: deps.WriteSession) -> LibraryTrashRestoreOut:
    return data.restore_library_trash(session=session, body=body)

@router.post('/library/trash/delete-preview', dependencies=[Depends(deps.authenticate)], response_model=LibraryTrashPreviewOut, operation_id='library_trash_delete_preview_api_v1_library_trash_delete_preview_post')
def library_trash_delete_preview(body: LibraryTrashSelection, request: Request, session: deps.ReadSession) -> LibraryTrashPreviewOut:
    return data.plan_cleanup(session=session, settings=request.app.state.settings, body=body)

@router.post('/library/trash/delete', dependencies=[Depends(deps.authenticate)], response_model=LibraryTrashDeleteOut, operation_id='library_trash_delete_api_v1_library_trash_delete_post')
def library_trash_delete(body: LibraryTrashDelete, request: Request, session: deps.ReadSession) -> LibraryTrashDeleteOut:
    return data.delete_library_trash(session=session, database=request.app.state.database, settings=request.app.state.settings, body=body)
