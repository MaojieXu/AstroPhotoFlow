from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

import astrophotoflow.interfaces.http.dependencies as deps
import astrophotoflow.modules.data.public as data
from astrophotoflow.contracts.assets import AssetOut, AssetPatch, AssetVersionOut, AssetVersionPage, FitsHduPage, FitsHeaderOut
from astrophotoflow.interfaces.http.responses import preview_response

router = APIRouter(prefix="/api/v1", responses=deps.ERROR_RESPONSES)

@router.get('/library/assets/{asset_id}', response_model=AssetOut, dependencies=[Depends(deps.authenticate)], operation_id='get_asset_api_v1_library_assets__asset_id__get')
def get_asset(asset_id: UUID, session: deps.ReadSession) -> AssetOut:
    return data.get_asset(asset_id=asset_id, session=session)

@router.patch('/library/assets/{asset_id}', response_model=AssetOut, dependencies=[Depends(deps.authenticate)], operation_id='patch_asset_api_v1_library_assets__asset_id__patch')
def patch_asset(asset_id: UUID, body: AssetPatch, session: deps.WriteSession) -> AssetOut:
    return data.update_asset(asset_id=asset_id, body=body, session=session)

@router.get('/library/assets/{asset_id}/versions', response_model=AssetVersionPage, dependencies=[Depends(deps.authenticate)], operation_id='list_asset_versions_api_v1_library_assets__asset_id__versions_get')
def list_asset_versions(asset_id: UUID, session: deps.ReadSession, limit: deps.Limit=50, offset: deps.Offset=0) -> AssetVersionPage:
    return data.list_asset_versions(asset_id=asset_id, session=session, limit=limit, offset=offset)

@router.get('/library/assets/{asset_id}/versions/{version_id}', response_model=AssetVersionOut, dependencies=[Depends(deps.authenticate)], operation_id='get_asset_version_api_v1_library_assets__asset_id__versions__version_id__get')
def get_asset_version(asset_id: UUID, version_id: UUID, session: deps.ReadSession) -> AssetVersionOut:
    return data.get_asset_version(asset_id=asset_id, version_id=version_id, session=session)

@router.get('/library/assets/{asset_id}/versions/{version_id}/hdus', response_model=FitsHduPage, dependencies=[Depends(deps.authenticate)], operation_id='list_version_hdus_api_v1_library_assets__asset_id__versions__version_id__hdus_get')
def list_version_hdus(asset_id: UUID, version_id: UUID, session: deps.ReadSession, limit: deps.Limit=200, offset: deps.Offset=0) -> FitsHduPage:
    return data.list_version_hdus(asset_id=asset_id, version_id=version_id, session=session, limit=limit, offset=offset)

@router.get('/library/assets/{asset_id}/versions/{version_id}/hdus/{hdu_index}/header', response_model=FitsHeaderOut, dependencies=[Depends(deps.authenticate)], operation_id='get_version_header_api_v1_library_assets__asset_id__versions__version_id__hdus__hdu_index__header_get')
def get_version_header(asset_id: UUID, version_id: UUID, hdu_index: int, session: deps.ReadSession) -> FitsHeaderOut:
    return data.get_version_header(asset_id=asset_id, version_id=version_id, hdu_index=hdu_index, session=session)


@router.get("/library/assets/{asset_id}/versions/{version_id}/previews/{size}", response_class=Response,
            responses={200: {"content": {"image/jpeg": {"schema": {"type": "string", "format": "binary"}}}}},
            dependencies=[Depends(deps.authenticate)], operation_id='get_version_preview_api_v1_library_assets__asset_id__versions__version_id__previews__size__get')
def get_version_preview(asset_id: UUID, version_id: UUID, size: str, request: Request, session: deps.ReadSession) -> Response:
    reference = data.get_asset_preview_reference(session, asset_id, version_id)
    return preview_response(request, reference, size)
