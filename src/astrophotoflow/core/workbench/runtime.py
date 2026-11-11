from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from filelock import FileLock, Timeout

from . import constants, paths
from .errors import WorkbenchError

_IDENTITY_SCRIPT = (
    "import json, sys\n"
    "import torch\n"
    "print(json.dumps({'version': sys.version.split()[0], 'base_prefix': sys.base_prefix, 'torch': torch.__version__}))\n"
)

PYTHON_VERSION = "3.12.15"


def uv_executable() -> str:
    executable = Path(sys.executable).with_name("uv.exe" if os.name == "nt" else "uv")
    if executable.is_file():
        return str(executable)
    found = shutil.which("uv")
    if found:
        return found
    raise WorkbenchError("找不到 uv。请在当前 Python 环境中安装产品依赖后重试。")


def uv_version() -> str:
    try:
        result = subprocess.run([uv_executable(), "--version"], check=False, capture_output=True, text=True, timeout=30,
                                env=os.environ.copy())
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else "unknown"


def uv_environment(runtime: Path) -> dict[str, str]:
    cache_dir = Path(os.environ.get("UV_CACHE_DIR", runtime / "uv-cache"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["UV_PYTHON_INSTALL_REGISTRY"] = "0"
    environment["UV_PYTHON_PREFERENCE"] = "only-managed"
    environment["UV_CACHE_DIR"] = str(cache_dir)
    return environment


def run_command(command: list[str], env: dict[str, str] | None = None) -> None:
    try:
        subprocess.run(command, check=True, env=env)
    except subprocess.CalledProcessError as exc:
        raise WorkbenchError(f"runtime准备命令失败（{exc.returncode}）；修复上述错误后重新执行apf runtime prepare。") from exc


def probe_python(python: Path, *, timeout: float = 120) -> dict | None:
    """Run the fixed interpreter and report its identity; None when it cannot run."""
    if not python.is_file():
        return None
    environment = os.environ.copy()
    environment["PYTHONNOUSERSITE"] = "1"
    try:
        result = subprocess.run([str(python), "-c", _IDENTITY_SCRIPT], check=False, capture_output=True, text=True,
                                timeout=timeout, env=environment)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode:
        return None
    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        return None
    if not isinstance(payload, dict) or not payload.get("torch"):
        return None
    return {key: payload[key] for key in ("version", "base_prefix", "torch") if isinstance(payload.get(key), str)}


def install_frontend(workspace: Path, frontend_assets: Path | None = None) -> Path:
    package = paths.package_directory()
    configured = frontend_assets if frontend_assets is not None else package / "web"
    if not (configured / "index.html").is_file():
        raise WorkbenchError(f"原生网页资源不存在：{configured / 'index.html'}")
    source = configured.resolve()
    target = workspace / "web"
    destination = target.resolve()
    if source.is_relative_to(destination) or destination.is_relative_to(source):
        raise WorkbenchError("请选择独立于 workspace 网页目录的构建产物。")
    if target.is_junction():
        target.rmdir()
    elif target.is_symlink():
        target.unlink()
    source_files = {path.relative_to(source) for path in source.rglob("*") if path.is_file()}
    shutil.copytree(source, target, dirs_exist_ok=True)
    for path in target.rglob("*"):
        if path.is_file() and path.relative_to(target) not in source_files:
            path.unlink()
    return target


def prepare_runtime(*, reuse_only: bool = False) -> dict:
    package = paths.package_directory()
    source_archive = package / "vendor/comfyui-0.42.0.zip"
    manifest = json.loads((package / "vendor/comfyui-source.json").read_text(encoding="utf-8"))
    digest = hashlib.sha256(source_archive.read_bytes()).hexdigest()
    if manifest["sha256"] != digest or manifest["commit"] != constants.COMFY_COMMIT:
        raise WorkbenchError("内置 ComfyUI 源码归档与固定来源清单不匹配。")
    runtime = paths.runtime_dir()
    runtime.mkdir(parents=True, exist_ok=True)
    try:
        with FileLock(str(runtime / ".prepare.lock"), timeout=0):
            return prepare_cpu_runtime(runtime, source_archive, digest, reuse_only=reuse_only)
    except Timeout as exc:
        raise WorkbenchError("该runtime已有准备操作，请等待原操作完成。") from exc


def _read_receipt(receipt: Path) -> tuple[dict | None, dict | None]:
    if not receipt.is_file():
        return None, None
    try:
        raw = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, None
    if not isinstance(raw, dict):
        return None, None
    if isinstance(raw.get("fingerprint"), dict):
        python = raw.get("python")
        return raw["fingerprint"], python if isinstance(python, dict) else None
    return raw, None


def _write_receipt(receipt: Path, fingerprint: dict, python: dict) -> None:
    pending = receipt.with_suffix(".pending")
    pending.write_text(json.dumps({"fingerprint": fingerprint, "python": python}, indent=2) + "\n", encoding="utf-8")
    pending.replace(receipt)


def runtime_fingerprint(source_archive: Path, digest: str) -> dict:
    lock = source_archive.with_name("comfyui-0.42.0-windows-py312.lock")
    return {"archive_sha256": digest, "python": "3.12", "platform": sys.platform, "uv": uv_version(),
            "torch": constants.TORCH_CPU, "torchvision": constants.TORCHVISION_CPU,
            "dependencies_sha256": hashlib.sha256(lock.read_bytes()).hexdigest() if os.name == "nt" else digest}


def prepare_cpu_runtime(runtime: Path, source_archive: Path, digest: str, *, reuse_only: bool) -> dict:
    comfyui = runtime / "ComfyUI"
    commit_marker = comfyui / ".apf-native-build"
    env_dir = runtime / "comfyui-env"
    comfy_python = env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    fingerprint = runtime_fingerprint(source_archive, digest)
    receipt = runtime / ".apf-runtime.json"
    prepared, recorded_python = _read_receipt(receipt)
    probed = probe_python(comfy_python)
    marker_ok = commit_marker.is_file() and commit_marker.read_text(encoding="utf-8").strip() == digest
    if (prepared == fingerprint and comfy_python.is_file() and marker_ok and probed is not None
            and (recorded_python is None or recorded_python == probed)):
        if recorded_python is None:
            _write_receipt(receipt, fingerprint, probed)
        return {"runtime": str(runtime), "reused": True, **fingerprint, "python": probed}
    if reuse_only:
        raise WorkbenchError("固定 CPU runtime 未准备完成或版本不匹配；请运行 apf runtime prepare。")
    receipt.unlink(missing_ok=True)
    uv_env = uv_environment(runtime)
    if not marker_ok:
        if comfyui.exists():
            shutil.rmtree(comfyui)
        comfyui.mkdir(parents=True)
        with zipfile.ZipFile(source_archive) as archive:
            archive.extractall(runtime)
        commit_marker.write_text(digest, encoding="utf-8")

    if probed is None and env_dir.exists():
        shutil.rmtree(env_dir)
    if not comfy_python.is_file():
        run_command([uv_executable(), "venv", "--python", PYTHON_VERSION, str(env_dir)], env=uv_env)
    run_command([uv_executable(), "pip", "install", "--python", str(comfy_python), *(["--no-deps"] if os.name == "nt" else []), "--index-url", constants.TORCH_CPU_INDEX,
          f"torch=={constants.TORCH_CPU}", f"torchvision=={constants.TORCHVISION_CPU}"], env=uv_env)
    requirements = source_archive.with_name("comfyui-0.42.0-windows-py312.lock") if os.name == "nt" else comfyui / "requirements.txt"
    run_command([uv_executable(), "pip", "install", "--python", str(comfy_python), "-r", str(requirements)], env=uv_env)
    probed = probe_python(comfy_python)
    if probed is None:
        raise WorkbenchError("固定 CPU runtime 已安装，但内置解释器无法运行（import torch 失败）；请检查安装日志后重试。")
    _write_receipt(receipt, fingerprint, probed)
    return {"runtime": str(runtime), "reused": False, **fingerprint, "python": probed}
