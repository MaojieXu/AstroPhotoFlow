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


def uv_executable() -> str:
    executable = Path(sys.executable).with_name("uv.exe" if os.name == "nt" else "uv")
    if executable.is_file():
        return str(executable)
    found = shutil.which("uv")
    if found:
        return found
    raise WorkbenchError("找不到 uv。请在当前 Python 环境中安装产品依赖后重试。")


def uv_environment(runtime: Path) -> dict[str, str]:
    python_bin_dir = runtime / "python-bin"
    cache_dir = Path(os.environ.get("UV_CACHE_DIR", runtime / "uv-cache"))
    python_bin_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["UV_PYTHON_BIN_DIR"] = str(python_bin_dir)
    environment["UV_PYTHON_INSTALL_REGISTRY"] = "0"
    environment["UV_CACHE_DIR"] = str(cache_dir)
    return environment


def run_command(command: list[str], env: dict[str, str] | None = None) -> None:
    try:
        subprocess.run(command, check=True, env=env)
    except subprocess.CalledProcessError as exc:
        raise WorkbenchError(f"runtime准备命令失败（{exc.returncode}）；修复上述错误后重新执行apf runtime prepare。") from exc


def install_frontend(workspace: Path, frontend_assets: Path | None = None) -> Path:
    package = paths.package_directory()
    source = frontend_assets if frontend_assets is not None else package / "web"
    if not (source / "index.html").is_file():
        raise WorkbenchError(f"原生网页资源不存在：{source / 'index.html'}")
    target = workspace / "web"
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


def prepare_cpu_runtime(runtime: Path, source_archive: Path, digest: str, *, reuse_only: bool) -> dict:
    comfyui = runtime / "ComfyUI"
    commit_marker = comfyui / ".apf-native-build"
    env_dir = runtime / "comfyui-env"
    comfy_python = env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    lock = source_archive.with_name("comfyui-0.42.0-windows-py312.lock")
    fingerprint = {"archive_sha256": digest, "python": "3.12", "platform": sys.platform,
                   "torch": constants.TORCH_CPU, "torchvision": constants.TORCHVISION_CPU,
                   "dependencies_sha256": hashlib.sha256(lock.read_bytes()).hexdigest() if os.name == "nt" else digest}
    receipt = runtime / ".apf-runtime.json"
    prepared = json.loads(receipt.read_text(encoding="utf-8")) if receipt.is_file() else None
    if (prepared == fingerprint and comfy_python.is_file() and commit_marker.is_file()
            and commit_marker.read_text(encoding="utf-8").strip() == digest):
        return {"runtime": str(runtime), "reused": True, **fingerprint}
    if reuse_only:
        raise WorkbenchError("固定 CPU runtime 未准备完成或版本不匹配；请运行 apf runtime prepare。")
    receipt.unlink(missing_ok=True)
    uv_env = uv_environment(runtime)
    if not commit_marker.is_file() or commit_marker.read_text(encoding="utf-8").strip() != digest:
        if comfyui.exists():
            shutil.rmtree(comfyui)
        comfyui.mkdir(parents=True)
        with zipfile.ZipFile(source_archive) as archive:
            archive.extractall(runtime)
        commit_marker.write_text(digest, encoding="utf-8")

    if not (env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")).is_file():
        run_command([uv_executable(), "python", "install", *(["--no-registry"] if os.name == "nt" else []), "3.12"], env=uv_env)
        run_command([uv_executable(), "venv", "--managed-python", "--python", "3.12", str(env_dir)], env=uv_env)
    comfy_python = env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    run_command([uv_executable(), "pip", "install", "--python", str(comfy_python), *(["--no-deps"] if os.name == "nt" else []), "--index-url", constants.TORCH_CPU_INDEX,
          f"torch=={constants.TORCH_CPU}", f"torchvision=={constants.TORCHVISION_CPU}"], env=uv_env)
    requirements = lock if os.name == "nt" else comfyui / "requirements.txt"
    run_command([uv_executable(), "pip", "install", "--python", str(comfy_python), "-r", str(requirements)], env=uv_env)
    pending = receipt.with_suffix(".pending")
    pending.write_text(json.dumps(fingerprint, indent=2) + "\n", encoding="utf-8")
    pending.replace(receipt)
    return {"runtime": str(runtime), "reused": False, **fingerprint}
