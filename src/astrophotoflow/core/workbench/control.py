from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

import httpx
import psutil
from filelock import FileLock, Timeout

from astrophotoflow.contracts.workbench import BusyState, WorkbenchResult
from astrophotoflow.core import config as app_config
from astrophotoflow.core.config import resolve_config_path

from . import observations, operations, paths, processes, state
from .errors import WorkbenchError

logger = logging.getLogger(__name__)


def choose_port(host: str, preferred: int, *, exclude: int | None = None) -> int:
    for port in range(preferred, 65536):
        if port != exclude and processes.port_available(host, port):
            return port
    raise WorkbenchError("没有可用端口，请修改首选端口后重试。")


def start_services(config_path: Path, result: WorkbenchResult, control: dict) -> None:
    workspace = config_path.parent
    observed = observations.status(config_path)
    if observed.ready:
        result.reused, result.web_url, result.service_url = True, observed.web_url, observed.service_url
        result.detail = "已核对并复用当前workspace。"
        return
    if observed.processes or observed.state in {"partial", "unknown"}:
        raise WorkbenchError("工作台进程尚未全部停止或状态无法确认；先核对并停止原实例。")
    values = app_config.get_configuration(config_path).saved
    settings = app_config.settings_from_values(values, config_path)
    preferred_web = urlsplit(settings.allowed_origins[0]).port
    if preferred_web == settings.port:
        raise WorkbenchError("资产服务与ComfyUI必须配置为不同端口。")
    service_port = choose_port(settings.host, settings.port)
    web_port = choose_port("127.0.0.1", preferred_web, exclude=service_port)
    web_url = f"http://127.0.0.1:{web_port}"
    origins = [f"http://{urlsplit(origin).hostname if urlsplit(origin).hostname == 'localhost' else '127.0.0.1'}:{web_port}"
               for origin in values.allowed_origins]
    values = values.model_copy(update={"service_port": service_port, "allowed_origins": origins})
    effective = app_config.settings_from_values(values, config_path)
    runtime = paths.runtime_dir()
    comfyui = runtime / "ComfyUI"
    if not (workspace / "web/index.html").is_file():
        raise WorkbenchError("当前workspace缺少原生网页资源；请先运行apf init。")
    env = os.environ.copy()
    env.update({"ASTROPHOTOFLOW_CONFIG": str(config_path), "APF_WORKSPACE": str(workspace),
                "PYTHONPATH": str(paths.package_directory().parent)})
    service_command = [sys.executable, "-m", "astrophotoflow.interfaces.http.cli", "serve"]
    comfy_python = runtime / "comfyui-env" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    comfy_command = [str(comfy_python), str(comfyui / "main.py"), "--cpu", "--listen", "127.0.0.1", "--port", str(web_port),
                     "--base-directory", str(workspace / "comfyui-data"), "--user-directory", str(workspace / "comfyui-user"),
                     "--input-directory", str(workspace / "input"), "--output-directory", str(workspace / "output"),
                     "--front-end-root", str(workspace / "web"), "--disable-all-custom-nodes", "--disable-api-nodes"]
    manifest = json.loads((paths.package_directory() / "vendor/comfyui-source.json").read_text(encoding="utf-8"))
    record = {"workspace": str(workspace), "config_path": str(config_path), "effective_settings": values.model_dump(),
              "web_url": web_url, "service_url": effective.service_url,
              "actual_ports": {"service": service_port, "web": web_port}, "processes": [], "maintenance_operation_id": None,
              "versions": {"platform": version("astrophotoflow"), "comfyui": manifest["comfyui_version"]}}
    state.write_state(workspace, record)
    pending_child = None
    try:
        launched = []
        for command, cwd, role, timeout in ((service_command, workspace, "asset-service", 90),
                                            (comfy_command, comfyui, "comfyui", 180)):
            control["pending_process"] = {"role": role, "pid": None, "command": command, "workspace": str(workspace),
                                          "started_at": datetime.now(UTC).isoformat(), "launch_started": time.time()}
            state.write_control(workspace, control)
            child = processes.launch_process(command, cwd, env, workspace / "logs" / ("service.log" if role == "asset-service" else "comfyui.log"))
            pending_child = child
            control["pending_process"].update({"pid": child.pid, "launch_finished": time.time()})
            state.write_control(workspace, control)
            control["pending_process"] = processes.record_process(child, role, workspace, command)
            state.write_control(workspace, control)
            record["processes"].append(control["pending_process"])
            state.update_running_state(workspace, {"processes": record["processes"]})
            control.pop("pending_process")
            state.write_control(workspace, control)
            pending_child = None
            ready = (lambda path=config_path: observations.service_healthy(path)) if role == "asset-service" \
                else (lambda: observations.web_healthy(web_url, workspace))
            launched.append({"role": role, "process": child, "timeout": timeout, "ready": ready,
                             "deadline": time.monotonic() + timeout})
        waiting = {entry["role"]: entry for entry in launched}
        while waiting:
            for role, entry in list(waiting.items()):
                if entry["process"].poll() is not None:
                    raise WorkbenchError(f"{role}启动失败；请查看workspace/logs。")
                if entry["ready"]():
                    waiting.pop(role)
            if not waiting:
                break
            for role, entry in waiting.items():
                if time.monotonic() >= entry["deadline"]:
                    raise WorkbenchError(f"{role}未能在{entry['timeout']}秒内就绪；请查看workspace/logs。")
            time.sleep(0.25)
    except Exception as startup_error:
        if pending_child is None and control.get("pending_process", {}).get("pid") is None:
            control.pop("pending_process", None)
        try:
            processes.stop_processes(config_path, control=control, pending_child=pending_child)
        except Exception as cleanup_error:
            logger.exception("Startup cleanup failed")
            identity_detail = ""
            if pending_child is not None and control.get("pending_process") is not None and "create_time" not in control["pending_process"]:
                try:
                    control["pending_process"] = processes.record_process(pending_child, role, workspace, command)
                except Exception as identity_error:
                    logger.exception("Pending process identity could not be recorded")
                    identity_detail = f"；PID {pending_child.pid} 身份尚未确认：{identity_error}"
            raise WorkbenchError(
                f"{startup_error} 启动失败后的停止未完成：{cleanup_error}{identity_detail}"
            ) from startup_error
        raise
    result.web_url, result.service_url = web_url, effective.service_url


def operate_control(action: str, workspace_config: Path | None, operation_id: UUID | None = None) -> WorkbenchResult:
    config_path = resolve_config_path(workspace_config)
    with operations.control_operation(config_path, action, operation_id) as (result, control):
        if action == "start":
            start_services(config_path, result, control)
        elif action == "stop":
            if state.read_state(config_path.parent)["processes"] or control.get("pending_process") is not None:
                processes.stop_processes(config_path, control=control)
        else:
            observed = observations.status(config_path)
            if observed.processes:
                if not observed.ready:
                    result.state, result.blockers = "rejected", [observed.reason or "服务未完全就绪，无法确认空闲"]
                    return result
                settings = app_config.load_running_settings(config_path.parent)
                token = settings.token_path.read_text(encoding="utf-8").strip()
                try:
                    response = httpx.post(settings.service_url + "/internal/maintenance",
                                          json={"action": "enter", "operation_id": str(result.operation_id)},
                                          headers={"Authorization": f"Bearer {token}"}, timeout=5)
                    response.raise_for_status()
                    busy = BusyState.model_validate(response.json())
                    if busy.busy or busy.unknown:
                        result.state, result.blockers = "rejected", busy.blockers
                        return result
                except (httpx.HTTPError, ValueError) as exc:
                    result.state, result.blockers = "rejected", [f"无法确认工作台空闲：{exc}"]
                    return result
                finally:
                    if result.state == "rejected":
                        try:
                            released = httpx.post(settings.service_url + "/internal/maintenance",
                                                  json={"action": "release", "operation_id": str(result.operation_id)},
                                                  headers={"Authorization": f"Bearer {token}"}, timeout=5)
                            released.raise_for_status()
                            release_state = BusyState.model_validate(released.json())
                            if release_state.busy or release_state.unknown:
                                result.blockers.extend(release_state.blockers)
                        except (httpx.HTTPError, ValueError) as release_error:
                            result.blockers.append(f"本次维护释放未确认，需查询或显式停止：{release_error}")
            elif observed.state == "unknown":
                result.state, result.blockers = "rejected", [observed.reason or "无法确认进程已停止"]
                return result
            processes.stop_processes(config_path, control=control)
            start_services(config_path, result, control)
        return result


def start(workspace_config: Path | None = None) -> WorkbenchResult:
    return operate_control("start", workspace_config)


def stop(workspace_config: Path | None = None) -> WorkbenchResult:
    return operate_control("stop", workspace_config)


def restart(workspace_config: Path | None = None, *, operation_id: UUID | None = None) -> WorkbenchResult:
    return operate_control("restart", workspace_config, operation_id)


def request_restart(workspace_config: Path, operation_id: UUID) -> WorkbenchResult:
    config_path = resolve_config_path(workspace_config)
    workspace = config_path.parent
    receipt = workspace / "run/web-restart.json"
    try:
        with FileLock(str(workspace / "run/control.lock"), timeout=0):
            if receipt.is_file():
                previous = json.loads(receipt.read_text(encoding="utf-8"))
                result = WorkbenchResult.model_validate_json(json.dumps(previous["result"]))
                if result.operation_id == operation_id:
                    return result
                if result.state == "in_progress":
                    try:
                        owner = psutil.Process(previous["controller"]["pid"])
                        if abs(owner.create_time() - previous["controller"]["create_time"]) < 1.0:
                            raise WorkbenchError("已有网页重启正在进行，请查询现有结果。")
                    except psutil.NoSuchProcess:
                        pass
            log_path = workspace / "logs/web-restart.log"
            result = WorkbenchResult(operation_id=operation_id, action="restart", state="in_progress",
                                     workspace=str(workspace), config_path=str(config_path), reused=False,
                                     web_url=None, service_url=None, detail=None, blockers=[], log_path=str(log_path))
            env = os.environ.copy()
            env["PYTHONPATH"] = str(paths.package_directory().parent)
            command = [sys.executable, "-c",
                       ("import sys; from pathlib import Path; from uuid import UUID; "
                       "from astrophotoflow.core.workbench.control import run_web_restart; "
                       "run_web_restart(Path(sys.argv[1]), UUID(sys.argv[2]))"),
                       str(config_path), str(operation_id)]
            parent = psutil.Process()
            pending = {"result": result.model_dump(mode="json"),
                       "controller": {"pid": parent.pid, "create_time": parent.create_time()}}
            app_config.write_configuration_file(receipt, json.dumps(pending))
            try:
                child = processes.launch_process(command, workspace, env, log_path)
            except OSError as exc:
                result.state, result.detail = "failed", str(exc)
                pending["result"] = result.model_dump(mode="json")
                app_config.write_configuration_file(receipt, json.dumps(pending))
                raise
            owner = psutil.Process(child.pid)
            pending["controller"] = {"pid": child.pid, "create_time": owner.create_time()}
            app_config.write_configuration_file(receipt, json.dumps(pending))
            return result
    except Timeout as exc:
        raise WorkbenchError("已有启停操作正在进行，请稍后查询状态。") from exc


def run_web_restart(config_path: Path, operation_id: UUID) -> None:
    receipt = config_path.parent / "run/web-restart.json"
    try:
        result = restart(config_path, operation_id=operation_id)
    except (OSError, ValueError, WorkbenchError, app_config.ConfigurationError, psutil.Error) as exc:
        result = WorkbenchResult(operation_id=operation_id, action="restart", state="unknown",
                                 workspace=str(config_path.parent), config_path=str(config_path), reused=False,
                                 web_url=None, service_url=None, detail=str(exc), blockers=[],
                                 log_path=str(config_path.parent / "logs/web-restart.log"))
    raw = json.loads(receipt.read_text(encoding="utf-8"))
    raw["result"] = result.model_dump(mode="json")
    app_config.write_configuration_file(receipt, json.dumps(raw))


def restart_result(workspace_config: Path, operation_id: UUID) -> WorkbenchResult | None:
    receipt = resolve_config_path(workspace_config).parent / "run/web-restart.json"
    if not receipt.is_file():
        return None
    raw = json.loads(receipt.read_text(encoding="utf-8"))
    result = WorkbenchResult.model_validate_json(json.dumps(raw["result"]))
    if result.operation_id != operation_id:
        return None
    if result.state == "in_progress":
        try:
            owner = psutil.Process(raw["controller"]["pid"])
            if abs(owner.create_time() - raw["controller"]["create_time"]) >= 1.0:
                result.state, result.detail = "unknown", "重启控制进程身份已变化，请查询实际状态。"
        except psutil.NoSuchProcess:
            result.state, result.detail = "unknown", "重启控制进程已退出，结果尚未确认。"
    return result
