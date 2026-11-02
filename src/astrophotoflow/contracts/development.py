"""Filesystem interests for local Bundle source and installation observation."""

from dataclasses import dataclass
from pathlib import Path

from pydantic import field_validator

from astrophotoflow.contracts.common import StrictModel


class BundleDevelopmentConfig(StrictModel):
    build: str
    watch: list[str]

    @field_validator('build')
    @classmethod
    def module_name(cls, value: str) -> str:
        if not value or not all(part.isidentifier() for part in value.split('.')):
            raise ValueError('Development build must name a Python module.')
        return value

    @field_validator('watch')
    @classmethod
    def contained_patterns(cls, values: list[str]) -> list[str]:
        for pattern in values:
            if not pattern or Path(pattern).is_absolute() or '..' in Path(pattern).parts:
                raise ValueError('Development watch patterns must stay inside the Bundle.')
        return values


@dataclass(frozen=True, slots=True)
class BundleWatchPath:
    path: Path
    directory: bool = False
    recursive: bool = False
