from typing import Literal

from pydantic import Field

from astrophotoflow.contracts.common import StrictModel


Locale = Literal['en', 'zh']


class WorkspaceLocale(StrictModel):
    locale: Locale


class DisplayLabel(StrictModel):
    label: str
    description: str = ''


class CapabilityDisplay(StrictModel):
    name: str
    description: str
    help: str
    parameters: dict[str, DisplayLabel] = Field(default_factory=dict)
    inputs: dict[str, DisplayLabel] = Field(default_factory=dict)
    outputs: dict[str, DisplayLabel] = Field(default_factory=dict)
