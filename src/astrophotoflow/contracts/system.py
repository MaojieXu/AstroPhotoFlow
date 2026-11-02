"""Public observations of the local service, not mutable configuration."""

from typing import Literal

from astrophotoflow.contracts.common import StrictModel


class ServiceHealth(StrictModel):
    status: Literal["ok"]
    api_version: Literal["v1"]
    database: Literal["ready"]
    schema_revision: str
    workspace: str


class ServiceCapabilities(StrictModel):
    stage: Literal["ingestion"]
    shared_library_read: bool
    project_assets_read: bool
    project_management: bool
    equipment_management: bool
    asset_import: bool
    asset_reference_write: bool
    asset_preview: bool
    asset_metadata_edit: bool
    dataset_management: bool
    asset_task_management: bool
    calibration_matching: bool
    asset_publish: bool
