"""Typed replies at the native node/service boundary."""

import json
from uuid import UUID

from astrophotoflow.contracts.common import JsonValue
from astrophotoflow.contracts.software import SoftwareCallResult


class SoftwareCallBlocked(RuntimeError):
    """The requested call was blocked by another use of its software."""


class SoftwareCallUnknown(RuntimeError):
    """The original call requires observation before another execution."""


def software_call_error(record: dict, prompt_id: str, call_id: str) -> RuntimeError:
    error = record.get('error') or (record.get('result') or {}).get('error') or {}
    message = error.get('message') or f"软件操作状态为 {record['state']}，请检查本次运行日志。"
    message += f'\n调用日志：/astrophotoflow/api/v1/runs/{prompt_id}/calls/{call_id}/log'
    if error.get('code') == 'SOFTWARE_BUSY':
        return SoftwareCallBlocked(message)
    if record['state'] == 'unknown':
        return SoftwareCallUnknown(message)
    return RuntimeError(message)


def software_call_reply(value: JsonValue, prompt_id: str, call_id: str) -> SoftwareCallResult:
    result = SoftwareCallResult.model_validate_json(json.dumps(value))
    if result.prompt_id != UUID(prompt_id) or result.call_id != UUID(call_id):
        raise ValueError("Software result belongs to another native call.")
    if result.state != "completed":
        raise ValueError("Software result has not completed successfully.")
    return result
