from __future__ import annotations

import json
from pathlib import Path

from filelock import FileLock

from astrophotoflow.contracts.workbench import WorkbenchResult
from astrophotoflow.core import config as app_config


def state_path(workspace: Path) -> Path:
    return workspace / "run" / "processes.json"


def read_state(workspace: Path) -> dict:
    path = state_path(workspace)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"processes": []}


def write_state(workspace: Path, state: dict) -> None:
    app_config.write_configuration_file(state_path(workspace), json.dumps(state, ensure_ascii=False, indent=2))


def control_record_path(workspace: Path) -> Path:
    return workspace / "run" / "control.json"


def write_control(workspace: Path, control: dict) -> None:
    app_config.write_configuration_file(control_record_path(workspace), json.dumps(control, ensure_ascii=False, indent=2))


def recent_result(workspace: Path) -> WorkbenchResult | None:
    path = control_record_path(workspace)
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return WorkbenchResult.model_validate_json(json.dumps(raw["result"]))


def update_running_state(workspace: Path, changes: dict) -> None:
    path = workspace / "run/processes.json"
    with FileLock(str(workspace / "run/processes.lock"), timeout=5):
        record = json.loads(path.read_text(encoding="utf-8"))
        if Path(record["workspace"]).resolve() != workspace.resolve():
            raise app_config.ConfigurationError("运行记录不属于目标workspace。")
        record.update(changes)
        app_config.write_configuration_file(path, json.dumps(record, ensure_ascii=False, indent=2))
