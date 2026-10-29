"""Bundle SDK v1: declarative package metadata and process plans."""
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from astrophotoflow.contracts.common import StrictModel


class BundleManifest(StrictModel):
    schema_version: Literal[1]
    package_id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    name: str
    bundle_version: str
    release_channel: Literal['dev', 'stable'] = 'dev'
    software_version: str
    platform: Literal["windows-x86_64"]
    host_api: Literal[1]
    executable: str
    version_args: list[str]
    version_output: str
    adapter: str
    operations: list[str]
    nodes: list[str]
    output_nodes: list[str] = Field(default_factory=list)
    commands: str | None = None
    assessments: str | None = None

    @model_validator(mode='after')
    def channel_matches_version(self):
        import re
        if 'release_channel' not in self.model_fields_set and self.bundle_version in {'0.1.0', '0.1.1'}:
            return self
        pattern = r'\d+\.\d+\.\d+-dev\.\d+' if self.release_channel == 'dev' else r'\d+\.\d+\.\d+'
        if not re.fullmatch(pattern, self.bundle_version):
            raise ValueError('Bundle version must match its dev/stable release channel.')
        return self


class ProcessPlan(StrictModel):
    arguments: list[str]
    outputs: list[Path]
    output_format: str
    linear_sample: Path | None = None


class BundlePreview(StrictModel):
    kind: Literal["science-image"]
    input: str
    max_edge: Literal[1024] = 1024
