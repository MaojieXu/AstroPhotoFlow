from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from astrophotoflow.contracts.assets import AssetClassification
from astrophotoflow.contracts.calibration import CalibrationBindings
from astrophotoflow.contracts.common import ErrorDetail, StrictModel, UuidInput


InputMode = Literal["reproducible", "reference"]
ScienceFormat = Literal["fits", "xisf", "image", "raw", "video", "numpy", "other"]


class ScienceSelection(StrictModel):
    kind: Literal["whole_file", "fits_hdu"]
    hdu_index: int | None = None

    @model_validator(mode="after")
    def valid_hdu_selection(self):
        if self.kind == "fits_hdu" and (self.hdu_index is None or self.hdu_index < 0):
            raise ValueError("FITS HDU 选择需要非负索引。")
        if self.kind == "whole_file" and self.hdu_index is not None:
            raise ValueError("whole_file 选择不能包含 HDU 索引。")
        return self

class AssetInputReference(StrictModel):
    kind: Literal["asset_version"]
    asset_version_id: UuidInput
    selection: ScienceSelection


class DatasetInputMember(StrictModel):
    member_index: int = Field(ge=0)
    asset_version_id: UuidInput
    selection: ScienceSelection


class DatasetInputReference(StrictModel):
    kind: Literal["dataset_version"]
    dataset_version_id: UuidInput
    members: list[DatasetInputMember] = Field(min_length=1)


InputReference = Annotated[AssetInputReference | DatasetInputReference, Field(discriminator="kind")]


class ResolveInputsRequest(StrictModel):
    project_id: UuidInput
    references: list[InputReference] = Field(min_length=1)
    input_mode: InputMode = "reproducible"


class ResolvedAssetInput(StrictModel):
    kind: Literal["asset_version"]
    reference_index: int = Field(ge=0)
    asset_id: UUID
    asset_version_id: UUID
    dataset_version_id: UUID | None = None
    member_index: int | None = None
    asset_revision: int = Field(ge=1)
    parameters: dict
    classification: AssetClassification | None
    value_sources: dict[str, Literal["manual", "file", "preset", "unknown"]]
    capture_snapshot: dict | None
    equipment_snapshot: dict
    effective_calibration: CalibrationBindings
    read_path: Path
    format: ScienceFormat
    selection: ScienceSelection
    byte_size: int = Field(ge=0)
    content_hash: str
    mtime_ns: int = Field(ge=0)
    scientific_metadata: dict | None
    preparation: Literal["existing_managed", "materialized", "reference"]


class OutputLocator(StrictModel):
    kind: Literal["run_output"]
    run_id: UuidInput
    node_execution_id: str
    output_index: int = Field(ge=0)
    member_index: int | None = Field(default=None, ge=0)


class ResolvedOutputInput(StrictModel):
    kind: Literal["run_output"]
    reference_index: int = Field(ge=0)
    locator: OutputLocator
    read_path: Path
    format: ScienceFormat
    selection: ScienceSelection
    byte_size: int = Field(ge=0)
    content_hash: str
    mtime_ns: int = Field(ge=0)
    scientific_metadata: dict | None


ResolvedInput = Annotated[ResolvedAssetInput | ResolvedOutputInput, Field(discriminator="kind")]


class ResolvedInputs(StrictModel):
    input_mode: InputMode
    items: list[ResolvedInput]
    required_copy_bytes: int = Field(ge=0)
    copied_bytes: int = Field(ge=0)


class ReferenceObservation(StrictModel):
    input_index: int = Field(ge=0)
    observed_at: datetime
    state: Literal["unchanged", "changed", "missing", "unverified"]
    byte_size: int | None = Field(default=None, ge=0)
    mtime_ns: int | None = Field(default=None, ge=0)
    content_hash: str | None = None
    error: ErrorDetail | None = None


class CheckedOutput(StrictModel):
    run_directory: Path
    path: Path
    format: ScienceFormat
    byte_size: int = Field(ge=0)
    content_hash: str
    checked_at: datetime
    scientific_metadata: dict | None = None
