"""Current calibration facts, independent of pending Master bindings."""

from typing import Literal

from pydantic import Field

from astrophotoflow.contracts.common import JsonObject, StrictModel

CalibrationStatus = Literal['UnCalibrated', 'Calibrated', 'Unknown']
CALIBRATION_STATUSES = ('UnCalibrated', 'Calibrated', 'Unknown')


class CalibrationDeclaration(StrictModel):
    calibration_status: CalibrationStatus = 'Unknown'
    calibration_reason: str | None = Field(default=None, min_length=1)


class CalibrationState(StrictModel):
    calibration_status: CalibrationStatus
    calibration_evidence: JsonObject = Field(default_factory=dict)


class CalibrationSummary(StrictModel):
    calibration_status: CalibrationStatus
    calibration_counts: dict[CalibrationStatus, int]


class CalibrationEffect(StrictModel):
    """Declared behavior for successful science outputs of one operation."""

    behavior: Literal['unknown', 'preserve', 'calibrate'] = 'unknown'
    input: str | None = None
    outputs: list[str] = Field(default_factory=list)
    masters: dict[Literal['bias', 'dark', 'flat', 'dark_flat'], str] = Field(default_factory=dict)
    parameter_calibrations: JsonObject = Field(default_factory=dict)
