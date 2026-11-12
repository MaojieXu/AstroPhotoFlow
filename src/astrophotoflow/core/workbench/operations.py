from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import psutil
from filelock import FileLock, Timeout

from astrophotoflow.contracts.workbench import WorkbenchResult
from astrophotoflow.core import config as app_config

from . import observations, paths, processes, state
from .errors import WorkbenchError


@contextmanager
def control_operation(config_path: Path, action: str, operation_id: UUID | None = None):
    workspace = paths.workspace_for_config(config_path)
    (workspace / "run").mkdir(parents=True, exist_ok=True)
    try:
        with FileLock(str(workspace / "run/control.lock"), timeout=5 if operation_id is not None else 0):
            previous = state.recent_result(workspace)
            previous_control = json.loads(state.control_record_path(workspace).read_text(encoding="utf-8")) if previous is not None else {}
            if previous is not None and previous.state in {"in_progress", "unknown"}:
                observed = observations.status(config_path)
                resolved = (previous.action in {"start", "restart"} and observed.ready
                            or previous.action == "stop" and observed.state == "stopped")
                if not resolved:
                    if action != "stop":
                        raise WorkbenchError("上次启停结果尚未确认；请先查询状态和日志。")
                    processes.stop_processes(config_path, control=previous_control)
            result = WorkbenchResult(operation_id=operation_id or uuid4(), action=action, state="in_progress", workspace=str(workspace),
                                     config_path=str(config_path), reused=False, web_url=None, service_url=None, detail=None,
                                     blockers=[], log_path=str(workspace / "logs"))
            owner = psutil.Process()
            control = {"result": result.model_dump(mode="json"),
                       "controller": {"pid": owner.pid, "create_time": owner.create_time()},
                       "started_at": datetime.now(UTC).isoformat(), "finished_at": None}
            if previous_control.get("pending_process") is not None:
                control["pending_process"] = previous_control["pending_process"]
            state.write_control(workspace, control)
            operation_error = None
            try:
                yield result, control
            except (OSError, ValueError, WorkbenchError, app_config.ConfigurationError, httpx.HTTPError, psutil.Error) as exc:
                operation_error = exc
                result.state, result.detail = ("unknown" if control.get("pending_process") is not None else "failed"), str(exc)
                raise WorkbenchError(str(exc)) from exc
            except BaseException as exc:
                operation_error = exc
                result.state, result.detail = "unknown", "控制操作中断，需查询进程及健康结果。"
                raise
            else:
                if result.state == "in_progress":
                    result.state = "completed"
            finally:
                control["result"] = result.model_dump(mode="json")
                control["finished_at"] = datetime.now(UTC).isoformat() if result.state != "unknown" else None
                try:
                    state.write_control(workspace, control)
                except Exception as write_error:
                    if operation_error is not None and not isinstance(operation_error, Exception):
                        operation_error.add_note(f"控制结果未能保存：{write_error}；状态需核对。")
                        raise operation_error from write_error
                    prior = f"{operation_error}；" if operation_error is not None else ""
                    raise WorkbenchError(f"{prior}控制结果未能保存：{write_error}；状态需核对。") from write_error
    except Timeout as exc:
        raise WorkbenchError("同一workspace已有启停或初始化操作，请查询当前结果。") from exc
