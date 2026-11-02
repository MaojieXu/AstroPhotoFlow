from pathlib import Path
from typing import Literal
from uuid import UUID

from astrophotoflow.contracts.common import ErrorDetail, StrictModel, UuidInput
from astrophotoflow.contracts.nodes import DefinitionWriteResult, NativeNodeLoad
from astrophotoflow.contracts.software import SoftwarePackage

SoftwareActionKind = Literal["install", "update", "uninstall"]


class SoftwarePlanNodeChange(StrictModel):
    definition_id: UUID
    name: str
    action: Literal["create", "update", "remove", "retain"]
    before_content_token: str | None
    after_content_token: str | None


class SoftwarePlanSummary(StrictModel):
    action: SoftwareActionKind
    package_id: str
    current_version: str | None
    target_version: str | None
    source: str | None
    install_path: Path | None
    package_token: str
    impact_token: str | None
    restart_required: bool | None
    restart_reason: str | None
    node_changes: list[SoftwarePlanNodeChange]
    current_bundle_version: str | None = None
    target_bundle_version: str | None = None
    target_tag: str | None = None
    target_commit: str | None = None
    release_token: str | None = None


class PendingSoftwareAction(StrictModel):
    operation_id: UuidInput
    state: Literal["awaiting_confirmation", "running", "completed", "failed", "expired", "unknown"]
    plan: SoftwarePlanSummary
    confirmation_url: str
    error: ErrorDetail | None


class PackageMutationResult(StrictModel):
    package: SoftwarePackage
    definition_results: list[DefinitionWriteResult]
    loads: list[NativeNodeLoad]
    error: ErrorDetail | None


class SoftwarePackageDetails(StrictModel):
    package: SoftwarePackage
    current_action: PendingSoftwareAction | None
    result: PackageMutationResult | None
