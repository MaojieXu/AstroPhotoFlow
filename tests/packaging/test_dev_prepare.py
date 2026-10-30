import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.fixture
def preparer(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[2] / "scripts/dev_prepare.py"
    spec = importlib.util.spec_from_file_location("dev_prepare", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    for name in ("uv.lock", "pyproject.toml", "setup.py", "frontend/package.json", "frontend/pnpm-lock.yaml", "frontend/pnpm-workspace.yaml"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
    commands = []
    workspace_state = {"ready": False, "processes": []}
    monkeypatch.setattr(module.shutil, "which", lambda name, **kwargs: name)

    def run(command, **kwargs):
        commands.append(command)
        output = ""
        if command[-1] == "--version":
            output = {"uv": "uv 0.13.5", "node": "v26.8.2", "pnpm": "11.13.1"}[command[0]]
        elif command[:2] == ["git", "ls-files"]:
            output = "frontend/package.json\0frontend/pnpm-lock.yaml\0frontend/pnpm-workspace.yaml\0"
        elif command[:2] == ["git", "rev-parse"]:
            output = "base-sha"
        elif command[:2] == ["uv", "sync"]:
            python = Path(kwargs["env"]["UV_PROJECT_ENVIRONMENT"]) / ("Scripts/python.exe" if module.os.name == "nt" else "bin/python")
            python.parent.mkdir(parents=True, exist_ok=True)
            python.touch()
        elif "install" in command:
            modules = tmp_path / "frontend/node_modules/.modules.yaml"
            modules.parent.mkdir(parents=True, exist_ok=True)
            modules.touch()
        elif "status" in command:
            output = json.dumps(workspace_state)
        elif "create" in command:
            workspace = Path(command[command.index("--workspace") + 1])
            workspace.mkdir(parents=True, exist_ok=True)
            config = workspace / "config.toml"
            config.touch()
            output = json.dumps({"workspace": str(workspace), "config_path": str(config)})
        return subprocess.CompletedProcess(command, 0, stdout=output)

    monkeypatch.setattr(module.subprocess, "run", run)
    return module, commands, workspace_state


def test_default_prepare_and_repeat_never_build_install_runtime_or_start(preparer, tmp_path, monkeypatch):
    module, commands, _ = preparer
    workspace = tmp_path / ".artifacts/workspaces/feature"
    monkeypatch.setattr(sys, "argv", ["dev_prepare", "--workspace", str(workspace)])
    assert module.main() == 0
    assert any(command[:2] == ["uv", "sync"] for command in commands)
    assert any("install" in command for command in commands)
    assert not any("build" in command or "runtime" in command or "start" in command for command in commands)
    commands.clear()
    assert module.main() == 0
    assert not any("sync" in command or "install" in command or "build" in command for command in commands)
    (tmp_path / "uv.lock").write_text("changed", encoding="utf-8")
    commands.clear()
    assert module.main() == 0
    assert any("sync" in command for command in commands)
    assert not any("install" in command for command in commands)


def test_wrong_frontend_sha_fails_before_installation(preparer, tmp_path, monkeypatch):
    module, commands, _ = preparer
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "index.html").touch()
    (assets / "build-manifest.json").write_text('{"commit":"other-sha"}', encoding="utf-8")
    workspace = tmp_path / ".artifacts/workspaces/feature"
    monkeypatch.setattr(sys, "argv", ["dev_prepare", "--workspace", str(workspace), "--start", "--frontend-assets", str(assets)])
    assert module.main() == 1
    assert not any("sync" in command or "install" in command for command in commands)
    assert not (workspace / "config.toml").exists()
    receipt = json.loads((tmp_path / ".artifacts/dev-prepare.json").read_text(encoding="utf-8"))
    assert "SHA" in receipt["error"]


def test_changed_dependencies_require_stopping_running_workspace(preparer, tmp_path, monkeypatch):
    module, commands, state = preparer
    workspace = tmp_path / ".artifacts/workspaces/feature"
    monkeypatch.setattr(sys, "argv", ["dev_prepare", "--workspace", str(workspace)])
    assert module.main() == 0
    state.update(ready=True, processes=[{"pid": 42}])
    (tmp_path / "uv.lock").write_text("changed", encoding="utf-8")
    commands.clear()
    assert module.main() == 1
    assert not any("sync" in command or "install" in command for command in commands)
    receipt = json.loads((tmp_path / ".artifacts/dev-prepare.json").read_text(encoding="utf-8"))
    assert "--stop" in receipt["error"]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows bootstrap")
@pytest.mark.parametrize("corrupt", [False, True])
def test_bootstrap_offline_rejects_missing_or_corrupt_archive(tmp_path, corrupt):
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    source = Path(__file__).resolve().parents[2] / "scripts/bootstrap.ps1"
    script = tmp_path / "scripts/bootstrap.ps1"
    script.parent.mkdir()
    script.write_bytes(source.read_bytes())
    if corrupt:
        archive = tmp_path / ".artifacts/cache/toolchains/uv-0.13.5-win-x64.zip"
        archive.parent.mkdir(parents=True)
        archive.write_bytes(b"not a verified executable archive")
    env = {**os.environ, "PATH": ""}
    env.pop("ASTROPHOTOFLOW_DEV_CACHE", None)
    result = subprocess.run([str(powershell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
                             "--offline", "--workspace", ".artifacts/workspaces/dev"],
                            cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert ("SHA256 mismatch" if corrupt else "Offline archive missing") in result.stderr
    assert not (tmp_path / ".artifacts/workspaces/dev").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows bootstrap")
def test_bootstrap_reuses_compatible_tools_until_version_process_exits(tmp_path):
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    source = Path(__file__).resolve().parents[2] / "scripts/bootstrap.ps1"
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "bootstrap.ps1").write_bytes(source.read_bytes())
    (scripts / "dev_prepare.py").write_text('from pathlib import Path; Path("prepared").touch()\n', encoding="utf-8")
    (tmp_path / "package.json").write_text('{"packageManager":"pnpm@11.13.1"}', encoding="utf-8")
    binaries = tmp_path / "bin"
    binaries.mkdir()
    python = sys.executable.replace("%", "%%")
    (binaries / "uv.cmd").write_text(
        '@echo off\nif "%~1"=="--version" (echo uv 0.13.5& exit /b 0)\n'
        f'<nul set /p "={python}"\necho.\nexit /b 0\n', encoding="utf-8")
    (binaries / "node.cmd").write_text(
        f'@echo off\necho v26.8.2\n"{powershell}" -NoProfile -Command "Start-Sleep -Milliseconds 100"\nexit /b 0\n',
        encoding="utf-8")
    (binaries / "pnpm.cmd").write_text('@echo off\necho 11.13.1\nexit /b 0\n', encoding="utf-8")
    env = {**os.environ, "PATH": str(binaries)}
    env.pop("ASTROPHOTOFLOW_DEV_CACHE", None)
    result = subprocess.run([str(powershell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(scripts / "bootstrap.ps1"),
                             "--offline", "--workspace", ".artifacts/workspaces/dev"],
                            cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "prepared").exists()
    assert not (tmp_path / ".artifacts/cache/toolchains").exists()
