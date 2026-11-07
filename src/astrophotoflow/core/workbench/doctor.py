from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

from astrophotoflow.core import config as app_config
from astrophotoflow.core.config import ConfigurationError, load_settings

from . import paths, runtime, state

OK = "ok"
WARN = "warn"
FAIL = "fail"


def _entry(name: str, status: str, detail: str) -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail}


def _python_checks() -> list[dict[str, str]]:
    checks = [_entry("python", OK, f"{sys.version.split()[0]}（{sys.executable}）")]
    base = Path(os.environ.get("ASTROPHOTOFLOW_DEV_PYTHON", sys._base_executable))
    if base.is_file():
        checks.append(_entry("python-base", OK, str(base)))
    else:
        checks.append(_entry("python-base", FAIL, f"开发入口解释器不存在：{base}；请重新运行 scripts/bootstrap.ps1"))
    return checks


def _version_tuple(text: str) -> tuple[int, ...] | None:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", text)
    return tuple(int(part) for part in match.groups()) if match else None


def _satisfies(version: tuple[int, ...], requirement: str) -> bool:
    current = (version + (0, 0, 0))[:3]
    for token in requirement.split():
        match = re.fullmatch(r"(>=|<=|>|<|=)?\s*(\d+(?:\.\d+){0,2})", token)
        if match is None:
            return True
        operator, raw = match.groups()
        operator = operator or "="
        wanted = (tuple(int(part) for part in raw.split(".")) + (0, 0, 0))[:3]
        difference = (current > wanted) - (current < wanted)
        if operator == ">=" and difference < 0:
            return False
        if operator == ">" and difference <= 0:
            return False
        if operator == "<=" and difference > 0:
            return False
        if operator == "<" and difference >= 0:
            return False
        if operator == "=" and difference != 0:
            return False
    return True


def _pinned_tools() -> dict[str, str]:
    package = paths.package_directory().parents[1] / "package.json"
    try:
        data = json.loads(package.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    pinned = {}
    node = data.get("engines", {}).get("node")
    if isinstance(node, str) and node.strip():
        pinned["node"] = node.strip()
    manager = data.get("packageManager")
    if isinstance(manager, str) and manager.startswith("pnpm@") and manager.count("@") == 1:
        pinned["pnpm"] = manager.split("@", 1)[1]
    return pinned


def _tool_checks() -> list[dict[str, str]]:
    pinned = _pinned_tools()
    checks = []
    for name in ("uv", "node", "pnpm"):
        executable = shutil.which(name)
        if executable is None:
            checks.append(_entry(f"tool:{name}", WARN, "PATH 中未找到；仅开发构建需要"))
            continue
        try:
            result = subprocess.run([executable, "--version"], check=False, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            checks.append(_entry(f"tool:{name}", WARN, f"无法执行：{executable}"))
            continue
        version = (result.stdout.strip() or result.stderr.strip() or "unknown")
        if result.returncode != 0:
            checks.append(_entry(f"tool:{name}", WARN, f"{version}（{executable}）"))
            continue
        requirement = pinned.get(name)
        parsed = _version_tuple(version)
        if requirement and parsed is not None and not _satisfies(parsed, requirement):
            checks.append(_entry(f"tool:{name}", WARN,
                                 f"{version}（{executable}）；项目固定 {requirement}，请通过 scripts/bootstrap.ps1 准备"))
            continue
        checks.append(_entry(f"tool:{name}", OK, f"{version}（{executable}）"))
    return checks


def _runtime_directory() -> tuple[Path, bool]:
    if os.environ.get("ASTROPHOTOFLOW_RUNTIME"):
        return paths.runtime_dir(), False
    default = paths.runtime_dir()
    if default.is_dir():
        return default, False
    repo = paths.package_directory().parents[1]
    dev = repo / ".artifacts/local-app-data/AstroPhotoFlow/runtime/native-web-0.1.0"
    if dev.is_dir():
        return dev, True
    return default, False


def _runtime_checks() -> list[dict[str, str]]:
    directory, from_checkout = _runtime_directory()
    package = paths.package_directory()
    comfy_python = directory / "comfyui-env" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    receipt = directory / ".apf-runtime.json"
    where = f"{directory}（开发目录）" if from_checkout else str(directory)
    if not directory.is_dir():
        return [_entry("runtime", WARN, f"尚未准备：{where}；运行 apf runtime prepare")]
    checks = []
    if not receipt.is_file():
        checks.append(_entry("runtime-receipt", WARN, f"缺少 .apf-runtime.json；运行 apf runtime prepare：{where}"))
    else:
        try:
            raw = json.loads(receipt.read_text(encoding="utf-8"))
            prepared = raw.get("fingerprint") if isinstance(raw.get("fingerprint"), dict) else raw
            archive = package / "vendor/comfyui-0.42.0.zip"
            expected = runtime.runtime_fingerprint(archive, hashlib.sha256(archive.read_bytes()).hexdigest())
            # The uv version only controls whether the next preparation rebuilds; a differently
            # installed uv can still run the same fixed runtime, so it is reported but not compared.
            prepared_uv = prepared.get("uv")
            if {key: value for key, value in prepared.items() if key != "uv"} != {key: value for key, value in expected.items() if key != "uv"}:
                checks.append(_entry("runtime-receipt", FAIL, "指纹与当前锁文件/工具链不一致；运行 apf runtime prepare 重建"))
            else:
                checks.append(_entry("runtime-receipt", OK, f"指纹与固定来源一致（准备时 uv {prepared_uv}）"))
        except (OSError, ValueError) as exc:
            checks.append(_entry("runtime-receipt", FAIL, f"无法读取：{exc}"))
    probe = runtime.probe_python(comfy_python)
    if probe is None:
        checks.append(_entry("runtime-python", FAIL, f"内置解释器无法运行（import torch 失败）：{comfy_python}；运行 apf runtime prepare"))
    else:
        checks.append(_entry("runtime-python", OK, f"Python {probe.get('version')}，torch {probe.get('torch')}"))
    return checks


def _workspace_checks(workspace: Path | None) -> list[dict[str, str]]:
    config_path = (workspace.expanduser() / "config.toml").resolve() if workspace else None
    try:
        resolved = app_config.resolve_config_path(config_path)
        settings = load_settings(resolved)
    except (ConfigurationError, OSError) as exc:
        # Without an explicit --workspace the default pointer may simply be unset on a
        # freshly bootstrapped machine; that is advisory, not a broken environment.
        return [_entry("workspace", FAIL if workspace is not None else WARN, str(exc))]
    preferred_web = urlsplit(settings.allowed_origins[0]).port
    checks = [_entry("workspace", OK, f"{settings.workspace}（{resolved}）")]
    record_path = state.state_path(settings.workspace)
    if record_path.is_file():
        try:
            record = state.read_state(settings.workspace)
            ports = record.get("actual_ports") or {}
            if ports:
                checks.append(_entry("workspace-ports", OK,
                                     f"最近运行 资产服务 {ports.get('service')} / 网页 {ports.get('web')}；"
                                     f"config.toml 首选 {settings.port} / {preferred_web}"))
            else:
                checks.append(_entry("workspace-ports", WARN, "运行记录缺少 actual_ports；重启工作台后重新记录"))
        except (OSError, ValueError, KeyError) as exc:
            checks.append(_entry("workspace-ports", WARN, f"无法读取运行记录：{exc}"))
    pointer = app_config.default_workspace()
    if pointer is None:
        checks.append(_entry("default-workspace", WARN, "未设置默认 workspace；缺省 --workspace 的命令需要它"))
    elif not (pointer / "config.toml").is_file():
        checks.append(_entry("default-workspace", WARN,
                             f"默认指针指向 {pointer}，但该目录没有 config.toml；用 apf init --workspace <路径> 修复"))
    elif pointer.resolve() != settings.workspace.resolve():
        checks.append(_entry("default-workspace", WARN, f"默认指针指向 {pointer}，与当前 workspace 不同"))
    else:
        checks.append(_entry("default-workspace", OK, str(pointer)))
    return checks


def doctor_checks(workspace: Path | None = None) -> list[dict[str, str]]:
    return [*_python_checks(), *_tool_checks(), *_runtime_checks(), *_workspace_checks(workspace)]
