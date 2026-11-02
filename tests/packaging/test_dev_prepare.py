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
        elif any(str(part).endswith('dev_bundle_sources.py') for part in command):
            output = '{}'
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


def test_build_reuses_verified_main_checkout_assets(preparer, tmp_path, monkeypatch):
    module, commands, _ = preparer
    main = tmp_path / 'main'
    assets = main / '.artifacts/build/frontend'
    assets.mkdir(parents=True)
    (assets / 'index.html').touch()
    (assets / 'build-manifest.json').write_text('{"commit":"base-sha","distribution":"localhost"}')
    monkeypatch.setattr(module, 'main_checkout', lambda: main)
    monkeypatch.setattr(module.frontend_build_record, 'matches', lambda *args: True)
    workspace = tmp_path / '.artifacts/workspaces/feature'
    monkeypatch.setattr(sys, 'argv', ['dev_prepare', '--workspace', str(workspace), '--build'])
    assert module.main() == 0
    assert not any(command[:2] == ['pnpm', 'build'] for command in commands)
    assert any('--frontend-assets' in command and str(assets) in command for command in commands)
    report = json.loads((tmp_path / '.artifacts/dev-prepare.json').read_text(encoding='utf-8'))
    assert report['frontend_reuse'] == str(assets)


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
def test_bootstrap_selects_main_cache_from_absolute_worktree_pointer(tmp_path):
    powershell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    root = tmp_path / 'feature'
    scripts = root / 'scripts'
    scripts.mkdir(parents=True)
    script = scripts / 'bootstrap.ps1'
    script.write_bytes((Path(__file__).resolve().parents[2] / 'scripts/bootstrap.ps1').read_bytes())
    git_dir = tmp_path / 'main/.git/worktrees/feature'
    git_dir.mkdir(parents=True)
    (git_dir / 'commondir').write_text('../..', encoding='utf-8')
    (root / '.git').write_text(f'gitdir: {git_dir.as_posix()}\n', encoding='utf-8')
    env = {**os.environ, 'PATH': ''}
    env.pop('ASTROPHOTOFLOW_DEV_CACHE', None)
    env.pop('PSMODULEPATH', None)
    subprocess.run([str(powershell), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script),
                    '--offline', '--workspace', '.artifacts/workspaces/feature'], env=env, check=False,
                   capture_output=True, text=True)
    report = json.loads((root / '.artifacts/dev-prepare.json').read_text(encoding='utf-8-sig'))
    assert Path(report['cache_dir']) == tmp_path / 'main/.artifacts/cache'


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
    # Python exposes Windows environment keys in uppercase; do not inject PS7 modules into PS5.1.
    env.pop("PSMODULEPATH", None)
    result = subprocess.run([str(powershell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
                             "--offline", "--workspace", ".artifacts/workspaces/dev"],
                            cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert ("SHA256 mismatch" if corrupt else "Offline archive missing") in result.stderr
    assert not (tmp_path / ".artifacts/workspaces/dev").exists()
    receipt = json.loads((tmp_path / ".artifacts/dev-prepare.json").read_text(encoding="utf-8"))
    assert receipt["completed"] is False
    assert receipt["ready"] is False
    assert receipt["started_at"] and receipt["finished_at"]
    assert receipt["stages"][0]["exit_code"] == 1
    assert Path(receipt["stages"][0]["log"]).is_file()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows bootstrap")
def test_bootstrap_reuses_compatible_tools_until_version_process_exits(tmp_path):
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    source = Path(__file__).resolve().parents[2] / "scripts/bootstrap.ps1"
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "bootstrap.ps1").write_bytes(source.read_bytes())
    (scripts / "dev_prepare.py").write_text(
        'import json\nfrom pathlib import Path\n'
        'Path("prepared").touch()\n'
        'receipt = Path(".artifacts/dev-prepare.json")\n'
        'report = json.loads(receipt.read_text(encoding="utf-8-sig"))\n'
        'report.update(completed=True, finished_at="2026-10-30T23:00:00Z")\n'
        'receipt.write_text(json.dumps(report), encoding="utf-8")\n', encoding="utf-8"
    )
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
    # Python exposes Windows environment keys in uppercase; do not inject PS7 modules into PS5.1.
    env.pop("PSMODULEPATH", None)
    result = subprocess.run([str(powershell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(scripts / "bootstrap.ps1"),
                             "--offline", "--workspace", ".artifacts/workspaces/dev"],
                            cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "prepared").exists()
    assert not (tmp_path / ".artifacts/cache/toolchains").exists()
    receipt = json.loads((tmp_path / ".artifacts/dev-prepare.json").read_text(encoding="utf-8"))
    assert receipt["completed"] is True
    assert receipt["stages"][0]["exit_code"] == 0
    assert receipt["elapsed_seconds"] >= receipt["stages"][0]["elapsed_seconds"]


@pytest.mark.parametrize("control_state", ["unknown", "starting", "stopping"])
def test_unresolved_workspace_state_blocks_preparation(preparer, tmp_path, monkeypatch, control_state):
    module, commands, state = preparer
    workspace = tmp_path / ".artifacts/workspaces/feature"
    monkeypatch.setattr(sys, "argv", ["dev_prepare", "--workspace", str(workspace)])
    assert module.main() == 0
    state.update(state=control_state, ready=False, processes=[])
    (tmp_path / "uv.lock").write_text("changed", encoding="utf-8")
    commands.clear()
    assert module.main() == 1
    assert not any("sync" in command or "install" in command or "create" in command
                   or "build" in command or "runtime" in command for command in commands)
    receipt = json.loads((tmp_path / ".artifacts/dev-prepare.json").read_text(encoding="utf-8"))
    assert "状态" in receipt["error"]


@pytest.mark.parametrize("running", [False, True])
@pytest.mark.parametrize("change", ["content", "added", "removed"])
def test_same_head_changed_assets_sync_when_stopped_and_reject_when_running(
    preparer, tmp_path, monkeypatch, running, change
):
    module, commands, state = preparer
    workspace = tmp_path / ".artifacts/workspaces/feature"
    monkeypatch.setattr(sys, "argv", ["dev_prepare", "--workspace", str(workspace)])
    assert module.main() == 0
    assets = tmp_path / "assets"
    installed = workspace / "web"
    for directory in (assets, installed):
        directory.mkdir()
        (directory / "index.html").write_text("index", encoding="utf-8")
        (directory / "app.js").write_text("old", encoding="utf-8")
        (directory / "build-manifest.json").write_text(
            '{"commit":"base-sha","distribution":"localhost"}', encoding="utf-8"
        )
    if change == "content":
        (assets / "app.js").write_text("new", encoding="utf-8")
    elif change == "added":
        (assets / "new.js").write_text("new", encoding="utf-8")
    else:
        (assets / "app.js").unlink()
    state.update(state="running" if running else "stopped", ready=running,
                 processes=[{"pid": 42}] if running else [])
    monkeypatch.setattr(sys, "argv", ["dev_prepare", "--workspace", str(workspace),
                                      "--frontend-assets", str(assets)])
    commands.clear()
    assert module.main() == (1 if running else 0)
    workspace_commands = [command for command in commands if "create" in command]
    if running:
        assert not workspace_commands
        assert not any("sync" in command or "install" in command for command in commands)
    else:
        assert len(workspace_commands) == 1
        assert "--frontend-assets" in workspace_commands[0]


def test_actual_frontend_sync_removes_obsolete_assets_and_matches(preparer, tmp_path):
    from astrophotoflow.core.workbench import install_frontend

    module, _, _ = preparer
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "index.html").write_text("old", encoding="utf-8")
    (assets / "old.js").write_text("old", encoding="utf-8")
    workspace = tmp_path / "workspace"
    installed = install_frontend(workspace, assets)
    (assets / "old.js").unlink()
    (assets / "new.js").write_text("new", encoding="utf-8")
    (assets / "index.html").write_text("new", encoding="utf-8")
    assert not module.frontend_matches(assets, installed)
    install_frontend(workspace, assets)
    assert not (installed / "old.js").exists()
    assert module.frontend_matches(assets, installed)


def test_managed_python_is_separate_from_tools(preparer, tmp_path):
    module, _, _ = preparer
    env = module.environment(tmp_path / ".artifacts/workspaces/feature")
    assert Path(env["UV_PYTHON_INSTALL_DIR"]) == tmp_path / ".artifacts/managed-python"


def test_invalid_arguments_replace_previous_success_receipt(preparer, tmp_path, monkeypatch):
    module, commands, _ = preparer
    monkeypatch.setattr(sys, "argv", ["dev_prepare", "--workspace", str(tmp_path / ".artifacts/workspaces/feature")])
    assert module.main() == 0
    path = tmp_path / ".artifacts/dev-prepare.json"
    previous = json.loads(path.read_text(encoding="utf-8"))
    commands.clear()
    monkeypatch.setattr(sys, "argv", ["dev_prepare", "--workspace", str(tmp_path / "outside")])
    assert module.main() == 2
    failed = json.loads(path.read_text(encoding="utf-8"))
    assert failed["run_id"] != previous["run_id"]
    assert failed["completed"] is False and failed["ready"] is False
    assert failed["arguments"][-1] == str(tmp_path / "outside")
    assert failed["started_at"] and failed["finished_at"]
    assert "参数" in failed["error"]
    assert not commands


def test_build_failure_stops_before_runtime_and_start(preparer, tmp_path, monkeypatch):
    module, commands, _ = preparer
    original_run = module.subprocess.run

    def fail_build(command, **kwargs):
        if command == ["pnpm", "build"]:
            commands.append(command)
            return subprocess.CompletedProcess(command, 1, stdout="type check failed")
        return original_run(command, **kwargs)

    monkeypatch.setattr(module.subprocess, "run", fail_build)
    monkeypatch.setattr(sys, "argv", ["dev_prepare", "--workspace", str(tmp_path / ".artifacts/workspaces/feature"),
                                      "--build", "--start"])
    assert module.main() == 1
    assert not any("runtime" in command or "start" in command or "create" in command for command in commands)
    report = json.loads((tmp_path / ".artifacts/dev-prepare.json").read_text(encoding="utf-8"))
    assert not report["completed"] and not report["ready"]
    stage = report["stages"][-1]
    assert stage["name"] == "build" and stage["exit_code"] == 1
    assert Path(stage["log"]).read_text(encoding="utf-8") == "type check failed"
    assert Path(stage["log"]).parent.name == report["run_id"]


@pytest.mark.parametrize("start_state", ["completed", "failed"])
def test_full_prepare_builds_then_prepares_runtime_and_reports_start(preparer, tmp_path, monkeypatch, start_state):
    module, commands, _ = preparer
    original_run = module.subprocess.run

    def full_run(command, **kwargs):
        if command == ["pnpm", "build"]:
            commands.append(command)
            assets = tmp_path / ".artifacts/build/frontend"
            assets.mkdir(parents=True)
            (assets / "index.html").touch()
            (assets / "build-manifest.json").write_text(
                '{"commit":"base-sha","distribution":"localhost"}', encoding="utf-8"
            )
            return subprocess.CompletedProcess(command, 0, stdout="built")
        if "runtime" in command or "start" in command:
            commands.append(command)
            if "runtime" in command:
                kwargs["stderr"].write("runtime dependency preparation warning\n")
            result = {"runtime": "private", "reused": False} if "runtime" in command else {
                "state": start_state, "web_url": "http://127.0.0.1:32618", "service_url": "http://127.0.0.1:32620"
            }
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps(result))
        return original_run(command, **kwargs)

    monkeypatch.setattr(module.subprocess, "run", full_run)
    monkeypatch.setattr(sys, "argv", ["dev_prepare", "--workspace", str(tmp_path / ".artifacts/workspaces/feature"),
                                      "--build", "--start"])
    assert module.main() == (0 if start_state == "completed" else 1)
    report = json.loads((tmp_path / ".artifacts/dev-prepare.json").read_text(encoding="utf-8"))
    assert report["completed"] is (start_state == "completed")
    assert report["ready"] is (start_state == "completed")
    assert report["preview"]["web_url"] == "http://127.0.0.1:32618"
    names = [stage["name"] for stage in report["stages"]]
    assert names.index("build") < names.index("runtime") < names.index("workspace") < names.index("start")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows bootstrap")
@pytest.mark.parametrize("style", ["separate", "equals"])
def test_bootstrap_cache_argument_overrides_environment_before_tools(tmp_path, style):
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    source = Path(__file__).resolve().parents[2] / "scripts/bootstrap.ps1"
    script = tmp_path / "scripts/bootstrap.ps1"
    script.parent.mkdir()
    script.write_bytes(source.read_bytes())
    old_receipt = tmp_path / ".artifacts/dev-prepare.json"
    old_receipt.parent.mkdir()
    old_receipt.write_text('{"run_id":"old","completed":true,"ready":true}', encoding="utf-8")
    chosen = tmp_path / "chosen cache"
    env = {**os.environ, "PATH": "", "ASTROPHOTOFLOW_DEV_CACHE": str(tmp_path / "environment-cache")}
    env.pop("PSMODULEPATH", None)
    cache_args = ["--cache-dir", str(chosen)] if style == "separate" else [f"--cache-dir={chosen}"]
    result = subprocess.run([str(powershell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
                             "--offline", "--workspace", ".artifacts/workspaces/feature", *cache_args],
                            cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode == 1
    report = json.loads(old_receipt.read_text(encoding="utf-8"))
    assert report["run_id"] != "old"
    assert report["cache_dir"] == str(chosen)
    assert str(chosen / "toolchains/uv-0.13.5-win-x64.zip") in report["error"]
    assert report["completed"] is False and report["ready"] is False
    assert not (tmp_path / "environment-cache").exists()
    assert not (tmp_path / ".artifacts/workspaces/feature").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows bootstrap")
def test_bootstrap_reads_utf8_child_receipt_without_corrupting_paths(tmp_path):
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    source = (Path(__file__).resolve().parents[2] / "scripts/bootstrap.ps1").read_text(encoding="utf-8")
    read_child = next(line for line in source.splitlines() if "$apfChildReport = Get-Content" in line)
    receipt = tmp_path / "receipt.json"
    expected = {"workspace": "C:/工作区/开发", "error": "参数无效"}
    receipt.write_text(json.dumps(expected, ensure_ascii=False), encoding="utf-8")
    script = tmp_path / "read.ps1"
    script.write_text("$apfReceipt = '" + str(receipt).replace("'", "''") + "'\n" + read_child +
                      "\n[IO.File]::WriteAllText($apfReceipt, ($apfChildReport | ConvertTo-Json), "
                      "(New-Object Text.UTF8Encoding($false)))", encoding="utf-8-sig")
    env = dict(os.environ)
    env.pop("PSMODULEPATH", None)
    subprocess.run([str(powershell), "-NoProfile", "-File", str(script)], env=env, check=True, capture_output=True)
    assert json.loads(receipt.read_text(encoding="utf-8")) == expected


def test_explicit_private_runtime_does_not_reuse_the_default_runtime(preparer, tmp_path):
    module, _, _ = preparer
    workspace = tmp_path / ".artifacts/workspaces/modernization"
    private = tmp_path / ".artifacts/runtimes/modernization"
    original = module.environment(workspace)["ASTROPHOTOFLOW_RUNTIME"]
    selected = module.environment(workspace, runtime=private)
    assert Path(selected["ASTROPHOTOFLOW_RUNTIME"]) == private
    assert selected["ASTROPHOTOFLOW_RUNTIME"] != original
    assert os.environ.get("ASTROPHOTOFLOW_RUNTIME") != str(private)


def test_private_runtime_outside_feature_artifacts_is_rejected_before_preparation(preparer, tmp_path, monkeypatch):
    module, commands, _ = preparer
    monkeypatch.setattr(sys, "argv", ["dev_prepare.py", "--workspace", str(tmp_path / ".artifacts/workspaces/modernization"),
                                    "--runtime-dir", str(tmp_path / "external-runtime")])
    assert module.main() == 2
    assert commands == []
    assert not (tmp_path / "external-runtime").exists()


def test_bundle_sources_run_after_sync_with_private_python_and_separate_arguments(preparer, tmp_path, monkeypatch):
    module, commands, _ = preparer
    workspace = tmp_path / '.artifacts/workspaces/feature'
    source = 'sample-tool=' + str(tmp_path / 'bundle with spaces')
    monkeypatch.setattr(sys, 'argv', ['dev_prepare', '--workspace', str(workspace),
                                     '--bundle-source', source, '--clear-bundle-source', 'retired-tool'])
    assert module.main() == 0
    command = next(command for command in commands if any(str(part).endswith('dev_bundle_sources.py') for part in command))
    python = tmp_path / '.artifacts/venvs/dev' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    assert command == [str(python), str(tmp_path / 'scripts/dev_bundle_sources.py'), '--workspace', str(workspace),
                       '--bundle-source', source, '--clear-bundle-source', 'retired-tool']
    assert next(i for i, value in enumerate(commands) if value[:2] == ['uv', 'sync']) < commands.index(command)
    report = json.loads((tmp_path / '.artifacts/dev-prepare.json').read_text(encoding='utf-8'))
    stage = next(stage for stage in report['stages'] if stage['name'] == 'bundle-sources')
    assert stage['exit_code'] == 0 and Path(stage['log']).read_text(encoding='utf-8') == '{}'


@pytest.mark.parametrize('failure', ['process', 'generation', 'invalid-json'])
def test_bundle_source_failure_is_recorded_and_never_starts_services(preparer, tmp_path, monkeypatch, failure):
    module, commands, _ = preparer
    original_run = module.subprocess.run

    def run(command, **kwargs):
        if any(str(part).endswith('dev_bundle_sources.py') for part in command):
            commands.append(command)
            kwargs['stderr'].write('bundle diagnostic\n')
            output = '{"sample-tool":{"state":"failed","error":"generation failed"}}' if failure == 'generation' else 'not JSON'
            return subprocess.CompletedProcess(command, 1 if failure == 'process' else 0, stdout=output)
        if 'runtime' in command:
            return subprocess.CompletedProcess(command, 0, stdout='{}')
        return original_run(command, **kwargs)

    assets = tmp_path / 'assets'
    assets.mkdir()
    (assets / 'index.html').touch()
    (assets / 'build-manifest.json').write_text('{"commit":"base-sha","distribution":"localhost"}', encoding='utf-8')
    monkeypatch.setattr(module.subprocess, 'run', run)
    monkeypatch.setattr(sys, 'argv', ['dev_prepare', '--workspace', str(tmp_path / '.artifacts/workspaces/feature'),
                                     '--start', '--frontend-assets', str(assets)])
    assert module.main() == 1
    assert not any('start' in command for command in commands)
    report = json.loads((tmp_path / '.artifacts/dev-prepare.json').read_text(encoding='utf-8'))
    assert report['completed'] is False and report['ready'] is False
    assert report['stages'][-1]['name'] == 'bundle-sources'
    assert 'bundle diagnostic' in Path(report['stages'][-1]['log']).read_text(encoding='utf-8')
    if failure == 'generation':
        assert report['development_sources']['sample-tool']['error'] == 'generation failed'


@pytest.fixture(scope='module')
def isolated_bundle_python(tmp_path_factory):
    import venv

    root = tmp_path_factory.mktemp('bundle-helper-interpreters')
    for name in ('launcher', 'private'):
        venv.EnvBuilder(with_pip=False).create(root / name)
    relative = 'Scripts/python.exe' if os.name == 'nt' else 'bin/python'
    launcher, private = (root / name / relative for name in ('launcher', 'private'))
    env = {key: value for key, value in os.environ.items() if key not in {'PYTHONPATH', 'PYTHONHOME'}}
    site = Path(subprocess.check_output([str(private), '-c', 'import sysconfig; print(sysconfig.get_path("purelib"))'],
                                      env=env, text=True).strip())
    package = site / 'astrophotoflow/modules/software'
    package.mkdir(parents=True)
    (package / 'development.py').write_text(
        'import json\nfrom pathlib import Path\nfrom types import SimpleNamespace\n'
        'def configure(workspace, sources, clear, python):\n'
        '    return {"configured": {"workspace":str(workspace), "sources":sources, "clear":clear, "python":python}}\n'
        'def bindings(workspace):\n'
        '    path=Path(workspace)/"existing.json"\n'
        '    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}\n'
        'def source_state(workspace, key):\n'
        '    return SimpleNamespace(model_dump=lambda **kwargs: bindings(workspace)[key])\n', encoding='utf-8')
    probe = subprocess.run([str(launcher), '-c', 'import astrophotoflow'], env=env, capture_output=True, text=True, check=False)
    assert probe.returncode != 0 and 'ModuleNotFoundError' in probe.stderr
    return launcher, private, env


@pytest.mark.parametrize('mode', ['none', 'bind', 'clear', 'existing'])
def test_bundle_helper_uses_real_private_subprocess_without_parent_imports(isolated_bundle_python, tmp_path, mode):
    launcher, private, env = isolated_bundle_python
    helper = Path(__file__).resolve().parents[2] / 'scripts/dev_bundle_sources.py'
    arguments = ['--workspace', str(tmp_path)]
    if mode == 'bind':
        arguments += ['--bundle-source', 'sample-tool=' + str(tmp_path / 'source with spaces')]
    elif mode == 'clear':
        arguments += ['--clear-bundle-source', 'sample-tool']
    elif mode == 'existing':
        (tmp_path / 'existing.json').write_text('{"sample-tool":{"state":"ready"}}', encoding='utf-8')
    driver = 'import subprocess,sys; raise SystemExit(subprocess.call(sys.argv[1:]))'
    result = subprocess.run([str(launcher), '-c', driver, str(private), str(helper), *arguments],
                            cwd=tmp_path, env=env, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    value = json.loads(result.stdout)
    if mode in {'bind', 'clear'}:
        assert Path(value['configured']['python']) == private
        assert value['configured']['workspace'] == str(tmp_path)
        assert value['configured']['sources'] == ([arguments[-1]] if mode == 'bind' else [])
        assert value['configured']['clear'] == (['sample-tool'] if mode == 'clear' else [])
    else:
        assert value == ({'sample-tool': {'state': 'ready'}} if mode == 'existing' else {})


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows bootstrap')
@pytest.mark.parametrize('blocked', ['cache', 'npm/_logs'])
def test_bootstrap_rejects_unusable_cache_before_tool_install(tmp_path, blocked):
    powershell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    source = Path(__file__).resolve().parents[2] / 'scripts/bootstrap.ps1'
    script = tmp_path / 'scripts/bootstrap.ps1'
    script.parent.mkdir()
    script.write_bytes(source.read_bytes())
    cache = tmp_path / 'cache'
    target = cache if blocked == 'cache' else cache / blocked
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('keep this file', encoding='utf-8')
    env = {**os.environ, 'PATH': ''}
    env.pop('PSMODULEPATH', None)
    result = subprocess.run([str(powershell), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script),
                             '--cache-dir', str(cache), '--workspace', '.artifacts/workspaces/feature'],
                            env=env, capture_output=True, text=True, check=False)
    assert result.returncode == 1 and 'Cache is not writable:' in result.stderr
    receipt = json.loads((tmp_path / '.artifacts/dev-prepare.json').read_text(encoding='utf-8'))
    assert receipt['completed'] is False and receipt['ready'] is False
    assert receipt['cache_dir'] == str(cache)
    assert target.read_text(encoding='utf-8') == 'keep this file'
    assert not (tmp_path / '.artifacts/toolchains').exists()
    assert not list(cache.glob('.apf-write-check-*'))
