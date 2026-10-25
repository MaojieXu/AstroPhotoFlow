from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import tomllib
import zipfile
from urllib.parse import urlsplit

import httpx
import psutil

from .client import CONFIG_PATH, config_path


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
    return _app_data() / "runtime" / "0.1.0"


def _active_config() -> Path:
    return config_path().resolve()


def _workspace_for_config(path: Path) -> Path:
    if path.name != "config.toml":
        raise WorkbenchError("workspace 配置文件必须命名为 config.toml。")
    return path.parent


def _load_config(path: Path) -> tuple[dict, int, str, int]:
    with path.open("rb") as stream:
        config = tomllib.load(stream)
    host = config["server"]["host"]
    service_port = config["server"]["port"]
    origin = config["comfyui"]["allowed_origins"][0]
    parsed = urlsplit(origin)
    if not parsed.hostname or parsed.port is None or not 1 <= service_port <= 65535 or service_port == parsed.port:
        raise WorkbenchError("workspace 配置中的 ComfyUI 来源无有效端口。")
    return config, service_port, parsed.hostname, parsed.port


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


def initialize(workspace: Path, service_port: int = 8190, comfyui_port: int = 8188) -> Path:
    workspace = workspace.expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    config_path = workspace / "config.toml"
    if not 1 <= service_port <= 65535 or not 1 <= comfyui_port <= 65535 or service_port == comfyui_port:
        raise WorkbenchError("资产服务与 ComfyUI 必须配置为不同的 1–65535 端口。")
    if config_path.exists():
        _load_config(config_path)

    app_package = Path(__file__).resolve().parent
    source_archive = app_package / "vendor" / "comfyui-0.42.0.zip"
    manifest_path = app_package / "vendor" / "comfyui-source.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(source_archive.read_bytes()).hexdigest()
    if manifest["sha256"] != digest or manifest["commit"] != COMFY_COMMIT:
        raise WorkbenchError("内置 ComfyUI 源码归档与固定来源清单不匹配。")

    for relative in ("data", "input", "output", "logs", "context", "comfyui-user", "run"):
        (workspace / relative).mkdir(parents=True, exist_ok=True)
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
    uv_env = _uv_environment(runtime)
    commit_marker = comfyui / ".apf-commit"
    if not commit_marker.is_file() or commit_marker.read_text(encoding="utf-8").strip() != COMFY_COMMIT:
        if comfyui.exists():
            shutil.rmtree(comfyui)
        comfyui.mkdir(parents=True)
        with zipfile.ZipFile(source_archive) as archive:
            archive.extractall(runtime)
        (comfyui / ".apf-commit").write_text(COMFY_COMMIT, encoding="utf-8")

    base_dir = runtime / "comfyui-data"
    plugin = base_dir / "custom_nodes" / "AstroPhotoFlow"
    base_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(app_package / "comfyui" / "extension", plugin, dirs_exist_ok=True)
    env_dir = runtime / "comfyui-env"
    if not (env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")).is_file():
        _run([_uv(), "venv", "--managed-python", "--python", "3.12", str(env_dir)], env=uv_env)
    comfy_python = env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    _run([_uv(), "pip", "install", "--python", str(comfy_python), "--index-url", TORCH_CPU_INDEX,
          f"torch=={TORCH_CPU}", f"torchvision=={TORCHVISION_CPU}"], env=uv_env)
    requirements = app_package / "vendor" / "comfyui-0.42.0-windows-py312.lock" if os.name == "nt" else comfyui / "requirements.txt"
    _run([_uv(), "pip", "install", "--python", str(comfy_python), "-r", str(requirements)], env=uv_env)

    _activate_workspace(config_path)
    print(f"ComfyUI 源码: {manifest['comfyui_version']} ({manifest['commit']})")
    print(f"ComfyUI archive SHA-256: {digest}")
    return config_path


def _port_available(host: str, port: int) -> bool:
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        try:
            listener.bind((host, port))
        except OSError:
            return False
    return True


def _identity(record: dict) -> psutil.Process | None:
    try:
        process = psutil.Process(record["pid"])
        if abs(process.create_time() - record["create_time"]) > 1.0:
            return None
        if os.path.normcase(process.exe()) != os.path.normcase(record["executable"]):
            return None
        if [os.path.normcase(arg) for arg in process.cmdline()] != [os.path.normcase(arg) for arg in record["command"]]:
            return None
        if process.environ().get("APF_WORKSPACE") != record["workspace"]:
            return None
        return process if process.is_running() else None
    except (psutil.Error, OSError, KeyError):
        return None


def _state_path(workspace: Path) -> Path:
    return workspace / "run" / "processes.json"


def _read_state(workspace: Path) -> dict:
    path = _state_path(workspace)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"processes": []}


def status(workspace_config: Path | None = None) -> tuple[str, list[dict]]:
    config_path = (workspace_config or _active_config()).resolve()
    workspace = _workspace_for_config(config_path)
    processes = _read_state(workspace).get("processes", [])
    live = [{"record": record, "process": _identity(record)} for record in processes]
    count = sum(item["process"] is not None for item in live)
    state = "stopped" if count == 0 else "running" if count == len(live) else "partial"
    return state, [item["record"] for item in live if item["process"] is not None]


def _record(process: subprocess.Popen, role: str, workspace: Path, command: list[str]) -> dict:
    item = psutil.Process(process.pid)
    return {
        "role": role,
        "pid": process.pid,
        "create_time": item.create_time(),
        "executable": item.exe(),
        "command": command,
        "started_at": time.time(),
        "workspace": str(workspace),
    }


def _activate_workspace(config_path: Path) -> None:
    pointer = CONFIG_PATH.parent / "active-workspace"
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text(str(config_path), encoding="utf-8")


def _launch(command: list[str], cwd: Path, env: dict, log_path: Path) -> subprocess.Popen:
    with log_path.open("ab") as log:
        kwargs = {"stdin": subprocess.DEVNULL, "stdout": log, "stderr": subprocess.STDOUT, "cwd": str(cwd), "env": env}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        return subprocess.Popen(command, **kwargs)


def _health(config_path: Path) -> bool:
    config, port, host, _comfy_port = _load_config(config_path)
    data_dir = Path(config["storage"]["data_dir"])
    if not data_dir.is_absolute():
        data_dir = config_path.parent / data_dir
    try:
        token = (data_dir / "service.token").read_text(encoding="utf-8").strip()
        response = httpx.get(f"http://{host}:{port}/api/v1/health", headers={"Authorization": f"Bearer {token}"}, timeout=1)
        return response.status_code == 200 and response.json().get("status") == "ok"
    except (OSError, httpx.HTTPError, ValueError):
        return False


def start(workspace_config: Path | None = None) -> str:
    config_path = (workspace_config or _active_config()).resolve()
    workspace = _workspace_for_config(config_path)
    _config, service_port, service_host, comfy_port = _load_config(config_path)
    state, _active = status(config_path)
    if state == "running":
        _activate_workspace(config_path)
        return "AstroPhotoFlow 工作台已在运行。"
    if state == "partial":
        raise WorkbenchError("工作台处于部分运行状态；先运行 apf stop，再重新启动。")
    if not _port_available(service_host, service_port):
        raise WorkbenchError(f"资产服务端口 {service_host}:{service_port} 已被占用。")
    if not _port_available("127.0.0.1", comfy_port):
        raise WorkbenchError(f"ComfyUI 端口 127.0.0.1:{comfy_port} 已被占用。")

    package_root = Path(__file__).resolve().parent
    runtime = _runtime_dir()
    comfyui = runtime / "ComfyUI"
    base_dir = runtime / "comfyui-data"
    env = os.environ.copy()
    env.update({
        "ASTROPHOTOFLOW_CONFIG": str(config_path),
        "APF_WORKSPACE": str(workspace),
        "APF_PACKAGE_ROOT": str(package_root),
        "APF_WORKBENCH_MANAGED": "1",
    })
    service_command = [sys.executable, "-m", "astrophotoflow.backend.cli", "serve"]
    comfy_python = runtime / "comfyui-env" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    comfy_command = [
        str(comfy_python), str(comfyui / "main.py"), "--cpu", "--listen", "127.0.0.1", "--port", str(comfy_port),
        "--base-directory", str(base_dir), "--user-directory", str(workspace / "comfyui-user"),
        "--input-directory", str(workspace / "input"), "--output-directory", str(workspace / "output"),
    ]
    launched: list[subprocess.Popen] = []
    records: list[dict] = []
    try:
        service = _launch(service_command, workspace, env, workspace / "logs" / "service.log")
        launched.append(service)
        records.append(_record(service, "asset-service", workspace, service_command))
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline and service.poll() is None and not _health(config_path):
            time.sleep(0.25)
        if service.poll() is not None or not _health(config_path):
            raise WorkbenchError("资产服务未能在 90 秒内启动；请查看 workspace/logs/service.log。")

        comfy = _launch(comfy_command, comfyui, env, workspace / "logs" / "comfyui.log")
        launched.append(comfy)
        records.append(_record(comfy, "comfyui", workspace, comfy_command))
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline and comfy.poll() is None:
            try:
                with socket.create_connection(("127.0.0.1", comfy_port), timeout=0.5):
                    break
            except OSError:
                time.sleep(0.5)
        else:
            raise WorkbenchError("ComfyUI 未能在 180 秒内启动；请查看 workspace/logs/comfyui.log。")
        _state_path(workspace).write_text(json.dumps({"processes": records}, indent=2), encoding="utf-8")
        _activate_workspace(config_path)
        return f"工作台已启动：资产服务 {service_host}:{service_port}，ComfyUI 127.0.0.1:{comfy_port}。"
    except (OSError, subprocess.SubprocessError) as exc:
        for process in reversed(launched):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        raise WorkbenchError(str(exc)) from exc
    except WorkbenchError:
        for process in reversed(launched):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        raise


def stop(workspace_config: Path | None = None) -> str:
    config_path = (workspace_config or _active_config()).resolve()
    workspace = _workspace_for_config(config_path)
    records = _read_state(workspace).get("processes", [])
    for record in reversed(records):
        process = _identity(record)
        if process is None:
            continue
        process.terminate()
        try:
            process.wait(timeout=10)
        except psutil.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    _state_path(workspace).write_text('{"processes": []}\n', encoding="utf-8")
    return "AstroPhotoFlow 工作台已停止。"
