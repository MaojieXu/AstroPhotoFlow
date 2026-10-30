"""Bundle SDK v1: declarative package metadata and process plans."""
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from pydantic import JsonValue

from astrophotoflow.contracts.common import StrictModel
from astrophotoflow.contracts.inputs import ScienceFormat, ScienceSelection


class BundleManifest(StrictModel):
    schema_version: Literal[1]
    package_id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    name: str
    bundle_version: str
    release_channel: Literal['dev', 'stable'] = 'dev'
    software_version: str
    platform: Literal["windows-x86_64"]
    host_api: Literal[1, 2]
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


class BundleInputMetadata(StrictModel):
    reference_index: int = Field(ge=0)
    selection: ScienceSelection
    scientific_metadata: dict[str, JsonValue] | None


class BundleFile(StrictModel):
    path: Path
    format: ScienceFormat
    allow_empty: bool = False
    frame_count: int | None = Field(default=None, ge=1)


class OutputPattern(StrictModel):
    pattern: str
    format: ScienceFormat
    minimum_count: int = Field(default=1, ge=0)
    allow_empty: bool = False
    frame_count: int | None = Field(default=None, ge=1)


class ProcessOutput(StrictModel):
    files: list[BundleFile] = Field(default_factory=list)
    patterns: list[OutputPattern] = Field(default_factory=list)
    supporting_patterns: list[OutputPattern] = Field(default_factory=list)


class NamedProcessPlan(StrictModel):
    schema_version: Literal[2] = 2
    arguments: list[str]
    outputs: dict[str, ProcessOutput]
    temporary_directory: Path
    thread_limit: int | None = Field(default=None, ge=1)
    environment: dict[str, str] = Field(default_factory=dict)
    linear_sample: Path | None = None


class AnalysisResult(StrictModel):
    kind: Literal["metrics", "table", "series", "text", "json"]
    title: str
    source: str
    unit: str | None = None
    columns: list[str] = Field(default_factory=list)
    rows: list[list[JsonValue]] = Field(default_factory=list)
    values: dict[str, JsonValue] = Field(default_factory=dict)
    text: str | None = None
    sample: str | None = None
    member_index: int | None = Field(default=None, ge=0)


class BundleCollectedResult(StrictModel):
    outputs: dict[str, list[BundleFile]]
    supporting_outputs: dict[str, list[BundleFile]] = Field(default_factory=dict)


class BundleProgress(StrictModel):
    phase: str | None = None
    progress: float | None = Field(default=None, ge=0, le=1)


class BundlePreview(StrictModel):
    kind: Literal["science-image"]
    input: str
    max_edge: Literal[1024] = 1024
