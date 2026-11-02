from __future__ import annotations

import json
from pathlib import Path

import httpx
import psutil

from astrophotoflow.contracts.workbench import ConfigValues, ProcessInfo, WorkbenchResult, WorkbenchState
from astrophotoflow.core import config as app_config
from astrophotoflow.core.config import resolve_config_path

from . import paths, processes, state
from .errors import WorkbenchError


def service_healthy(config_path: Path) -> bool:
    settings = app_config.load_running_settings(config_path.parent)
    try:
        token = settings.token_path.read_text(encoding="utf-8").strip()
        response = httpx.get(settings.service_url + "/api/v1/health", headers={"Authorization": f"Bearer {token}"}, timeout=2)
        return response.status_code == 200 and response.json().get("status") == "ok" and response.json().get("workspace") == str(settings.workspace)
    except (OSError, httpx.HTTPError, ValueError):
        return False


def web_healthy(url: str, workspace: Path) -> bool:
    try:
        page = httpx.get(url, timeout=2)
        health = httpx.get(url + "/astrophotoflow/api/v1/health", headers={"Origin": url}, timeout=2)
        return (page.status_code == 200 and "AstroPhotoFlow" in page.text and health.status_code == 200
                and health.json().get("workspace") == str(workspace))
    except (httpx.HTTPError, ValueError):
        return False


def status(workspace_config: Path | None = None) -> WorkbenchState:
    config_path = resolve_config_path(workspace_config)
    workspace = paths.workspace_for_config(config_path)
    result = WorkbenchState(workspace=str(workspace), config_path=str(config_path), state="stopped", ready=False,
                            web_url=None, service_url=None, processes=[], effective_settings=None, versions={}, reason=None, recent=None)
    try:
        raw = state.read_state(workspace)
        control_path = state.control_record_path(workspace)
        control = json.loads(control_path.read_text(encoding="utf-8")) if control_path.is_file() else {}
        result.recent = WorkbenchResult.model_validate_json(json.dumps(control["result"])) if control else None
        live = []
        for record in raw["processes"]:
            if processes.identify_process(record) is not None:
                live.append(ProcessInfo.model_validate_json(json.dumps(record)))
        result.processes = live
        result.web_url, result.service_url = raw.get("web_url"), raw.get("service_url")
        result.versions = raw.get("versions", {})
        if live:
            result.effective_settings = ConfigValues.model_validate(raw["effective_settings"])
            complete = {item.role for item in live} == {"asset-service", "comfyui"}
            result.ready = bool(complete and service_healthy(config_path) and result.web_url and web_healthy(result.web_url, workspace))
            result.state = "running" if result.ready else "partial"
            if not result.ready:
                result.reason = "双服务进程或workspace健康核对尚未通过。"
            if raw.get("maintenance_operation_id") is not None:
                result.ready = False
                result.reason = "维护准入仍关闭；请核对控制结果或显式停止。"
        if result.recent is not None and result.recent.state == "in_progress":
            controller = control["controller"]
            owner = psutil.Process(controller["pid"])
            if abs(owner.create_time() - controller["create_time"]) < 1.0 and owner.is_running():
                result.state = "stopping" if result.recent.action == "stop" else "starting"
                result.reason = "控制操作仍在进行；查询现有结果，不重复提交。"
            elif not result.ready:
                result.state, result.reason = "unknown", "控制进程已退出，操作结果需核对。"
        if control.get("pending_process") is not None:
            result.ready = False
            if result.state not in {"starting", "stopping"}:
                result.state = "unknown"
            pending_pid = control["pending_process"].get("pid") or "未记录"
            result.reason = f"启动进程尚未完成登记（PID {pending_pid}）；请核对并停止。"
    except psutil.NoSuchProcess:
        if control.get("pending_process") is not None:
            result.state, result.ready, result.reason = "unknown", False, "启动进程身份尚未核对，不能确认已停止。"
        elif result.recent is not None and result.recent.action == "stop" and not result.processes:
            result.state, result.reason = "stopped", "已核对记录进程均已退出。"
        elif not result.ready:
            result.state, result.reason = "unknown", "控制进程已退出，操作结果需核对。"
    except (OSError, ValueError, KeyError, TypeError, WorkbenchError, app_config.ConfigurationError, psutil.AccessDenied) as exc:
        result.state, result.ready, result.reason = "unknown", False, str(exc)
    return result
