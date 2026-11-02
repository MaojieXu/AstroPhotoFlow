from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from astrophotoflow.contracts.common import ErrorDetail, StrictModel, UuidInput
from astrophotoflow.contracts.packages import PendingSoftwareAction
from astrophotoflow.contracts.software import ConfirmSoftwareEvent


class NativePageOpenEvent(StrictModel):
    event_id: UuidInput
    page_id: UuidInput
    page_token: str
    action: Literal["open"]
    payload: None


class NativePageCloseEvent(StrictModel):
    event_id: UuidInput
    page_id: UuidInput
    page_token: str
    action: Literal["close"]
    payload: None


class NativePageConfirmSoftwareEvent(StrictModel):
    event_id: UuidInput
    page_id: UuidInput
    page_token: str
    action: Literal["confirm_software"]
    payload: ConfirmSoftwareEvent


NativePageEvent = Annotated[
    NativePageOpenEvent | NativePageCloseEvent | NativePageConfirmSoftwareEvent,
    Field(discriminator="action"),
]


class NativePageReply(StrictModel):
    event_id: UUID
    page_id: UUID
    page_token: str
    result: PendingSoftwareAction | None
    error: ErrorDetail | None
