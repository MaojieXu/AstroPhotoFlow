"""HTTP adaptation for source inspection; reading sources does not import them."""
from uuid import UUID

from fastapi import APIRouter, Depends, Request

import astrophotoflow.interfaces.http.dependencies as deps
import astrophotoflow.modules.data.public as data
from astrophotoflow.contracts.import_batches import InspectionOut, InspectionPage, SourceInspection

router = APIRouter(prefix='/api/v1/import-inspections', dependencies=[Depends(deps.authenticate)], responses=deps.ERROR_RESPONSES)


@router.post('', response_model=InspectionOut, operation_id='inspect_api_v1_import_inspections_post')
def inspect(body: SourceInspection, request: Request):
    return data.inspection_summary(data.inspect_sources(request.app.state.settings, body))


@router.get('/{scan_id}', response_model=InspectionOut, operation_id='get_inspection_api_v1_import_inspections__scan_id__get')
def get_inspection(scan_id: UUID, request: Request):
    return data.get_source_inspection(request.app.state.settings, scan_id)


@router.get('/{scan_id}/entries', response_model=InspectionPage, operation_id='inspection_entries_api_v1_import_inspections__scan_id__entries_get')
def inspection_entries(scan_id: UUID, request: Request, limit: deps.Limit = 50, offset: deps.Offset = 0,
                       group_id: UUID | None = None, kind: str = 'files'):
    return data.list_inspection_entries(request.app.state.settings, scan_id, limit=limit, offset=offset,
                                        group_id=group_id, kind=kind)
