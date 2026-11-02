"""Checked file facts for one concrete native execution, never an entire graph."""

from typing import Literal

from pydantic import Field

from astrophotoflow.contracts.common import JsonObject, StrictModel, UuidInput
from astrophotoflow.contracts.inputs import CheckedOutput, ResolvedAssetInput


class CheckedResultMember(StrictModel):
    checked: CheckedOutput
    source_input: ResolvedAssetInput | None = None
    name: str
    selection: JsonObject = Field(default_factory=dict)
    display: Literal["direct", "auto"] = "direct"


class CheckedResultPort(StrictModel):
    name: str
    type: str
    members: list[CheckedResultMember]
    supporting: list[CheckedResultMember] = Field(default_factory=list)


class CheckedResult(StrictModel):
    run_id: UuidInput
    execution_id: UuidInput
    source_kind: Literal["data", "software"]
    ports: list[CheckedResultPort]
