"""Capture-preset HTTP adaptation through the data public entry."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

import astrophotoflow.modules.data.public as data
from astrophotoflow.contracts.setups import CapturePresetCreate, CapturePresetOut, CapturePresetPage, CapturePresetPatch, CapturePresetQuery
from astrophotoflow.interfaces.http.dependencies import ERROR_RESPONSES, ReadSession, WriteSession, authenticate

router = APIRouter(prefix="/api/v1", dependencies=[Depends(authenticate)], responses=ERROR_RESPONSES)


@router.get("/equipment-setups/{setup_id}/presets", response_model=CapturePresetPage, response_model_exclude_unset=True, operation_id='list_setup_presets_api_v1_equipment_setups__setup_id__presets_get')
def list_setup_presets(setup_id: UUID, session: ReadSession, query: Annotated[CapturePresetQuery, Query()]) -> CapturePresetPage:
    return data.list_capture_presets(session, query.model_copy(update={"equipment_setup_id": setup_id}))


@router.get("/capture-presets", response_model=CapturePresetPage, response_model_exclude_unset=True, operation_id='list_presets_api_v1_capture_presets_get')
def list_presets(session: ReadSession, query: Annotated[CapturePresetQuery, Query()]) -> CapturePresetPage:
    return data.list_capture_presets(session, query)


@router.post("/equipment-setups/{setup_id}/presets", response_model=CapturePresetOut, status_code=201, response_model_exclude_unset=True, operation_id='create_preset_api_v1_equipment_setups__setup_id__presets_post')
def create_preset(setup_id: UUID, body: CapturePresetCreate, session: WriteSession) -> CapturePresetOut:
    return data.create_capture_preset(session, setup_id, body)


@router.get("/capture-presets/{preset_id}", response_model=CapturePresetOut, response_model_exclude_unset=True, operation_id='get_preset_api_v1_capture_presets__preset_id__get')
def get_preset(preset_id: UUID, session: ReadSession) -> CapturePresetOut:
    return data.get_capture_preset(session, preset_id)


@router.patch("/capture-presets/{preset_id}", response_model=CapturePresetOut, response_model_exclude_unset=True, operation_id='patch_preset_api_v1_capture_presets__preset_id__patch')
def patch_preset(preset_id: UUID, body: CapturePresetPatch, session: WriteSession) -> CapturePresetOut:
    return data.update_capture_preset(session, preset_id, body)
