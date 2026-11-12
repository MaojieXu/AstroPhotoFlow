"""Equipment HTTP parameters and transaction dependencies."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

import astrophotoflow.modules.data.public as data
from astrophotoflow.contracts.equipment import EquipmentCreate, EquipmentOut, EquipmentPage, EquipmentPatch, EquipmentQuery
from astrophotoflow.interfaces.http.dependencies import ERROR_RESPONSES, ReadSession, WriteSession, authenticate

router = APIRouter(prefix="/api/v1", dependencies=[Depends(authenticate)], responses=ERROR_RESPONSES)


@router.get("/equipment", response_model=EquipmentPage, operation_id='list_equipment_api_v1_equipment_get')
def list_equipment(session: ReadSession, query: Annotated[EquipmentQuery, Query()]) -> EquipmentPage:
    return data.list_equipment(session, query)


@router.post("/equipment", response_model=EquipmentOut, status_code=201, operation_id='create_equipment_api_v1_equipment_post')
def create_equipment(body: EquipmentCreate, session: WriteSession) -> EquipmentOut:
    return data.create_equipment(session, body)


@router.get("/equipment/{equipment_id}", response_model=EquipmentOut, operation_id='get_equipment_api_v1_equipment__equipment_id__get')
def get_equipment(equipment_id: UUID, session: ReadSession) -> EquipmentOut:
    return data.get_equipment(session, equipment_id)


@router.patch("/equipment/{equipment_id}", response_model=EquipmentOut, operation_id='patch_equipment_api_v1_equipment__equipment_id__patch')
def patch_equipment(equipment_id: UUID, body: EquipmentPatch, session: WriteSession) -> EquipmentOut:
    return data.update_equipment(session, equipment_id, body)
