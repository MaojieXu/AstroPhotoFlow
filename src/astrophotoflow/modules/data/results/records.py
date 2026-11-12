"""One immutable checked-result record per prompt and execution UUID."""
import json
from pathlib import Path
from uuid import UUID
from filelock import FileLock
from astrophotoflow.contracts.results import CheckedResult
from astrophotoflow.core.config import Settings
from astrophotoflow.core.errors import ApiError, not_found

def result_record_path(settings: Settings, run_id: UUID, execution_id: UUID) -> Path:
    return settings.workspace / 'runs' / str(UUID(str(run_id))) / 'results' / (str(UUID(str(execution_id))) + '.json')

def get_checked_result(settings: Settings, run_id: UUID, execution_id: UUID) -> CheckedResult:
    path = result_record_path(settings, run_id, execution_id)
    if not path.is_file():
        raise not_found()
    result = CheckedResult.model_validate_json(path.read_bytes())
    if result.run_id != UUID(str(run_id)) or result.execution_id != UUID(str(execution_id)):
        raise ApiError(409, 'RESULT_IDENTITY_CONFLICT', 'Checked result identity differs from its address.', message_key='result_record_identity_mismatch')
    return result

def save_checked_result(settings: Settings, result: CheckedResult) -> CheckedResult:
    path = result_record_path(settings, result.run_id, result.execution_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(str(path.with_suffix('.lock'))):
        if path.exists():
            previous = get_checked_result(settings, result.run_id, result.execution_id)
            if previous != result:
                raise ApiError(409, 'RESULT_CONTENT_CONFLICT', 'Execution already owns different checked output facts.', message_key='result_execution_identity_conflict')
            return previous
        part = path.with_suffix('.part')
        part.write_text(result.model_dump_json(indent=2), encoding='utf-8')
        part.replace(path)
    return result

def data_execution_directory(settings, run_id, execution_id):
    return settings.workspace / 'runs' / str(UUID(str(run_id))) / 'data' / str(UUID(str(execution_id)))

def read_data_execution(settings, run_id, execution_id):
    path = data_execution_directory(settings, run_id, execution_id) / 'result.json'
    if not path.is_file():
        raise not_found()
    return json.loads(path.read_text(encoding='utf-8'))

def save_data_execution(path, value):
    part = path.with_suffix('.part')
    part.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    part.replace(path)
