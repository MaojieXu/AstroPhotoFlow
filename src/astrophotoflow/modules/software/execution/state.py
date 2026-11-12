"""In-process concrete invocation and preview handles."""
import asyncio
from dataclasses import dataclass, field
from uuid import UUID

from astrophotoflow.contracts.software import SoftwareInvocation, SoftwareObservation


@dataclass
class Call:
    invocation: SoftwareInvocation
    observation: SoftwareObservation
    process: asyncio.subprocess.Process | None = None
    cancelled: bool = False
    descendants: dict[int, float] = field(default_factory=dict)
    inspection_unknown: bool = False


CALLS: dict[UUID, Call] = {}


LIVE_PREVIEWS: dict[UUID, tuple[str, asyncio.subprocess.Process | None]] = {}


class ObservationFailed(RuntimeError):
    pass
