"""Typed HTTP adapters for bounded library and raw asset queries."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

import astrophotoflow.interfaces.http.dependencies as deps
import astrophotoflow.modules.data.public as data
from astrophotoflow.contracts.assets import AssetPage, AssetQuery, LibraryFilterOptions, LibraryItemPage, LibraryQuery

router = APIRouter(prefix="/api/v1", dependencies=[Depends(deps.authenticate)], responses=deps.ERROR_RESPONSES)


@router.get("/library/items", response_model=LibraryItemPage, operation_id="searchLibrary")
def library_items(session: deps.ReadSession, query: Annotated[LibraryQuery, Query()]) -> LibraryItemPage:
    return data.search_library(session, query)


@router.get("/library/filter-options", response_model=LibraryFilterOptions, operation_id="getLibraryFilterOptions")
def library_filter_options(session: deps.ReadSession) -> LibraryFilterOptions:
    return data.get_filter_options(session)


@router.get("/library/assets", response_model=AssetPage, operation_id="listLibraryAssets")
def list_library_assets(session: deps.ReadSession, query: Annotated[AssetQuery, Query()]) -> AssetPage:
    return data.list_assets(session, query)
