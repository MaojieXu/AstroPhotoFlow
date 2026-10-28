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
