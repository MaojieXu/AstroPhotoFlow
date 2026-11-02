from typing import Literal
from uuid import UUID

from pydantic import Field

from astrophotoflow.contracts.common import StrictModel


class AutoStretch(StrictModel):
    algorithm: Literal["auto-mtf-1"] = "auto-mtf-1"
    input_offset: float
    white_balance: list[float] = Field(min_length=1, max_length=3)
    shadows: float
    highlights: float
    midtones: float


class PreviewIssue(StrictModel):
    code: str
    message: str


class DisplayPreviewState(StrictModel):
    asset_version_id: UUID
    size: Literal["display"] = "display"
    status: Literal["not_ready", "generating", "available", "failed", "unsupported"]
    width: int | None = None
    height: int | None = None
    error: PreviewIssue | None = None
    stretch: AutoStretch | None = None
