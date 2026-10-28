from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request

from astrophotoflow.contracts.assets import AssetContentAccept, AssetContentObservation, AssetOut
from astrophotoflow.core.http import ERROR_RESPONSES, authenticate
from astrophotoflow.modules.data.science_inputs import accept_asset_content, observe_asset_content


router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)


@router.post("/library/assets/{asset_id}/content-observation", response_model=AssetContentObservation, dependencies=[Depends(authenticate)])
def observe_content(asset_id: UUID, request: Request):
    return observe_asset_content(request.app.state.database, request.app.state.settings, asset_id)


@router.post("/library/assets/{asset_id}/content-accept", response_model=AssetOut, status_code=201, dependencies=[Depends(authenticate)])
def accept_content(asset_id: UUID, body: AssetContentAccept, request: Request):
    return accept_asset_content(request.app.state.database, request.app.state.settings, asset_id, body)\n