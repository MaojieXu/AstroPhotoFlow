"""Typed replies at the native node/service boundary."""

import json
from uuid import UUID

from astrophotoflow.contracts.common import JsonValue
from astrophotoflow.contracts.software import SoftwareCallResult


def software_call_reply(value: JsonValue, prompt_id: str, call_id: str) -> SoftwareCallResult:
    result = SoftwareCallResult.model_validate_json(json.dumps(value))
    if result.prompt_id != UUID(prompt_id) or result.call_id != UUID(call_id):
        raise ValueError("Software result belongs to another native call.")
    if result.state != "completed":
        raise ValueError("Software result has not completed successfully.")
    return result
