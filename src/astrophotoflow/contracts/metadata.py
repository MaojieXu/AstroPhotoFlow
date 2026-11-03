"""Shared capture metadata without asset, setup or transport dependencies."""

from math import isfinite
from typing import Literal

from pydantic import Field, field_validator, model_validator

from astrophotoflow.contracts.common import CfaPattern, StrictModel, UuidInput

FrameClass = Literal["subframe", "masterframe", "video"]

FrameType = Literal["light", "bias", "dark", "flat", "dark_flat"]

ParameterMode = Literal["iso", "gain", "standard"]

class AssetClassification(StrictModel):
    frame_class: FrameClass | None = None
    frame_type: FrameType | None = None

    @model_validator(mode="after")
    def frame_class_has_valid_type(self):
        if self.frame_class == "video" and self.frame_type is not None:
            raise ValueError("Video 不设置帧用途")
        return self



class CaptureParametersPatch(StrictModel):
    readout_mode: str | None = None
    parameter_mode: ParameterMode | None = None
    iso: int | None = Field(default=None, gt=0)
    gain: float | None = None
    offset: float | None = None
    exposure_seconds: float | None = Field(default=None, ge=0)
    integration_seconds: float | None = Field(default=None, ge=0)
    sensor_temperature_c: float | None = None
    binning_x: int | None = Field(default=None, gt=0)
    binning_y: int | None = Field(default=None, gt=0)
    cfa_pattern: CfaPattern | None = None

    @field_validator("gain", "offset", "exposure_seconds", "integration_seconds", "sensor_temperature_c")
    @classmethod
    def finite_values(cls, value):
        if value is not None and not isfinite(value):
            raise ValueError("数值必须是有限值")
        return value

class AssetParametersPatch(CaptureParametersPatch):
    camera_id: UuidInput | None = None
    optical_system_id: UuidInput | None = None
    filter_id: UuidInput | None = None


class AssetParameters(AssetParametersPatch):
    parameter_mode: ParameterMode = "standard"
