"""HTTP adaptation for source inspection; reading sources does not import them."""
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field

import astrophotoflow.interfaces.http.dependencies as deps
import astrophotoflow.modules.data.public as data
from astrophotoflow.contracts.image_imports import ImageInspectionOut, ImageInspectionPage, ImageInspectionRequest, InspectionQuery
from astrophotoflow.contracts.import_batches import InspectionOut, InspectionPage, SourceInspection


class ImageInspectionHttpRequest(ImageInspectionRequest):
    file_facts_only: Literal[True]


class InspectionHttpQuery(InspectionQuery):
    file_facts_only: bool = Field(default=False, strict=False)
    group_id: UUID | None = None
    kind: str = "files"

router = APIRouter(prefix='/api/v1/import-inspections', dependencies=[Depends(deps.authenticate)], responses=deps.ERROR_RESPONSES)


@router.post('', response_model=InspectionOut | ImageInspectionOut, operation_id='inspect_api_v1_import_inspections_post')
def inspect(body: SourceInspection | ImageInspectionHttpRequest, request: Request):
    if isinstance(body, ImageInspectionHttpRequest):
        return data.inspect_image_files(request.app.state.settings, ImageInspectionRequest(paths=body.paths, recursive=body.recursive))
    return data.inspection_summary(data.inspect_sources(request.app.state.settings, body))


@router.get('/{scan_id}', response_model=InspectionOut | ImageInspectionOut, operation_id='get_inspection_api_v1_import_inspections__scan_id__get')
def get_inspection(scan_id: UUID, request: Request, file_facts_only: bool = False):
    if file_facts_only:
        return data.get_image_inspection(request.app.state.settings, scan_id)
    return data.get_source_inspection(request.app.state.settings, scan_id)


@router.get('/{scan_id}/entries', response_model=ImageInspectionPage | InspectionPage, operation_id='inspection_entries_api_v1_import_inspections__scan_id__entries_get')
def inspection_entries(scan_id: UUID, request: Request, query: Annotated[InspectionHttpQuery, Query()]):
    if query.file_facts_only:
        values = query.model_dump(exclude={"file_facts_only", "group_id", "kind"})
        return data.list_image_inspection_files(request.app.state.settings, scan_id, kind=query.kind, query=InspectionQuery.model_validate(values))
    return data.list_inspection_entries(request.app.state.settings, scan_id, limit=query.limit, offset=query.offset,
                                        group_id=query.group_id, kind=query.kind)
