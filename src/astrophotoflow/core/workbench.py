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
import zipfile
from urllib.parse import urlsplit

import httpx
import psutil

from astrophotoflow.core import config as app_config
from astrophotoflow.core.config import Settings, load_settings, resolve_config_path


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


def initialize(workspace: Path, service_port: int = 8190, comfyui_port: int = 8188, *,
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
    pointer = app_config.CONFIG_PATH.parent / "active-workspace"
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text(str(config_path), encoding="utf-8")


def _launch(command: list[str], cwd: Path, env: dict, log_path: Path) -> subprocess.Popen:
    with log_path.open("ab") as log:
        kwargs = {"stdin": subprocess.DEVNULL, "stdout": log, "stderr": subprocess.STDOUT, "cwd": str(cwd), "env": env}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        return subprocess.Popen(command, **kwargs)


def _health(config_path: Path) -> bool:
    settings = load_settings(config_path)
    try:
        token = settings.token_path.read_text(encoding="utf-8").strip()
        response = httpx.get(settings.service_url + "/api/v1/health", headers={"Authorization": f"Bearer {token}"}, timeout=1)
        return response.status_code == 200 and response.json().get("status") == "ok"
    except (OSError, httpx.HTTPError, ValueError):
        return False


def _web_health(url: str) -> bool:
    try:
        page = httpx.get(url, timeout=1)
        health = httpx.get(url + "/astrophotoflow/api/v1/health", headers={"Origin": url}, timeout=1)
        return page.status_code == 200 and "AstroPhotoFlow" in page.text and health.status_code == 200
    except httpx.HTTPError:
        return False


def start(workspace_config: Path | None = None, *, activate: bool = True) -> str:
    config_path = (workspace_config or _active_config()).resolve()
    workspace = _workspace_for_config(config_path)
    _config, service_port, service_host, comfy_port = _load_config(config_path)
    state, _active = status(config_path)
    if state == "running":
        if activate:
            _activate_workspace(config_path)
        return "AstroPhotoFlow 工作台已在运行。"
    if state == "partial":
        raise WorkbenchError("工作台处于部分运行状态；先运行 apf stop，再重新启动。")
    if not _port_available(service_host, service_port):
        raise WorkbenchError(f"资产服务端口 {service_host}:{service_port} 已被占用。")
    if not _port_available("127.0.0.1", comfy_port):
        raise WorkbenchError(f"ComfyUI 端口 127.0.0.1:{comfy_port} 已被占用。")

    package_root = Path(__file__).resolve().parents[1]
    runtime = _runtime_dir()
    comfyui = runtime / "ComfyUI"
    base_dir = workspace / "comfyui-data"
    if not (workspace / "web" / "index.html").is_file():
        raise WorkbenchError("当前 workspace 缺少原生网页资源；请先运行 apf init。")
    env = os.environ.copy()
    env.update({
        "ASTROPHOTOFLOW_CONFIG": str(config_path),
        "APF_WORKSPACE": str(workspace),
        "PYTHONPATH": str(package_root.parent),
    })
    service_command = [sys.executable, "-m", "astrophotoflow.interfaces.http.cli", "serve"]
    comfy_python = runtime / "comfyui-env" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    comfy_command = [
        str(comfy_python), str(comfyui / "main.py"), "--cpu", "--listen", "127.0.0.1", "--port", str(comfy_port),
        "--base-directory", str(base_dir), "--user-directory", str(workspace / "comfyui-user"),
        "--input-directory", str(workspace / "input"), "--output-directory", str(workspace / "output"),
        "--front-end-root", str(workspace / "web"), "--disable-all-custom-nodes", "--disable-api-nodes",
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
        web_url = f"http://127.0.0.1:{comfy_port}"
        while time.monotonic() < deadline and comfy.poll() is None and not _web_health(web_url):
            time.sleep(0.5)
        if comfy.poll() is not None or not _web_health(web_url):
            raise WorkbenchError("原生网页未能在 180 秒内启动；请查看 workspace/logs/comfyui.log。")
        _state_path(workspace).write_text(json.dumps({"processes": records}, indent=2), encoding="utf-8")
        if activate:
            _activate_workspace(config_path)
        return f"AstroPhotoFlow 已启动：{web_url}/#/workflows"
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
    native = any(record["role"] == "comfyui" and "--front-end-root" in record["command"] for record in records)
    for record in reversed(records):
        process = _identity(record)
        if process is None:
            continue
        if native and record["role"] == "asset-service":
            settings = load_settings(config_path)
            token = settings.token_path.read_text(encoding="utf-8").strip()
            httpx.post(settings.service_url + "/internal/shutdown", headers={"Authorization": f"Bearer {token}"}, timeout=5).raise_for_status()
            try:
                process.wait(timeout=30)
            except psutil.TimeoutExpired as exc:
                raise WorkbenchError("后台任务仍在排空，进程记录已保留；稍后再次运行 apf stop。") from exc
            continue
        family = []
        for member in [process, *process.children(recursive=True)]:
            try:
                if member.environ().get("APF_WORKSPACE") != str(workspace):
                    raise WorkbenchError(f"进程 {member.pid} 不属于当前 workspace，停止操作已中止。")
            except psutil.NoSuchProcess:
                continue
            family.append(member)
        for member in reversed(family):
            try:
                member.terminate()
            except psutil.NoSuchProcess:
                pass
        _gone, alive = psutil.wait_procs(family, timeout=10)
        for member in alive:
            try:
                member.kill()
            except psutil.NoSuchProcess:
                pass
        _gone, alive = psutil.wait_procs(alive, timeout=5)
        if alive:
            raise WorkbenchError(f"工作台进程未能退出：{[member.pid for member in alive]}")
    _state_path(workspace).write_text('{"processes": []}\n', encoding="utf-8")
    return "AstroPhotoFlow 工作台已停止。"
