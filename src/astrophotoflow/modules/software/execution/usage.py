"""Read current process usage without executing operations."""
from uuid import UUID

from astrophotoflow.contracts.software import SoftwareUse
from astrophotoflow.modules.software.execution.processes import runtime_active
from astrophotoflow.modules.software.execution.state import CALLS, LIVE_PREVIEWS


def get_usage(package_id: str) -> list[SoftwareUse]:
    for call_id, call in list(CALLS.items()):
        if call.observation.runtime_ref is not None and (call.process is None or call.process.returncode is not None):
            active = runtime_active(call.observation.runtime_ref)
            call.observation = call.observation.model_copy(update={"active": active})
            if active is False:
                CALLS.pop(call_id, None)
    return [SoftwareUse(
        call_id=call.invocation.call_id, run_id=call.invocation.run_id,
        node_execution_id=call.invocation.node_execution_id,
        state="unknown" if call.observation.active is None or call.observation.state == 'unknown' else "running",
    ) for call in CALLS.values() if call.invocation.package_id == package_id
        and call.observation.active is not False]


def get_preview_usage(package_id: str) -> list[UUID]:
    for key, (_, process) in list(LIVE_PREVIEWS.items()):
        if process is not None and process.returncode is not None:
            LIVE_PREVIEWS.pop(key, None)
    return [key for key, (package, _) in LIVE_PREVIEWS.items() if package == package_id]
