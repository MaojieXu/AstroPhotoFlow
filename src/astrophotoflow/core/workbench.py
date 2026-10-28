from __future__ import annotations

import hashlib
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib.metadata import version
from uuid import UUID, uuid4
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import zipfile
from urllib.parse import urlsplit

import httpx
import psutil
from filelock import FileLock, Timeout

from astrophotoflow.contracts.workbench import BusyState, ConfigValues, ProcessInfo, WorkbenchResult, WorkbenchState

from astrophotoflow.core import config as app_config
from astrophotoflow.core.config import Settings, load_settings, resolve_config_path
from astrophotoflow.core.errors import ApiError


COMFY_COMMIT = "1a82e6d01f395b43275c77acd289af1eb7090bb9"
TORCH_CPU = "2.14.1+cpu"
TORCHVISION_CPU = "0.29.1+cpu"
TORCH_CPU_INDEX = "https://download.pytorch.org/whl/cpu"


class WorkbenchError(RuntimeError):
    pass


def _app_data() -> Path:
    if os.name == "nt":
        return Path(os.environ["LOCALAPPDATA"]) / "AstroPhotoFlow"
    return Path.home() / ".local" / "share" / "astrophotoflow"


def _runtime_dir() -> Path:
    return _app_data() / "runtime" / "native-web-0.1.0"


def _active_config() -> Path:
    return resolve_config_path()


def _workspace_for_config(path: Path) -> Path:
    if path.name != "config.toml":
        raise WorkbenchError("workspace 配置文件必须命名为 config.toml。")
    return path.parent


def _load_config(path: Path) -> tuple[Settings, int, str, int]:
    settings = load_settings(path)
    parsed = urlsplit(settings.allowed_origins[0])
    if settings.port == parsed.port:
        raise WorkbenchError("资产服务与 ComfyUI 必须使用不同端口。")
    return settings, settings.port, settings.host, parsed.port


def _uv() -> str:
    executable = Path(sys.executable).with_name("uv.exe" if os.name == "nt" else "uv")
    if executable.is_file():
        return str(executable)
    found = shutil.which("uv")
    if found:
        return found
    raise WorkbenchError("找不到 uv。请在当前 Python 环境中安装产品依赖后重试。")


def _uv_environment(runtime: Path) -> dict[str, str]:
    python_bin_dir = runtime / "python-bin"
    cache_dir = runtime / "uv-cache"
    python_bin_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["UV_PYTHON_BIN_DIR"] = str(python_bin_dir)
    environment["UV_PYTHON_INSTALL_REGISTRY"] = "0"
    environment["UV_CACHE_DIR"] = str(cache_dir)
    return environment


def _run(command: list[str], env: dict[str, str] | None = None) -> None:
    subprocess.run(command, check=True, env=env)


def install_frontend(workspace: Path, frontend_assets: Path | None = None) -> Path:
    package = Path(__file__).resolve().parents[1]
    source = frontend_assets if frontend_assets is not None else package / "web"
    if not (source / "index.html").is_file():
        raise WorkbenchError(f"原生网页资源不存在：{source / 'index.html'}")
    target = workspace / "web"
    shutil.copytree(source, target, dirs_exist_ok=True)
    return target


def _initialize(workspace: Path, service_port: int = 8190, comfyui_port: int = 8188, *,
               frontend_assets: Path | None = None, activate: bool = True,
               reuse_runtime: bool = False) -> Path:
    workspace = workspace.expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    config_path = workspace / "config.toml"
    if not 1 <= service_port <= 65535 or not 1 <= comfyui_port <= 65535 or service_port == comfyui_port:
        raise WorkbenchError("资产服务与 ComfyUI 必须配置为不同的 1–65535 端口。")
    if config_path.exists():
        _load_config(config_path)

    app_package = Path(__file__).resolve().parents[1]
    source_archive = app_package / "vendor" / "comfyui-0.42.0.zip"
    manifest_path = app_package / "vendor" / "comfyui-source.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(source_archive.read_bytes()).hexdigest()
    if manifest["sha256"] != digest or manifest["commit"] != COMFY_COMMIT:
        raise WorkbenchError("内置 ComfyUI 源码归档与固定来源清单不匹配。")

    for relative in ("data", "input", "output", "logs", "context", "comfyui-user", "comfyui-data", "run"):
        (workspace / relative).mkdir(parents=True, exist_ok=True)
    for relative in ("workflows", "subgraphs"):
        (workspace / "comfyui-user/default" / relative).mkdir(parents=True, exist_ok=True)
    templates = workspace / "comfyui-user/default/comfy.templates.json"
    if not templates.exists():
        templates.write_text("[]\n", encoding="utf-8")
    if not config_path.exists():
        config_path.write_text(
            "[server]\n"
            f'host = "127.0.0.1"\nport = {service_port}\n\n'
            '[storage]\ndata_dir = "data"\n\n'
            "[comfyui]\n"
            f'allowed_origins = ["http://127.0.0.1:{comfyui_port}", "http://localhost:{comfyui_port}"]\n',
            encoding="utf-8",
        )

    runtime = _runtime_dir()
    comfyui = runtime / "ComfyUI"
    runtime.mkdir(parents=True, exist_ok=True)
    commit_marker = comfyui / ".apf-native-build"
    env_dir = runtime / "comfyui-env"
    comfy_python = env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if reuse_runtime:
        if not commit_marker.is_file() or commit_marker.read_text(encoding="utf-8").strip() != digest or not comfy_python.is_file():
            raise WorkbenchError("可复用的固定 CPU runtime 不完整；请先正常执行 apf init。")
        install_frontend(workspace, frontend_assets)
        if activate:
            _activate_workspace(config_path)
        return config_path
    uv_env = _uv_environment(runtime)
    if not commit_marker.is_file() or commit_marker.read_text(encoding="utf-8").strip() != digest:
        if comfyui.exists():
            shutil.rmtree(comfyui)
        comfyui.mkdir(parents=True)
        with zipfile.ZipFile(source_archive) as archive:
            archive.extractall(runtime)
        commit_marker.write_text(digest, encoding="utf-8")

    install_frontend(workspace, frontend_assets)
    if not (env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")).is_file():
        _run([_uv(), "venv", "--managed-python", "--python", "3.12", str(env_dir)], env=uv_env)
    comfy_python = env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    _run([_uv(), "pip", "install", "--python", str(comfy_python), "--index-url", TORCH_CPU_INDEX,
          f"torch=={TORCH_CPU}", f"torchvision=={TORCHVISION_CPU}"], env=uv_env)
    requirements = app_package / "vendor" / "comfyui-0.42.0-windows-py312.lock" if os.name == "nt" else comfyui / "requirements.txt"
    _run([_uv(), "pip", "install", "--python", str(comfy_python), "-r", str(requirements)], env=uv_env)

    if activate:
        _activate_workspace(config_path)
    print(f"ComfyUI 源码: {manifest['comfyui_version']} ({manifest['commit']})")
    print(f"ComfyUI archive SHA-256: {digest}")
    return config_path


def _port_available(host: str, port: int) -> bool:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        try:
            listener.bind((host, port))
        except OSError:
            return False
    return True


def _identity(record: dict) -> psutil.Process | None:
    try:
        process = psutil.Process(record["pid"])
        created = process.create_time()
        recovering = "create_time" not in record
        if recovering:
            if not record["launch_started"] - 1.0 <= created <= record["launch_finished"] + 1.0:
                raise WorkbenchError("无法确认待登记进程的启动时间。")
        elif abs(created - record["create_time"]) > 1.0 or os.path.normcase(process.exe()) != os.path.normcase(record["executable"]):
            return None
        if process.cmdline() != record["command"] or process.environ().get("APF_WORKSPACE") != record["workspace"]:
            if recovering:
                raise WorkbenchError("无法确认待登记进程的命令或工作区。")
            return None
        if recovering:
            record["create_time"], record["executable"] = created, process.exe()
        return process if process.is_running() else None
    except psutil.NoSuchProcess:
        return None
    except (psutil.AccessDenied, OSError, KeyError, TypeError, ValueError) as exc:
        raise WorkbenchError("无法确认记录进程的身份。") from exc


def _state_path(workspace: Path) -> Path:
    return workspace / "run" / "processes.json"


def _read_state(workspace: Path) -> dict:
    path = _state_path(workspace)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"processes": []}


def _write_state(workspace: Path, state: dict) -> None:
    app_config._write_configuration_file(_state_path(workspace), json.dumps(state, ensure_ascii=False, indent=2))


def _control_path(workspace: Path) -> Path:
    return workspace / "run" / "control.json"


def _write_control(workspace: Path, control: dict) -> None:
    app_config._write_configuration_file(_control_path(workspace), json.dumps(control, ensure_ascii=False, indent=2))


def _recent(workspace: Path) -> WorkbenchResult | None:
    path = _control_path(workspace)
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return WorkbenchResult.model_validate_json(json.dumps(raw["result"]))


def _health(config_path: Path) -> bool:
    settings = app_config.load_running_settings(config_path.parent)
    try:
        token = settings.token_path.read_text(encoding="utf-8").strip()
        response = httpx.get(settings.service_url + "/api/v1/health", headers={"Authorization": f"Bearer {token}"}, timeout=2)
        return response.status_code == 200 and response.json().get("status") == "ok" and response.json().get("workspace") == str(settings.workspace)
    except (OSError, httpx.HTTPError, ValueError):
        return False


def _web_health(url: str, workspace: Path) -> bool:
    try:
        page = httpx.get(url, timeout=2)
        health = httpx.get(url + "/astrophotoflow/api/v1/health", headers={"Origin": url}, timeout=2)
        return (page.status_code == 200 and "AstroPhotoFlow" in page.text and health.status_code == 200
                and health.json().get("workspace") == str(workspace))
    except (httpx.HTTPError, ValueError):
        return False


def status(workspace_config: Path | None = None) -> WorkbenchState:
    config_path = resolve_config_path(workspace_config)
    workspace = _workspace_for_config(config_path)
    result = WorkbenchState(workspace=str(workspace), config_path=str(config_path), state="stopped", ready=False,
                            web_url=None, service_url=None, processes=[], effective_settings=None, versions={}, reason=None, recent=None)
    try:
        raw = _read_state(workspace)
        control_path = _control_path(workspace)
        control = json.loads(control_path.read_text(encoding="utf-8")) if control_path.is_file() else {}
        result.recent = WorkbenchResult.model_validate_json(json.dumps(control["result"])) if control else None
        live = []
        for record in raw["processes"]:
            if _identity(record) is not None:
                live.append(ProcessInfo.model_validate_json(json.dumps(record)))
        result.processes = live
        result.web_url, result.service_url = raw.get("web_url"), raw.get("service_url")
        result.versions = raw.get("versions", {})
        if live:
            result.effective_settings = ConfigValues.model_validate(raw["effective_settings"])
            complete = {item.role for item in live} == {"asset-service", "comfyui"}
            result.ready = bool(complete and _health(config_path) and result.web_url and _web_health(result.web_url, workspace))
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


def _record(process, role: str, workspace: Path, command: list[str]) -> dict:
    item = psutil.Process(process.pid)
    return {"role": role, "pid": process.pid, "create_time": item.create_time(), "executable": item.exe(),
            "command": command, "started_at": datetime.now(timezone.utc).isoformat(), "workspace": str(workspace)}


def _activate_workspace(config_path: Path) -> None:
    app_config._set_default_workspace(config_path.parent)


def _launch(command: list[str], cwd: Path, env: dict, log_path: Path) -> subprocess.Popen:
    with log_path.open("ab") as log:
        kwargs = {"stdin": subprocess.DEVNULL, "stdout": log, "stderr": subprocess.STDOUT, "cwd": str(cwd), "env": env}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        return subprocess.Popen(command, **kwargs)


@contextmanager
def _control_operation(config_path: Path, action: str, operation_id: UUID | None = None):
    workspace = _workspace_for_config(config_path)
    (workspace / "run").mkdir(parents=True, exist_ok=True)
    try:
        with FileLock(str(workspace / "run/control.lock"), timeout=5 if operation_id is not None else 0):
            previous = _recent(workspace)
            previous_control = json.loads(_control_path(workspace).read_text(encoding="utf-8")) if previous is not None else {}
            if previous is not None and previous.state in {"in_progress", "unknown"}:
                observed = status(config_path)
                resolved = (previous.action in {"start", "restart"} and observed.ready
                            or previous.action == "stop" and observed.state == "stopped")
                if not resolved:
                    if action != "stop":
                        raise WorkbenchError("上次启停结果尚未确认；请先查询状态和日志。")
                    _stop(config_path, control=previous_control)
            result = WorkbenchResult(operation_id=operation_id or uuid4(), action=action, state="in_progress", workspace=str(workspace),
                                     config_path=str(config_path), reused=False, web_url=None, service_url=None, detail=None,
                                     blockers=[], log_path=str(workspace / "logs"))
            owner = psutil.Process()
            control = {"result": result.model_dump(mode="json"),
                       "controller": {"pid": owner.pid, "create_time": owner.create_time()},
                       "started_at": datetime.now(timezone.utc).isoformat(), "finished_at": None}
            if previous_control.get("pending_process") is not None:
                control["pending_process"] = previous_control["pending_process"]
            _write_control(workspace, control)
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
                control["finished_at"] = datetime.now(timezone.utc).isoformat() if result.state != "unknown" else None
                try:
                    _write_control(workspace, control)
                except Exception as write_error:
                    if operation_error is not None and not isinstance(operation_error, Exception):
                        operation_error.add_note(f"控制结果未能保存：{write_error}；状态需核对。")
                        raise operation_error from write_error
                    prior = f"{operation_error}；" if operation_error is not None else ""
                    raise WorkbenchError(f"{prior}控制结果未能保存：{write_error}；状态需核对。") from write_error
    except Timeout as exc:
        raise WorkbenchError("同一workspace已有启停或初始化操作，请查询当前结果。") from exc


def initialize(workspace: Path, service_port: int = 8190, comfyui_port: int = 8188, *,
               frontend_assets: Path | None = None, activate: bool = True, reuse_runtime: bool = False) -> Path:
    workspace = workspace.expanduser().resolve()
    with _control_operation(workspace / "config.toml", "initialize"):
        observed = status(workspace / "config.toml")
        if observed.processes or observed.state == "unknown":
            raise WorkbenchError("workspace仍在使用或状态无法确认；先停止后再初始化。")
        return _initialize(workspace, service_port, comfyui_port, frontend_assets=frontend_assets,
                           activate=activate, reuse_runtime=reuse_runtime)


def _choose_port(host: str, preferred: int, *, exclude: int | None = None) -> int:
    for port in range(preferred, 65536):
        if port != exclude and _port_available(host, port):
            return port
    raise WorkbenchError("没有可用端口，请修改首选端口后重试。")


def _write_actual_ports(config_path: Path, service_port: int, origins: list[str]) -> None:
    app_config.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(str(app_config.CONFIG_PATH) + ".lock", timeout=0):
        # Read the latest other values under the same lock as configuration saves.
        current = app_config.get_configuration(config_path)
        values = current.saved.model_copy(update={"service_port": service_port, "allowed_origins": origins})
        app_config._write_configuration_file(config_path, app_config._configuration_text(values))


def _start(config_path: Path, result: WorkbenchResult, control: dict) -> None:
    workspace = config_path.parent
    observed = status(config_path)
    if observed.ready:
        result.reused, result.web_url, result.service_url = True, observed.web_url, observed.service_url
        result.detail = "已核对并复用当前workspace。"
        return
    if observed.processes or observed.state in {"partial", "unknown"}:
        raise WorkbenchError("工作台进程尚未全部停止或状态无法确认；先核对并停止原实例。")
    values = app_config.get_configuration(config_path).saved
    settings = app_config._settings_from_raw(app_config._raw_from_values(values), config_path)
    preferred_web = urlsplit(settings.allowed_origins[0]).port
    if preferred_web == settings.port:
        raise WorkbenchError("资产服务与ComfyUI必须配置为不同端口。")
    service_port = _choose_port(settings.host, settings.port)
    web_port = _choose_port("127.0.0.1", preferred_web, exclude=service_port)
    web_url = f"http://127.0.0.1:{web_port}"
    origins = [f"http://{urlsplit(origin).hostname if urlsplit(origin).hostname == 'localhost' else '127.0.0.1'}:{web_port}"
               for origin in values.allowed_origins]
    values = values.model_copy(update={"service_port": service_port, "allowed_origins": origins})
    effective = app_config._settings_from_raw(app_config._raw_from_values(values), config_path)
    runtime = _runtime_dir()
    comfyui = runtime / "ComfyUI"
    if not (workspace / "web/index.html").is_file():
        raise WorkbenchError("当前workspace缺少原生网页资源；请先运行apf init。")
    env = os.environ.copy()
    env.update({"ASTROPHOTOFLOW_CONFIG": str(config_path), "APF_WORKSPACE": str(workspace),
                "PYTHONPATH": str(Path(__file__).resolve().parents[2])})
    service_command = [sys.executable, "-m", "astrophotoflow.interfaces.http.cli", "serve"]
    comfy_python = runtime / "comfyui-env" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    comfy_command = [str(comfy_python), str(comfyui / "main.py"), "--cpu", "--listen", "127.0.0.1", "--port", str(web_port),
                     "--base-directory", str(workspace / "comfyui-data"), "--user-directory", str(workspace / "comfyui-user"),
                     "--input-directory", str(workspace / "input"), "--output-directory", str(workspace / "output"),
                     "--front-end-root", str(workspace / "web"), "--disable-all-custom-nodes", "--disable-api-nodes"]
    manifest = json.loads((Path(__file__).resolve().parents[1] / "vendor/comfyui-source.json").read_text(encoding="utf-8"))
    record = {"workspace": str(workspace), "config_path": str(config_path), "effective_settings": values.model_dump(),
              "web_url": web_url, "service_url": effective.service_url, "processes": [], "maintenance_operation_id": None,
              "versions": {"platform": version("astrophotoflow"), "comfyui": manifest["comfyui_version"]}}
    _write_state(workspace, record)
    pending_child = None
    try:
        for command, cwd, role, timeout in ((service_command, workspace, "asset-service", 90),
                                            (comfy_command, comfyui, "comfyui", 180)):
            control["pending_process"] = {"role": role, "pid": None, "command": command, "workspace": str(workspace),
                                          "started_at": datetime.now(timezone.utc).isoformat(), "launch_started": time.time()}
            _write_control(workspace, control)
            child = _launch(command, cwd, env, workspace / "logs" / ("service.log" if role == "asset-service" else "comfyui.log"))
            pending_child = child
            control["pending_process"].update({"pid": child.pid, "launch_finished": time.time()})
            _write_control(workspace, control)
            control["pending_process"] = _record(child, role, workspace, command)
            _write_control(workspace, control)
            record["processes"].append(control["pending_process"])
            app_config._update_running_state(workspace, {"processes": record["processes"]})
            control.pop("pending_process")
            _write_control(workspace, control)
            pending_child = None
            deadline = time.monotonic() + timeout
            while True:
                if child.poll() is not None:
                    raise WorkbenchError(f"{role}启动失败；请查看workspace/logs。")
                ready = _health(config_path) if role == "asset-service" else _web_health(web_url, workspace)
                if ready:
                    break
                if time.monotonic() >= deadline:
                    raise WorkbenchError(f"{role}未能在{timeout}秒内就绪；请查看workspace/logs。")
                time.sleep(0.25)
    except Exception as startup_error:
        if pending_child is None and control.get("pending_process", {}).get("pid") is None:
            control.pop("pending_process", None)
        try:
            _stop(config_path, control=control, pending_child=pending_child)
        except Exception as cleanup_error:
            identity_detail = ""
            if pending_child is not None and control.get("pending_process") is not None and "create_time" not in control["pending_process"]:
                try:
                    control["pending_process"] = _record(pending_child, role, workspace, command)
                except Exception as identity_error:
                    identity_detail = f"；PID {pending_child.pid} 身份尚未确认：{identity_error}"
            raise WorkbenchError(
                f"{startup_error} 启动失败后的停止未完成：{cleanup_error}{identity_detail}"
            ) from startup_error
        raise
    result.web_url, result.service_url = web_url, effective.service_url
    try:
        _write_actual_ports(config_path, service_port, origins)
    except (OSError, Timeout, ApiError, app_config.ConfigurationError) as exc:
        result.detail = f"服务已就绪，但实际端口未保存：{exc}"


def _stop(config_path: Path, *, control: dict, pending_child=None) -> None:
    workspace = config_path.parent
    raw = _read_state(workspace)
    pending = control.get("pending_process")
    if pending is not None and pending.get("pid") is None:
        raise WorkbenchError("启动进程身份尚未登记，无法确认是否已停止；请先核对实际进程。")
    native = "effective_settings" in raw or pending is not None or any(
        item["role"] == "comfyui" and "--front-end-root" in item["command"] for item in raw["processes"])
    records = list(raw["processes"])
    if pending is not None and not any(
            item.get("pid") == pending["pid"] and item.get("role") == pending["role"] for item in records):
        records.append(pending)
    for record in reversed(records):
        is_pending_child = (pending_child is not None and pending is not None
                            and record["pid"] == pending["pid"] and record["role"] == pending["role"])
        if is_pending_child and pending_child.poll() is not None:
            process = None
        elif is_pending_child and record["role"] == "asset-service":
            process = pending_child
        elif is_pending_child:
            try:
                process = psutil.Process(pending_child.pid)
            except psutil.NoSuchProcess:
                if pending_child.poll() is None:
                    raise WorkbenchError(f"无法确认启动进程 {pending_child.pid} 已退出。")
                process = None
        else:
            process = _identity(record)
        if process is None:
            continue
        if native and record["role"] == "asset-service":
            settings = app_config.load_running_settings(workspace)
            token = settings.token_path.read_text(encoding="utf-8").strip()
            httpx.post(settings.service_url + "/internal/shutdown", headers={"Authorization": f"Bearer {token}"}, timeout=5).raise_for_status()
            try:
                process.wait(timeout=30)
            except (psutil.TimeoutExpired, subprocess.TimeoutExpired) as exc:
                raise WorkbenchError("导入或预览仍在排空，进程记录已保留；稍后查询并停止。") from exc
            continue
        family = [process, *process.children(recursive=True)]
        for member in family:
            if member.environ().get("APF_WORKSPACE") != str(workspace):
                raise WorkbenchError(f"进程{member.pid}不属于目标workspace，停止已中止。")
        for member in reversed(family):
            try:
                member.terminate()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(family, timeout=10)
        if alive:
            raise WorkbenchError("原生进程尚未退出，保留记录；请查询后再停止。")
    raw["processes"] = []
    if "effective_settings" in raw:
        app_config._update_running_state(workspace, {"processes": []})
    else:
        _write_state(workspace, raw)
    control.pop("pending_process", None)


def _operate(action: str, workspace_config: Path | None, operation_id: UUID | None = None) -> WorkbenchResult:
    config_path = resolve_config_path(workspace_config)
    with _control_operation(config_path, action, operation_id) as (result, control):
        if action == "start":
            _start(config_path, result, control)
        elif action == "stop":
            if _read_state(config_path.parent)["processes"] or control.get("pending_process") is not None:
                _stop(config_path, control=control)
        else:
            observed = status(config_path)
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
            _stop(config_path, control=control)
            _start(config_path, result, control)
        return result


def start(workspace_config: Path | None = None) -> WorkbenchResult:
    return _operate("start", workspace_config)


def stop(workspace_config: Path | None = None) -> WorkbenchResult:
    return _operate("stop", workspace_config)


def restart(workspace_config: Path | None = None, *, operation_id: UUID | None = None) -> WorkbenchResult:
    return _operate("restart", workspace_config, operation_id)


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
            env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
            command = [sys.executable, "-c",
                       "import sys; from pathlib import Path; from uuid import UUID; "
                       "from astrophotoflow.core.workbench import _web_restart; "
                       "_web_restart(Path(sys.argv[1]), UUID(sys.argv[2]))",
                       str(config_path), str(operation_id)]
            parent = psutil.Process()
            pending = {"result": result.model_dump(mode="json"),
                       "controller": {"pid": parent.pid, "create_time": parent.create_time()}}
            app_config._write_configuration_file(receipt, json.dumps(pending))
            try:
                child = _launch(command, workspace, env, log_path)
            except OSError as exc:
                result.state, result.detail = "failed", str(exc)
                pending["result"] = result.model_dump(mode="json")
                app_config._write_configuration_file(receipt, json.dumps(pending))
                raise
            owner = psutil.Process(child.pid)
            pending["controller"] = {"pid": child.pid, "create_time": owner.create_time()}
            app_config._write_configuration_file(receipt, json.dumps(pending))
            return result
    except Timeout as exc:
        raise WorkbenchError("已有启停操作正在进行，请稍后查询状态。") from exc


def _web_restart(config_path: Path, operation_id: UUID) -> None:
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
    app_config._write_configuration_file(receipt, json.dumps(raw))


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
