from typing import Literal

from fastapi import APIRouter, Depends

import astrophotoflow.interfaces.http.dependencies as deps
import astrophotoflow.modules.data.public as data
from astrophotoflow.contracts.calibration import CalibrationTargetPage

router = APIRouter(prefix="/api/v1", responses=deps.ERROR_RESPONSES)

@router.get('/calibration/targets', response_model=CalibrationTargetPage, dependencies=[Depends(deps.authenticate)], operation_id='list_calibration_targets_api_v1_calibration_targets_get')
def list_calibration_targets(session: deps.ReadSession, limit: deps.Limit=50, offset: deps.Offset=0, frame_type: Literal['bias', 'dark', 'flat', 'dark_flat'] | None=None, q: str | None=None) -> CalibrationTargetPage:
    return data.list_calibration_targets(session=session, limit=limit, offset=offset, frame_type=frame_type, q=q)
