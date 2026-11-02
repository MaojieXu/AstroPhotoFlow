"""Typed concrete software facts; checked file facts belong to data."""
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID

from astrophotoflow.contracts.software_calls import SoftwareCallRecord
from astrophotoflow.core.config import Settings
from astrophotoflow.core.errors import ApiError
from astrophotoflow.core.files import replace_file


def call_record_path(settings: Settings, prompt_id: UUID, call_id: UUID) -> Path:
    return settings.workspace / 'runs' / str(UUID(str(prompt_id))) / 'calls' / (str(UUID(str(call_id))) + '.json')


def check_record_identity(record: SoftwareCallRecord, prompt_id: UUID, call_id: UUID) -> None:
    if record.request.prompt_id != prompt_id or record.request.call_id != call_id:
        raise ValueError('Software record identity does not match its storage path.')


def read_software_call(settings: Settings, prompt_id: UUID, call_id: UUID) -> SoftwareCallRecord:
    value = find_software_call(settings, prompt_id, call_id)
    if value is None:
        raise ApiError(404, 'RESOURCE_NOT_FOUND', 'Software invocation not found.', message_key='software_call_not_found')
    return value


def find_software_call(settings: Settings, prompt_id: UUID, call_id: UUID) -> SoftwareCallRecord | None:
    path = call_record_path(settings, prompt_id, call_id)
    if not path.is_file():
        return None
    record = SoftwareCallRecord.model_validate_json(path.read_bytes())
    check_record_identity(record, prompt_id, call_id)
    return record


def save_software_call(settings: Settings, prompt_id: UUID, call_id: UUID, value: SoftwareCallRecord) -> None:
    if not isinstance(value, SoftwareCallRecord):
        raise TypeError('Software call persistence requires a typed SoftwareCallRecord.')
    payload = value.model_dump_json(indent=2)
    record = SoftwareCallRecord.model_validate_json(payload)
    check_record_identity(record, prompt_id, call_id)
    path = call_record_path(settings, prompt_id, call_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix('.part')
    pending.write_text(payload + '\n', encoding='utf-8')
    replace_file(pending, path)


def list_software_call_records(settings: Settings, prompt_id: UUID) -> list[tuple[UUID, SoftwareCallRecord]]:
    folder = settings.workspace / 'runs' / str(prompt_id) / 'calls'
    return [(UUID(path.stem), read_software_call(settings, prompt_id, UUID(path.stem)))
            for path in sorted(folder.glob('*.json'))]


def unfinished_software_calls(settings: Settings) -> Iterator[tuple[UUID, UUID, SoftwareCallRecord]]:
    for path in (settings.workspace / 'runs').glob('*/calls/*.json'):
        prompt_id, call_id = UUID(path.parent.parent.name), UUID(path.stem)
        record = read_software_call(settings, prompt_id, call_id)
        if record.state in {'starting', 'running', 'unknown'}:
            yield prompt_id, call_id, record


def software_call_log(settings: Settings, prompt_id: UUID, call_id: UUID) -> Path:
    read_software_call(settings, prompt_id, call_id)
    path = settings.workspace / 'runs' / str(prompt_id) / 'work' / str(call_id) / 'siril.log'
    if not path.is_file():
        raise ApiError(404, 'RESOURCE_NOT_FOUND', 'Program log is not available.', message_key='software_log_unavailable')
    return path
