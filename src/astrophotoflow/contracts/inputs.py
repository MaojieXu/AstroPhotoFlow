from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, model_validator

from astrophotoflow.contracts.calibration import CalibrationBindings
from astrophotoflow.contracts.common import ErrorDetail, StrictModel, UuidInput
from astrophotoflow.contracts.metadata import AssetClassification
from astrophotoflow.contracts.snapshots import VersionCaptureSnapshot

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


class CanvasDataRequest(StrictModel):
    entry_type: Literal["asset", "dataset"]
    id: UuidInput
    version_id: UuidInput
    member_indexes: list[int] | None = None

    @model_validator(mode="after")
    def valid_members(self):
        if self.member_indexes is not None:
            if self.entry_type != "dataset" or not self.member_indexes:
                raise ValueError("只有图像组可以指定非空成员范围。")
            if self.member_indexes != sorted(set(self.member_indexes)) or self.member_indexes[0] < 0:
                raise ValueError("成员索引必须非负、不重复并保持原顺序。")
        return self


class CanvasDataOut(StrictModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    native_type: Literal["APF_DATA_REFERENCE", 'APF_FILE_REFERENCE'] = "APF_DATA_REFERENCE"
    title: str
    reference: InputReference


class CanvasInspectRequest(StrictModel):
    reference: InputReference
    member_index: int = Field(default=0, ge=0)


class CanvasInspectOut(StrictModel):
    title: str
    total: int
    member_index: int
    asset_id: UuidInput
    asset_version_id: UuidInput
    view_base: str
    name: str
    availability: Literal["unknown", "available", "changed", "missing"]
    parameters: dict
    equipment: dict[str, str | None]
    format: str | None
    width: int | None
    height: int | None
    bitpix: int | None
    pixel_type: str | None
    preview_status: Literal["available", "pending", "failed", "unsupported", "not_ready"]
    preview_url: str | None
    preview_error: str | None
    byte_size: int | None = Field(default=None, ge=0)
    content_hash: str | None = None


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
    capture_snapshot: VersionCaptureSnapshot | None
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
    execution_id: UuidInput
    output_index: int = Field(ge=0)
    member_index: int | None = Field(default=None, ge=0)


class ResolvedOutputInput(StrictModel):
    kind: Literal["run_output"]
    reference_index: int = Field(ge=0)
    locator: OutputLocator
    source_input: ResolvedAssetInput | None = None
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
    mtime_ns: int | None = Field(default=None, ge=0)
