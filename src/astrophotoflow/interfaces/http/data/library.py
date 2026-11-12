import asyncio
"""Typed HTTP adapters for bounded library and raw asset queries."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field

import astrophotoflow.interfaces.http.dependencies as deps
import astrophotoflow.modules.data.public as data
from astrophotoflow.contracts.assets import AssetPage, AssetQuery, LibraryChangeState, LibraryFilterOptions, LibraryItemPage, LibraryQuery
from astrophotoflow.contracts.image_management import ImagePage, ImageSearch
from astrophotoflow.contracts.library import (
    LibraryDirectoryOpened, LibraryEntryType, LibraryLocationOut, ManifestRebuildRequest,
    LibraryOrganizeRequest, LibraryOrganizeExecute, LibraryOrganizePlan, LibraryOrganizeReceipt,
)
from astrophotoflow.interfaces.application.library_organization import preflight_organization, execute_organization


class ImageAssetHttpQuery(ImageSearch):
    image_query: bool = Field(default=False, strict=False)
    q: str | None = None
    calibration_level: Literal["individual", "master"] | None = None
    optical_system_id: UUID | None = None
    role: Literal["raw", "calibration", "intermediate", "final"] | None = None

router = APIRouter(prefix="/api/v1", dependencies=[Depends(deps.authenticate)], responses=deps.ERROR_RESPONSES)


@router.get('/library/change-state', response_model=LibraryChangeState, operation_id='getLibraryChangeState')
def library_change_state(session: deps.ReadSession):
    return data.get_library_change_state(session)


@router.get("/library/items", response_model=LibraryItemPage, operation_id="searchLibrary")
def library_items(session: deps.ReadSession, query: Annotated[LibraryQuery, Query()]) -> LibraryItemPage:
    return data.search_library(session, query)


@router.get("/library/filter-options", response_model=LibraryFilterOptions, operation_id="getLibraryFilterOptions")
def library_filter_options(session: deps.ReadSession) -> LibraryFilterOptions:
    return data.get_filter_options(session)


@router.get("/library/assets", response_model=ImagePage | AssetPage, operation_id="listLibraryAssets")
def list_library_assets(session: deps.ReadSession, query: Annotated[ImageAssetHttpQuery, Query()]):
    if query.image_query:
        return ImagePage.model_validate(data.search_images(session, ImageSearch.model_validate(query.model_dump(exclude={"image_query", "q", "calibration_level", "optical_system_id", "role"}))), strict=False)
    legacy = {key: value for key, value in query.model_dump().items() if key in AssetQuery.model_fields}
    return data.list_assets(session, AssetQuery.model_validate(legacy))


@router.get('/library/locations/{entry_type}/{entry_id}', response_model=LibraryLocationOut, operation_id='getLibraryLocation')
def library_location(entry_type: LibraryEntryType, entry_id: UUID, session: deps.ReadSession, request: Request):
    return data.library_location(session, request.app.state.settings, entry_type, entry_id)


@router.post('/datasets/{dataset_id}/manifest', response_model=LibraryLocationOut, operation_id='rebuildDatasetManifest')
def rebuild_dataset_manifest(dataset_id: UUID, body: ManifestRebuildRequest, session: deps.WriteSession, request: Request):
    return data.rebuild_dataset_manifest(session, request.app.state.settings, dataset_id, body.base_revision)


@router.post('/library/locations/{entry_type}/{entry_id}/open', response_model=LibraryDirectoryOpened, operation_id='openLibraryDirectory')
def open_library_directory(entry_type: LibraryEntryType, entry_id: UUID, session: deps.ReadSession, request: Request):
    return data.open_library_directory(session, request.app.state.settings, entry_type, entry_id)


@router.post('/library/organization/plan', response_model=LibraryOrganizePlan, operation_id='planLibraryOrganization')
def plan_organization(body: LibraryOrganizeRequest, request: Request):
    state = request.app.state
    return preflight_organization(state.database, state.settings, body, state.data_exports)


@router.post('/library/organization', response_model=LibraryOrganizeReceipt, operation_id='organizeLibrary')
async def organize(body: LibraryOrganizeExecute, request: Request, admission: deps.TaskAdmission):
    state = request.app.state
    return await asyncio.to_thread(execute_organization, state.database, state.settings, body, state.data_exports)


@router.get('/library/organization/{request_id}', response_model=LibraryOrganizeReceipt, operation_id='getLibraryOrganization')
def organization_status(request_id: UUID, session: deps.ReadSession):
    return data.get_library_organization(session, request_id)
