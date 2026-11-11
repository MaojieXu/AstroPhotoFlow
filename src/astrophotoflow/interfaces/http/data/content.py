from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request

from astrophotoflow.contracts.assets import AssetContentObservation
from astrophotoflow.interfaces.http.dependencies import ERROR_RESPONSES, authenticate
from astrophotoflow.modules.data.public import observe_asset_content

router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)


@router.post("/library/assets/{asset_id}/content-observation", response_model=AssetContentObservation, dependencies=[Depends(authenticate)], operation_id='observe_content_api_v1_library_assets__asset_id__content_observation_post')
def observe_content(asset_id: UUID, request: Request):
    return observe_asset_content(request.app.state.database, request.app.state.settings, asset_id)
