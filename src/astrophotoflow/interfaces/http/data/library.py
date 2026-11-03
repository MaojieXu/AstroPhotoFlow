"""Typed HTTP adapters for bounded library and raw asset queries."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import Field

import astrophotoflow.interfaces.http.dependencies as deps
import astrophotoflow.modules.data.public as data
from astrophotoflow.contracts.assets import AssetPage, AssetQuery, LibraryChangeState, LibraryFilterOptions, LibraryItemPage, LibraryQuery
from astrophotoflow.contracts.image_management import ImagePage, ImageSearch


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
