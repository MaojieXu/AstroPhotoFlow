from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from astrophotoflow.contracts.common import StrictModel


class ImportRootValue(StrictModel):
    id: str
    path: str


class ConfigValues(StrictModel):
    host: str
    service_port: int
    data_dir: str
    allowed_origins: list[str]
    import_roots: list[ImportRootValue]
    file_workers: int = Field(ge=1)
    preview_workers: int = Field(ge=1)


class ConfigSave(StrictModel):
    config_token: str
    values: ConfigValues
    default_workspace: str | None = None

    @model_validator(mode="after")
    def check_default_workspace(self):
        if "default_workspace" in self.model_fields_set:
            if self.default_workspace is None or not self.default_workspace.strip():
                raise ValueError("默认 workspace 必须为非空路径；省略字段以保持原值。")
        return self


class ConfigState(StrictModel):
    config_path: str
    default_workspace: str | None
    saved: ConfigValues
    config_token: str
    effective: ConfigValues | None
    restart_required: bool


class ProcessInfo(StrictModel):
    role: Literal["asset-service", "comfyui"]
    pid: int
    create_time: float
    executable: str
    command: list[str]
    workspace: str
    started_at: datetime


class BusyState(StrictModel):
    busy: bool
    unknown: bool
    blockers: list[str]


class WorkbenchResult(StrictModel):
    operation_id: UUID
    action: Literal["initialize", "start", "stop", "restart"]
    state: Literal["in_progress", "completed", "rejected", "failed", "unknown"]
    workspace: str
    config_path: str
    reused: bool
    web_url: str | None
    service_url: str | None
    detail: str | None
    blockers: list[str]
    log_path: str | None


class WorkbenchState(StrictModel):
    workspace: str
    config_path: str
    state: Literal["stopped", "starting", "stopping", "running", "partial", "unknown"]
    ready: bool
    web_url: str | None
    service_url: str | None
    processes: list[ProcessInfo]
    effective_settings: ConfigValues | None
    versions: dict[str, str]
    reason: str | None
    recent: WorkbenchResult | None
