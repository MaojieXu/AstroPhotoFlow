from astrophotoflow.contracts.common import CfaPattern, StrictModel, UuidInput, check_name
from datetime import datetime
from math import isfinite
from pydantic import Field, field_validator, model_validator
from typing import Any, Literal
from uuid import UUID


class AssetVersionOut(StrictModel):
    id: UUID
    asset_id: UUID
    version_number: int
    storage_mode: Literal["reference", "managed"]
    storage_location: str
    byte_size: int | None
    content_hash: str | None
    availability: Literal["unknown", "available", "changed", "missing"]
    camera_id: UuidInput | None
    optical_system_id: UuidInput | None
    filter_id: UuidInput | None
    frame_type: Literal["light", "bias", "dark", "flat", "dark_flat"] | None
    calibration_level: Literal["individual", "master"] | None
    capture_snapshot: dict | None
    scientific_metadata: dict | None
    created_at: datetime


class AssetOut(StrictModel):
    id: UUID
    name: str
    scope: Literal["shared", "project"]
    owner_project_id: UUID | None
    role: Literal["raw", "calibration", "intermediate", "final"]
    calibration_level: Literal["individual", "master"] | None
    current_version_id: UUID | None
    classification: dict | None
    parameters: dict
    equipment_snapshot: dict
    value_sources: dict
    notes: str | None
    status: Literal["active", "archived"]
    revision: int
    created_at: datetime
    current_version: AssetVersionOut | None


class AssetPage(StrictModel):
    items: list[AssetOut]
    total: int
    limit: int
    offset: int


class LibraryAssetItemOut(StrictModel):
    entry_type: Literal["asset"]
    asset: AssetOut
    import_issue: str | None


class AssetVersionPage(StrictModel):
    items: list[AssetVersionOut]
    total: int
    limit: int
    offset: int


class FilterEquipmentOption(StrictModel):
    id: UUID
    name: str


class NumericRangeOut(StrictModel):
    min: float
    max: float


class LibraryFilterOptions(StrictModel):
    frame_classes: list[str]
    frame_types: list[str]
    roles: list[str]
    parameter_modes: list[str]
    bin_values: list[str]
    equipment: dict[str, list[FilterEquipmentOption]]
    numeric_ranges: dict[str, NumericRangeOut]


class FitsHduOut(StrictModel):
    id: UUID
    asset_version_id: UUID
    hdu_index: int
    name: str | None
    hdu_type: str
    shape: list[int] | None
    bitpix: int | None
    pixel_type: str | None
    bscale: float | None
    bzero: float | None
    bunit: str | None
    parser_version: str
    supported_kind: Literal["mono", "bayer", "rgb", "xtrans", "quad_bayer"] | None
    is_selected: bool
    parse_error: str | None


class FitsHduPage(StrictModel):
    items: list[FitsHduOut]
    total: int
    limit: int
    offset: int


class FitsHeaderOut(StrictModel):
    asset_version_id: UUID
    hdu_index: int
    cards: list[dict[str, Any]]


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


class AssetClassificationPatch(StrictModel):
    frame_class: FrameClass | None = None
    frame_type: FrameType | None = None

    @model_validator(mode="after")
    def video_has_no_frame_type(self):
        if self.frame_class == "video" and self.frame_type is not None:
            raise ValueError("Video 不设置帧用途")
        return self


class AssetParameters(StrictModel):
    camera_id: UuidInput | None = None
    optical_system_id: UuidInput | None = None
    filter_id: UuidInput | None = None
    parameter_mode: ParameterMode = "standard"
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


class AssetParametersPatch(StrictModel):
    camera_id: UuidInput | None = None
    optical_system_id: UuidInput | None = None
    filter_id: UuidInput | None = None
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


class AssetPatch(StrictModel):
    base_revision: int = Field(ge=1)
    name: str | None = None
    notes: str | None = None
    classification: AssetClassificationPatch | None = None
    parameters: AssetParametersPatch | None = None
    status: Literal["active", "archived"] | None = None

    @field_validator("name")
    @classmethod
    def valid_name(cls, value):
        return None if value is None else check_name(value)

    @model_validator(mode="after")
    def reject_null_objects(self):
        for field in ("classification", "parameters"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} 不能为 null，请传对象")
        return self
