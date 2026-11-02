"""HTTP adaptation for registered and inline equipment setups."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

import astrophotoflow.modules.data.public as data
from astrophotoflow.contracts.setups import (
    EquipmentSetupCreate,
    EquipmentSetupOut,
    EquipmentSetupPage,
    EquipmentSetupPatch,
    EquipmentSetupQuery,
)
from astrophotoflow.interfaces.http.dependencies import ERROR_RESPONSES, ReadSession, WriteSession, authenticate

router = APIRouter(prefix="/api/v1", dependencies=[Depends(authenticate)], responses=ERROR_RESPONSES)


@router.get("/equipment-setups", response_model=EquipmentSetupPage, operation_id='list_setups_api_v1_equipment_setups_get')
def list_setups(session: ReadSession, query: Annotated[EquipmentSetupQuery, Query()]) -> EquipmentSetupPage:
    return data.list_setups(session, query)


@router.post("/equipment-setups", response_model=EquipmentSetupOut, status_code=201, operation_id='create_setup_api_v1_equipment_setups_post')
def create_setup(body: EquipmentSetupCreate, session: WriteSession) -> EquipmentSetupOut:
    return data.create_setup(session, body)


@router.get("/equipment-setups/{setup_id}", response_model=EquipmentSetupOut, operation_id='get_setup_api_v1_equipment_setups__setup_id__get')
def get_setup(setup_id: UUID, session: ReadSession) -> EquipmentSetupOut:
    return data.get_setup(session, setup_id)


@router.patch("/equipment-setups/{setup_id}", response_model=EquipmentSetupOut, operation_id='patch_setup_api_v1_equipment_setups__setup_id__patch')
def patch_setup(setup_id: UUID, body: EquipmentSetupPatch, session: WriteSession) -> EquipmentSetupOut:
    return data.update_setup(session, setup_id, body)
